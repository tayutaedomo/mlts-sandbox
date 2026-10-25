import argparse
import ssl
from pathlib import Path
from urllib.request import urlopen


def get(url: str, cafile: str | Path, certfile: str | Path, keyfile: str | Path) -> str:
    """サーバーを検証し、自分の証明書を提示して mTLS で GET する。"""
    # create_default_context は証明書検証と接続先ホスト名の検証を有効にする。
    # cafile はサーバー証明書の検証に使う CA で、自分の証明書とは役割が異なる。
    context = ssl.create_default_context(cafile=str(cafile))

    # クライアント自身の証明書と、その証明書に対応する秘密鍵を読み込む。
    # TLS では秘密鍵を送らず、鍵を持っていることを署名で証明する。
    context.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))

    # urlopen に SSLContext を渡すことで、この接続に使う検証条件を明示する。
    with urlopen(url, context=context, timeout=5) as response:
        return response.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="ローカル mTLS サーバーへ接続します")
    parser.add_argument("--url", default="https://127.0.0.1:8444/", help="接続先 URL")
    parser.add_argument("--cafile", required=True, help="信頼する CA 証明書の PEM ファイル")
    parser.add_argument("--certfile", required=True, help="クライアント証明書の PEM ファイル")
    parser.add_argument("--keyfile", required=True, help="クライアント秘密鍵の PEM ファイル")
    args = parser.parse_args()
    print(get(args.url, args.cafile, args.certfile, args.keyfile), end="")


if __name__ == "__main__":
    main()
