import argparse
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class HelloHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # HTTPS 接続が成立した後、動作確認用の固定メッセージを返す。
        body = "ローカル HTTPS サーバーからの応答です。\n".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        # Content-Length は文字数ではなく、UTF-8 にした本文のバイト数を指定する。
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class HttpsServer(ThreadingHTTPServer):
    # 接続ごとに作られる処理スレッドが、サーバー終了を妨げないようにする。
    daemon_threads = True


def create_server(certfile: str | Path, keyfile: str | Path, host: str = "127.0.0.1", port: int = 8443) -> HttpsServer:
    """サーバー証明書を使う HTTPS サーバーを作る。クライアント証明書は要求しない。"""
    # HTTPServer が作る TCP ソケットに TLS を追加し、HTTPS として待ち受ける。
    server = HttpsServer((host, port), HelloHandler)

    # サーバー用の TLS 設定を作り、サーバー自身の証明書と秘密鍵を読み込む。
    # この段階ではクライアント証明書の検証を設定していない。
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))

    # server_side=True は、このソケットが TLS サーバー側であることを示す。
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def main():
    parser = argparse.ArgumentParser(description="ローカル HTTPS サーバーを起動します")
    parser.add_argument("--certfile", required=True, help="サーバー証明書の PEM ファイル")
    parser.add_argument("--keyfile", required=True, help="サーバー秘密鍵の PEM ファイル")
    parser.add_argument("--host", default="127.0.0.1", help="待ち受ける IP アドレス")
    parser.add_argument("--port", type=int, default=8443, help="待ち受けるポート番号")
    args = parser.parse_args()

    server = create_server(args.certfile, args.keyfile, args.host, args.port)
    print(f"https://{args.host}:{args.port}/ で HTTPS サーバーを起動しました（Ctrl+C で停止）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nHTTPS サーバーを停止します")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
