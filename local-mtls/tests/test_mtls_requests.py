import socket
import subprocess
import threading
import time
from io import BytesIO
from pathlib import Path

import pytest
import requests

from mtls.client_requests import get
from mtls.server import create_server as create_stdlib_server
from mtls_fastapi.server import create_server as create_fastapi_server

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
def server(request, certificates):
    """既存の両サーバーへ接続し、クライアントだけを置き換えて検証する。"""
    trusted = certificates / "trusted"
    options = dict(certfile=trusted / "server.crt", keyfile=trusted / "server.key", cafile=trusted / "ca.crt")
    if request.param == "stdlib":
        instance = create_stdlib_server(**options, port=0)
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
        # ソケットを先に確保し、ポートの取り合いを避ける。
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            instance = create_fastapi_server(**options, port=port)
            thread = threading.Thread(target=instance.run, kwargs={"sockets": [listener]}, daemon=True)
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
def test_rejects_invalid_client_authentication(certificates, server, client_certificate):
    # 正常接続を前後に挟み、サーバー停止による失敗と区別する。
    assert connect(server, certificates) == BODY
    trusted = certificates / "trusted"
    untrusted = certificates / "untrusted"
    with pytest.raises(requests.exceptions.ConnectionError) as error:
        if client_certificate == "missing":
            get(server, trusted / "ca.crt")
        else:
            get(server, trusted / "ca.crt", untrusted / "client.crt", untrusted / "client.key")

    # TLS 拒否・接続切断を確認し、接続拒否やタイムアウトを成功扱いしない。
    message = str(error.value)
    assert any(
        reason in message
        for reason in (
            "CERTIFICATE_REQUIRED",
            "HANDSHAKE_FAILURE",
            "UNKNOWN_CA",
            "RemoteDisconnected",
            "Connection reset by peer",
            "EOF occurred",
        )
    ), message
    assert "CERTIFICATE_VERIFY_FAILED" not in message
    print(f"クライアント証明書 {client_certificate}: {type(error.value).__name__}: {message}")
    assert connect(server, certificates) == BODY


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
