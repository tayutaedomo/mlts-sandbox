"""Requests による両 mTLS サーバーへの接続を検証する。

概要:
    相互認証の成功・失敗と、引数エラー・HTTP エラーを比較する。

方針:
    - 実サーバーの TLS 拒否理由と HTTP 未到達を照合し、拒否前後に正常接続する。
    - 入力検証と HTTP エラーの伝播は単体で確認する。

テストケース一覧:
    - 正常な証明書で両サーバーに接続する。
    - 証明書なし・非信頼 CA の接続を、それぞれの理由で拒否する。
    - サーバー検証用 CA の不一致を拒否する。
    - 証明書・秘密鍵の片方だけの指定を拒否する。
    - HTTP エラーを呼び出し元へ返す。
"""

import socket
import ssl
import subprocess
import threading
import time
from io import BytesIO
from pathlib import Path

import pytest
import requests

from mtls.client_requests import get
from mtls.server import HelloHandler
from mtls.server import create_server as create_stdlib_server
from mtls_fastapi import server as fastapi_server

CERT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate-certs.sh"
BODY = "ローカル mTLS サーバーからの応答です。\n"


@pytest.fixture(scope="session")
def certificates(tmp_path_factory):
    """信頼する CA と別の CA を同じ手順で作り、発行元だけを変える。"""
    root = tmp_path_factory.mktemp("requests-certificates")
    for name in ("trusted", "untrusted"):
        subprocess.run(["sh", str(CERT_SCRIPT), str(root / name)], check=True, capture_output=True, text=True)
    return root


@pytest.fixture(params=["stdlib", "fastapi"])
def server(request, certificates, monkeypatch, server_observations, run_uvicorn):
    """既存の両サーバーへ接続し、クライアントだけを置き換えて検証する。"""
    trusted = certificates / "trusted"
    options = dict(certfile=trusted / "server.crt", keyfile=trusted / "server.key", cafile=trusted / "ca.crt")
    if request.param == "stdlib":
        instance = create_stdlib_server(**options, port=0)
        original_get_request = instance.get_request
        original_do_get = HelloHandler.do_GET

        def track_handshake():
            try:
                return original_get_request()
            except ssl.SSLError as error:
                server_observations["tls_errors"].put((error.reason, getattr(error, "verify_code", None)))
                raise

        def track_http(handler):
            server_observations["requests"].append(handler.path)
            return original_do_get(handler)

        monkeypatch.setattr(instance, "get_request", track_handshake)
        monkeypatch.setattr(HelloHandler, "do_GET", track_http)
        thread = threading.Thread(target=instance.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"https://127.0.0.1:{instance.server_port}/"
        finally:
            instance.shutdown()
            instance.server_close()
            thread.join(timeout=5)
            assert not thread.is_alive()
    else:
        app = fastapi_server.app

        async def track_requests(scope, receive, send):
            if scope["type"] == "http":
                server_observations["requests"].append(scope["path"])
            await app(scope, receive, send)

        monkeypatch.setattr(fastapi_server, "app", track_requests)
        # ソケットを先に確保し、ポートの取り合いを避ける。
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            instance = fastapi_server.create_server(**options, port=port)
            thread = threading.Thread(target=run_uvicorn, args=(instance, [listener]), daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 10
                while not instance.started:
                    assert thread.is_alive(), "Uvicorn が起動前に終了しました"
                    assert time.monotonic() < deadline, "Uvicorn の起動が10秒以内に完了しませんでした"
                    time.sleep(0.01)
                yield f"https://127.0.0.1:{port}/"
            finally:
                instance.should_exit = True
                thread.join(timeout=5)
                assert not thread.is_alive(), "Uvicorn が5秒以内に停止しませんでした"


def connect(url, certificates):
    trusted = certificates / "trusted"
    return get(url, trusted / "ca.crt", trusted / "client.crt", trusted / "client.key")


def test_connects_with_trusted_client_certificate(certificates, server):
    assert connect(server, certificates) == BODY


@pytest.mark.parametrize("client_certificate", ["missing", "untrusted"])
def test_rejects_invalid_client_authentication(certificates, server, client_certificate, server_observations):
    # 正常接続を前後に挟み、サーバー停止による失敗と区別する。
    assert connect(server, certificates) == BODY
    trusted = certificates / "trusted"
    untrusted = certificates / "untrusted"
    with pytest.raises(requests.exceptions.ConnectionError) as error:
        if client_certificate == "missing":
            get(server, trusted / "ca.crt")
        else:
            get(server, trusted / "ca.crt", untrusted / "client.crt", untrusted / "client.key")

    # 切断の例外メッセージは環境で変わる。証明書を拒否した理由はサーバー側で照合する。
    assert not isinstance(error.value, requests.exceptions.Timeout)
    assert "CERTIFICATE_VERIFY_FAILED" not in str(error.value)
    reason, verify_code = server_observations["tls_errors"].get(timeout=5)
    if client_certificate == "missing":
        assert reason == "PEER_DID_NOT_RETURN_A_CERTIFICATE"
    else:
        assert reason == "CERTIFICATE_VERIFY_FAILED"
        assert verify_code == 20
    assert server_observations["requests"] == ["/"]
    print(f"クライアント証明書 {client_certificate}: {type(error.value).__name__}: {error.value}")
    assert connect(server, certificates) == BODY
    assert server_observations["requests"] == ["/", "/"]


def test_rejects_server_certificate_with_wrong_ca(certificates, server):
    trusted = certificates / "trusted"
    with pytest.raises(requests.exceptions.SSLError, match="CERTIFICATE_VERIFY_FAILED"):
        get(server, certificates / "untrusted" / "ca.crt", trusted / "client.crt", trusted / "client.key")


@pytest.mark.parametrize("certfile,keyfile", [("client.crt", None), (None, "client.key")])
def test_requires_certificate_and_key_together(certfile, keyfile):
    # 不完全な指定は接続前に説明付きで拒否する。
    with pytest.raises(ValueError, match="証明書と秘密鍵は両方"):
        get("https://127.0.0.1:1/", "ca.crt", certfile, keyfile)


def test_raises_for_http_error(monkeypatch):
    # HTTP エラーは、TLS の失敗とは異なる HTTPError で呼び出し元へ返す。
    response = requests.Response()
    response.raw = BytesIO(b"")
    response.status_code = 403
    response.url = "https://localhost/"
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)
    with pytest.raises(requests.exceptions.HTTPError):
        get(response.url, "ca.crt")
