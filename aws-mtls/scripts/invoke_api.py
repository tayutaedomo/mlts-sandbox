import argparse
import sys
from urllib.parse import urlsplit

import requests


def main(argv: list[str] | None = None) -> int:
    """証明書の条件を変えて接続し、HTTP 応答と通信エラーを区別して表示する。"""
    parser = argparse.ArgumentParser(description="Requests で AWS の mTLS API を呼び出します")
    parser.add_argument("--url", required=True, help="接続先の HTTPS URL")
    parser.add_argument("--method", default="GET", type=str.upper, help="HTTP メソッド（既定: GET）")
    parser.add_argument("--certfile", help="クライアント証明書の PEM ファイル")
    parser.add_argument("--keyfile", help="クライアント秘密鍵の PEM ファイル")
    args = parser.parse_args(argv)

    if urlsplit(args.url).scheme != "https":
        parser.error("--url は https:// で指定してください")
    if (args.certfile is None) != (args.keyfile is None):
        parser.error("--certfile と --keyfile は両方を指定してください")

    # cert は自分の証明書、verify は相手の検証。公開 CA のサーバー証明書を通常どおり検証する。
    certificate = (args.certfile, args.keyfile) if args.certfile is not None else None
    try:
        # 元の接続先の結果を確認するため、リダイレクトを追跡しない。
        with requests.request(
            args.method, args.url, cert=certificate, verify=True, timeout=5, allow_redirects=False
        ) as response:
            print(f"HTTP {response.status_code}")
            for name in ("Content-Type", "x-amzn-RequestId", "x-amz-apigw-id"):
                if name in response.headers:
                    print(f"{name}: {response.headers[name]}")
            print()
            print(response.text)
            # 403 なども応答として表示する。TLS 拒否などの通信例外とは分けて扱う。
            return 0 if 200 <= response.status_code < 300 else 1
    except requests.RequestException as error:
        print(f"通信エラー ({type(error).__name__}): {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
