import argparse
import ssl
from pathlib import Path
from urllib.request import urlopen


def get(url: str, cafile: str | Path) -> str:
    """指定した CA を信頼して HTTPS GET を行い、本文を返す。"""
    # create_default_context は証明書検証と接続先ホスト名の検証を有効にする。
    # cafile で OS 標準の CA に加えて、この検証用 CA を信頼対象に指定する。
    context = ssl.create_default_context(cafile=str(cafile))

    # urlopen に SSLContext を渡すことで、この接続に使う検証条件を明示する。
    with urlopen(url, context=context, timeout=5) as response:
        return response.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="ローカル HTTPS サーバーへ接続します")
    parser.add_argument("--url", default="https://127.0.0.1:8443/", help="接続先 URL")
    parser.add_argument("--cafile", required=True, help="信頼する CA 証明書の PEM ファイル")
    args = parser.parse_args()
    print(get(args.url, args.cafile), end="")


if __name__ == "__main__":
    main()
