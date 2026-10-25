import ssl
import subprocess
import threading
from pathlib import Path
from urllib.error import URLError

import pytest

from mtls.client import get
from mtls.server import create_server
from tls.client import get as get_without_client_certificate

PROJECT_DIR = Path(__file__).resolve().parents[1]
CERT_SCRIPT = PROJECT_DIR / "scripts" / "generate-certs.sh"


@pytest.fixture(scope="session")
def certificates(tmp_path_factory):
    """同じ CA が発行したサーバー・クライアント証明書を作る。"""
    cert_dir = tmp_path_factory.mktemp("mtls-certificates")
    # 生成失敗時は OpenSSL のエラーも表示し、環境差を調べられるようにする。
    result = subprocess.run(["sh", str(CERT_SCRIPT), str(cert_dir)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return cert_dir


@pytest.fixture(scope="session")
def untrusted_certificates(tmp_path_factory):
    """サーバーが信頼しない別の CA からクライアント証明書を発行する。"""
    cert_dir = tmp_path_factory.mktemp("untrusted-mtls-certificates")
    result = subprocess.run(["sh", str(CERT_SCRIPT), str(cert_dir)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return cert_dir


@pytest.fixture
def mtls_server(certificates):
    """クライアント証明書を要求するサーバーを、テスト中だけ起動する。"""
    server = create_server(
        certfile=certificates / "server.crt",
        keyfile=certificates / "server.key",
        cafile=certificates / "ca.crt",
        host="127.0.0.1",
        port=0,
    )
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_connects_with_client_certificate_signed_by_trusted_ca(certificates, mtls_server):
    # クライアントはサーバーを検証し、自分の証明書と秘密鍵も接続に使う。
    body = get(
        mtls_server,
        cafile=certificates / "ca.crt",
        certfile=certificates / "client.crt",
        keyfile=certificates / "client.key",
    )

    assert body == "ローカル mTLS サーバーからの応答です。\n"


def test_rejects_connection_without_client_certificate(certificates, mtls_server):
    # HTTPS 版のクライアントは、サーバーを検証するが自分の証明書を提示しない。
    with pytest.raises((URLError, ssl.SSLError)) as error:
        get_without_client_certificate(mtls_server, cafile=certificates / "ca.crt")

    # TLS バージョンによって、証明書必須またはハンドシェイク失敗のアラートになる。
    # 単なる接続拒否やタイムアウトを、認証による拒否として扱わない。
    tls_error = error.value.reason if isinstance(error.value, URLError) else error.value
    assert isinstance(tls_error, ssl.SSLError)
    assert tls_error.reason in {"TLSV13_ALERT_CERTIFICATE_REQUIRED", "SSLV3_ALERT_HANDSHAKE_FAILURE"}


def test_rejects_client_certificate_signed_by_untrusted_ca(certificates, untrusted_certificates, mtls_server):
    # サーバーの検証用 CA は正常なまま、自分が提示する証明書の発行元だけを変える。
    with pytest.raises((URLError, ssl.SSLError)) as error:
        get(
            mtls_server,
            cafile=certificates / "ca.crt",
            certfile=untrusted_certificates / "client.crt",
            keyfile=untrusted_certificates / "client.key",
        )

    tls_error = error.value.reason if isinstance(error.value, URLError) else error.value
    assert isinstance(tls_error, ssl.SSLError)
    assert tls_error.reason == "TLSV1_ALERT_UNKNOWN_CA"
