import ssl
import subprocess
import threading
from pathlib import Path
from urllib.error import URLError

import pytest

from tls.client import get
from tls.server import create_server

PROJECT_DIR = Path(__file__).resolve().parents[1]
CERT_SCRIPT = PROJECT_DIR / "scripts" / "generate-certs.sh"


@pytest.fixture(scope="session")
def certificates(tmp_path_factory):
    """テスト専用の信頼済み CA と、別の非信頼 CA を生成する。"""
    cert_root = tmp_path_factory.mktemp("certificates")
    trusted_dir = cert_root / "trusted"
    untrusted_dir = cert_root / "untrusted"

    # CA が異なる場合だけ接続結果が変わるよう、同じ生成スクリプトを別々に実行する。
    for cert_dir in (trusted_dir, untrusted_dir):
        subprocess.run(
            ["sh", str(CERT_SCRIPT), str(cert_dir)],
            check=True,
            capture_output=True,
            text=True,
        )

    return {"trusted": trusted_dir, "untrusted": untrusted_dir}


@pytest.fixture
def https_server(certificates):
    """テスト中だけ HTTPS サーバーを起動し、終了時に確実に閉じる。"""
    trusted_dir = certificates["trusted"]
    server = create_server(
        certfile=trusted_dir / "server.crt",
        keyfile=trusted_dir / "server.key",
        host="127.0.0.1",
        port=0,
    )
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    url = f"https://127.0.0.1:{server.server_port}/"

    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_connects_when_server_certificate_is_signed_by_trusted_ca(certificates, https_server):
    body = get(https_server, cafile=certificates["trusted"] / "ca.crt")

    assert body == "ローカル HTTPS サーバーからの応答です。\n"


def test_rejects_server_certificate_signed_by_untrusted_ca(certificates, https_server):
    # 接続拒否が単なる通信エラーではなく、証明書検証によるものと確認する。
    with pytest.raises(URLError) as error:
        get(https_server, cafile=certificates["untrusted"] / "ca.crt")

    assert isinstance(error.value.reason, ssl.SSLCertVerificationError)
