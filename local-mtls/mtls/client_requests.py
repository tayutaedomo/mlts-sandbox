import argparse
from pathlib import Path

import requests


def get(
    url: str,
    cafile: str | Path,
    certfile: str | Path | None = None,
    keyfile: str | Path | None = None,
) -> str:
    """CA でサーバーを検証し、指定した場合は自分の証明書も提示する。"""
    if (certfile is None) != (keyfile is None):
        raise ValueError("クライアント証明書と秘密鍵は両方を指定してください")

    # verify は相手のサーバーを検証する CA、cert は自分の証明書と秘密鍵。
    # 証明書なしの拒否を比較できるよう、両方省略した場合は提示しない。
    certificate = (str(certfile), str(keyfile)) if certfile is not None else None
    with requests.get(url, verify=str(cafile), cert=certificate, timeout=5) as response:
        # HTTP の 4xx・5xx は例外にする。TLS で拒否された場合は、ここまで到達しない。
        response.raise_for_status()
        return response.text


def main():
    parser = argparse.ArgumentParser(description="Requests でローカル mTLS サーバーへ接続します")
    parser.add_argument("--url", default="https://127.0.0.1:8444/", help="接続先 URL")
    parser.add_argument("--cafile", required=True, help="信頼する CA 証明書の PEM ファイル")
    parser.add_argument("--certfile", help="クライアント証明書の PEM ファイル（秘密鍵と同時に指定）")
    parser.add_argument("--keyfile", help="クライアント秘密鍵の PEM ファイル（証明書と同時に指定）")
    args = parser.parse_args()
    if (args.certfile is None) != (args.keyfile is None):
        parser.error("クライアント証明書と秘密鍵は両方を指定してください")
    print(get(args.url, args.cafile, args.certfile, args.keyfile), end="")


if __name__ == "__main__":
    main()
