"""標準ライブラリ版の mTLS 接続とクライアント証明書の拒否を検証する。

概要:
    正常な証明書・証明書なし・非信頼 CA の証明書を使い、相互認証の結果を比較する。

方針:
    - ループバック上の実サーバーと、テスト用に生成した証明書を使う。
    - 実際の拒否後にクライアント例外を接続リセットへ置き換え、環境差も確実に通す。
    - サーバーの TLS 拒否理由・HTTP 未到達と、拒否前後の正常接続を確認する。

テストケース一覧:
    - 正常な証明書で応答を取得する。
    - 証明書なしの接続を、実際の例外と接続リセットの両方で確認する。
    - 非信頼 CA の証明書を、実際の例外と接続リセットの両方で確認する。
"""

import errno
import ssl
import subprocess
import threading
from pathlib import Path
from queue import Queue
from urllib.error import URLError

import pytest

from mtls.client import get
from mtls.server import HelloHandler, create_server
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


@pytest.fixture(params=["native", "connection_reset"])
def rejected_connection(request):
    """実際に接続を拒否された後、OS により異なるクライアントの見え方を再現する。"""

    def connect(client, *args, **kwargs):
        try:
            return client(*args, **kwargs)
        except (URLError, ssl.SSLError, ConnectionResetError) as error:
            cause = error.reason if isinstance(error, URLError) else error
            if (
                request.param == "connection_reset"
                and isinstance(cause, (ssl.SSLError, ConnectionResetError))
                and not isinstance(cause, ssl.SSLCertVerificationError)
            ):
                # 接続処理自体は実物を使い、拒否の通知形式だけを決定的に切り替える。
                raise URLError(ConnectionResetError(errno.ECONNRESET, "Connection reset by peer")) from error
            raise

    return connect


@pytest.fixture
def server_observations():
    """HTTP 到達と TLS エラーをテスト中だけ記録する。"""
    return {"requests": [], "tls_errors": Queue()}


@pytest.fixture
def mtls_server(certificates, monkeypatch, server_observations):
    """クライアント証明書を要求するサーバーを、テスト中だけ起動する。"""
    server = create_server(
        certfile=certificates / "server.crt",
        keyfile=certificates / "server.key",
        cafile=certificates / "ca.crt",
        host="127.0.0.1",
        port=0,
    )
    original_get_request = server.get_request
    original_do_get = HelloHandler.do_GET

    def track_handshake():
        try:
            return original_get_request()
        except ssl.SSLError as error:
            # HTTPServer は accept 中の TLS エラーを処理するため、ここで先に記録する。
            # 例外自体は保持せず、判定に必要な理由と検証コードだけを保存する。
            server_observations["tls_errors"].put((error.reason, getattr(error, "verify_code", None)))
            raise

    def track_http(handler):
        server_observations["requests"].append(handler.path)
        return original_do_get(handler)

    monkeypatch.setattr(server, "get_request", track_handshake)
    monkeypatch.setattr(HelloHandler, "do_GET", track_http)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive(), "mTLS サーバーが5秒以内に停止しませんでした"


@pytest.fixture
def trusted_connection(certificates, mtls_server):
    """拒否の前後で、サーバーが正常に応答できることを確認する。"""

    def connect():
        return get(
            mtls_server,
            cafile=certificates / "ca.crt",
            certfile=certificates / "client.crt",
            keyfile=certificates / "client.key",
        )

    return connect


def test_connects_with_client_certificate_signed_by_trusted_ca(trusted_connection, server_observations):
    assert trusted_connection() == "ローカル mTLS サーバーからの応答です。\n"
    assert server_observations["requests"] == ["/"]


def test_rejects_connection_without_client_certificate(
    certificates, mtls_server, rejected_connection, trusted_connection, server_observations
):
    assert trusted_connection() == "ローカル mTLS サーバーからの応答です。\n"
    # HTTPS 版のクライアントは、サーバーを検証するが自分の証明書を提示しない。
    with pytest.raises((URLError, ssl.SSLError, ConnectionResetError)) as error:
        rejected_connection(get_without_client_certificate, mtls_server, cafile=certificates / "ca.crt")

    # クライアント側では TLS アラートまたは接続リセットとして見える。
    cause = error.value.reason if isinstance(error.value, URLError) else error.value
    assert isinstance(cause, (ssl.SSLError, ConnectionResetError))
    assert not isinstance(cause, ssl.SSLCertVerificationError)
    if isinstance(cause, ssl.SSLError):
        assert cause.reason in {"TLSV13_ALERT_CERTIFICATE_REQUIRED", "SSLV3_ALERT_HANDSHAKE_FAILURE"}

    # 接続リセットだけで成功にせず、サーバーが証明書未提示を理由に拒否したことを照合する。
    reason, _ = server_observations["tls_errors"].get(timeout=5)
    assert reason == "PEER_DID_NOT_RETURN_A_CERTIFICATE"
    assert server_observations["requests"] == ["/"]
    assert trusted_connection() == "ローカル mTLS サーバーからの応答です。\n"
    assert server_observations["requests"] == ["/", "/"]


def test_rejects_client_certificate_signed_by_untrusted_ca(
    certificates, untrusted_certificates, mtls_server, rejected_connection, trusted_connection, server_observations
):
    assert trusted_connection() == "ローカル mTLS サーバーからの応答です。\n"
    # サーバーの検証用 CA は正常なまま、自分が提示する証明書の発行元だけを変える。
    with pytest.raises((URLError, ssl.SSLError, ConnectionResetError)) as error:
        rejected_connection(
            get,
            mtls_server,
            cafile=certificates / "ca.crt",
            certfile=untrusted_certificates / "client.crt",
            keyfile=untrusted_certificates / "client.key",
        )

    cause = error.value.reason if isinstance(error.value, URLError) else error.value
    assert isinstance(cause, (ssl.SSLError, ConnectionResetError))
    assert not isinstance(cause, ssl.SSLCertVerificationError)
    if isinstance(cause, ssl.SSLError):
        assert cause.reason == "TLSV1_ALERT_UNKNOWN_CA"

    # 実際の証明書検証エラーを確認し、HTTP 処理への到達や単なる通信障害と区別する。
    reason, verify_code = server_observations["tls_errors"].get(timeout=5)
    assert reason == "CERTIFICATE_VERIFY_FAILED"
    assert verify_code is not None and verify_code != 0
    assert server_observations["requests"] == ["/"]
    assert trusted_connection() == "ローカル mTLS サーバーからの応答です。\n"
    assert server_observations["requests"] == ["/", "/"]
