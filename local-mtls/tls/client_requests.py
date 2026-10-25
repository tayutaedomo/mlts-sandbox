import argparse
from pathlib import Path

import requests


def get(url: str, cafile: str | Path) -> str:
    """指定した CA でサーバーを検証し、Requests で HTTPS GET する。"""
    # verify はサーバー証明書と接続先ホスト名の検証に使う CA を指定する。
    # mTLS 版と異なり、クライアント自身の証明書・秘密鍵は指定しない。
    with requests.get(url, verify=str(cafile), timeout=5) as response:
        # TLS の検証失敗とは別に、HTTP の 4xx・5xx も例外として返す。
        response.raise_for_status()
        return response.text


def main():
    parser = argparse.ArgumentParser(description="Requests でローカル HTTPS サーバーへ接続します")
    parser.add_argument("--url", default="https://127.0.0.1:8443/", help="接続先 URL")
    parser.add_argument("--cafile", required=True, help="信頼する CA 証明書の PEM ファイル")
    args = parser.parse_args()
    print(get(args.url, args.cafile), end="")


if __name__ == "__main__":
    main()
