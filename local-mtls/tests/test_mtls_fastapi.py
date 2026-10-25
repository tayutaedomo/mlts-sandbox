import socket
import ssl
import subprocess
import threading
import time
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import URLError

import pytest

from mtls.client import get
from mtls_fastapi import server as fastapi_server
from tls.client import get as get_without_client_certificate

PROJECT_DIR = Path(__file__).resolve().parents[1]
CERT_SCRIPT = PROJECT_DIR / "scripts" / "generate-certs.sh"


@pytest.fixture(scope="session")
def certificates(tmp_path_factory):
    """既存の生成スクリプトで、相互認証用の証明書一式を作る。"""
    cert_dir = tmp_path_factory.mktemp("fastapi-certificates")
    result = subprocess.run(["sh", str(CERT_SCRIPT), str(cert_dir)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return cert_dir


@pytest.fixture
def mtls_fastapi_server(certificates, monkeypatch):
    """実際の Uvicorn を空きポートで起動し、テスト後に停止する。"""
    # テスト内だけで HTTP 到達を記録し、TLS 拒否がアプリの処理前かを確認する。
    requests = []
    app = fastapi_server.app

    async def track_requests(scope, receive, send):
        if scope["type"] == "http":
            requests.append(scope["path"])
        await app(scope, receive, send)

    monkeypatch.setattr(fastapi_server, "app", track_requests)

    # ポートを先に確保し、そのソケットを Uvicorn に渡して取り合いを避ける。
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = fastapi_server.create_server(
            certfile=certificates / "server.crt",
            keyfile=certificates / "server.key",
            cafile=certificates / "ca.crt",
            host="127.0.0.1",
            port=port,
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            # 固定秒数を待つのではなく、起動完了か起動失敗を期限付きで確認する。
            deadline = time.monotonic() + 10
            while not server.started:
                if not thread.is_alive():
                    pytest.fail("Uvicorn が起動前に終了しました")
                if time.monotonic() >= deadline:
                    pytest.fail("Uvicorn の起動が10秒以内に完了しませんでした")
                time.sleep(0.01)
            yield f"https://127.0.0.1:{port}/", requests
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive(), "Uvicorn が5秒以内に停止しませんでした"


def test_connects_with_client_certificate_signed_by_trusted_ca(certificates, mtls_fastapi_server):
    # 既存クライアントを使い、サーバー実装だけを置き換えて比較する。
    url, requests = mtls_fastapi_server
    body = get(
        url,
        cafile=certificates / "ca.crt",
        certfile=certificates / "client.crt",
        keyfile=certificates / "client.key",
    )

    assert body == "ローカル mTLS サーバーからの応答です。\n"
    assert requests == ["/"]


@pytest.fixture(scope="session")
def untrusted_certificates(tmp_path_factory):
    """クライアントが提示する証明書だけを別の発行元にするための CA。"""
    cert_dir = tmp_path_factory.mktemp("untrusted-fastapi-certificates")
    result = subprocess.run(["sh", str(CERT_SCRIPT), str(cert_dir)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return cert_dir


@pytest.mark.parametrize("client_certificate", ["missing", "untrusted"])
def test_rejects_invalid_client_authentication(
    certificates, untrusted_certificates, mtls_fastapi_server, client_certificate
):
    url, requests = mtls_fastapi_server

    def connect_with_trusted_certificate():
        return get(url, certificates / "ca.crt", certificates / "client.crt", certificates / "client.key")

    # 拒否の前後で正常接続し、サーバー停止による通信失敗と区別する。
    assert connect_with_trusted_certificate() == "ローカル mTLS サーバーからの応答です。\n"
    assert requests == ["/"]

    # asyncio の TLS 処理では、拒否が TLS アラートではなく接続切断で見える場合もある。
    with pytest.raises((URLError, ssl.SSLError, RemoteDisconnected, ConnectionResetError)) as error:
        if client_certificate == "missing":
            get_without_client_certificate(url, cafile=certificates / "ca.crt")
        else:
            get(
                url,
                cafile=certificates / "ca.crt",
                certfile=untrusted_certificates / "client.crt",
                keyfile=untrusted_certificates / "client.key",
            )

    cause = error.value.reason if isinstance(error.value, URLError) else error.value
    assert isinstance(cause, (ssl.SSLError, RemoteDisconnected, ConnectionResetError))
    # サーバー証明書の検証失敗や、接続拒否・タイムアウトは今回の成功条件に含めない。
    assert not isinstance(cause, ssl.SSLCertVerificationError)
    assert requests == ["/"]
    print(f"クライアント証明書 {client_certificate}: {type(cause).__name__}: {cause}")

    assert connect_with_trusted_certificate() == "ローカル mTLS サーバーからの応答です。\n"
    assert requests == ["/", "/"]
