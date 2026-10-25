import argparse
import ssl
from pathlib import Path

import uvicorn

from mtls_fastapi.app import app


def create_server(
    certfile: str | Path,
    keyfile: str | Path,
    cafile: str | Path,
    host: str = "127.0.0.1",
    port: int = 8445,
) -> uvicorn.Server:
    """FastAPI の手前で、Uvicorn が相互の証明書を使う TLS 接続を処理する。"""
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        # サーバー自身の証明書と、その証明書に対応する秘密鍵。
        ssl_certfile=str(certfile),
        ssl_keyfile=str(keyfile),
        # クライアント証明書の検証用 CA と、証明書提示を必須にする設定。
        # 検証を通過した接続だけが FastAPI の HTTP 処理へ進む。
        ssl_ca_certs=str(cafile),
        ssl_cert_reqs=ssl.CERT_REQUIRED,
        # 追加 extras に依存せず、単一プロセスで動作を追える構成にする。
        loop="asyncio",
        http="h11",
        workers=1,
        reload=False,
    )
    return uvicorn.Server(config)


def main():
    parser = argparse.ArgumentParser(description="FastAPI と Uvicorn でローカル mTLS サーバーを起動します")
    parser.add_argument("--certfile", required=True, help="サーバー証明書の PEM ファイル")
    parser.add_argument("--keyfile", required=True, help="サーバー秘密鍵の PEM ファイル")
    parser.add_argument("--client-ca", required=True, help="クライアント証明書を検証する CA 証明書の PEM ファイル")
    parser.add_argument("--host", default="127.0.0.1", help="待ち受ける IP アドレス")
    parser.add_argument("--port", type=int, default=8445, help="待ち受けるポート番号")
    args = parser.parse_args()

    server = create_server(args.certfile, args.keyfile, args.client_ca, args.host, args.port)
    # Uvicorn がポートの待ち受けと、Ctrl+C による停止処理を担当する。
    server.run()


if __name__ == "__main__":
    main()
