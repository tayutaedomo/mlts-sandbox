"""mTLS テストで使うサーバー側の HTTP 到達と TLS 拒否理由の観測。"""

import asyncio
import ssl
from queue import Queue

import pytest


@pytest.fixture
def server_observations():
    """クライアントの例外と照合するため、HTTP 到達と TLS 拒否理由を記録する。"""
    return {"requests": [], "tls_errors": Queue()}


@pytest.fixture
def run_uvicorn(server_observations):
    """テスト中だけ asyncio のハンドシェイク失敗を記録して Uvicorn を動かす。"""

    async def serve(server, sockets):
        loop = asyncio.get_running_loop()

        def record_error(loop, context):
            error = context.get("exception")
            if isinstance(error, ssl.SSLError):
                server_observations["tls_errors"].put((error.reason, getattr(error, "verify_code", None)))
            else:
                loop.default_exception_handler(context)

        loop.set_exception_handler(record_error)
        await server.serve(sockets=sockets)

    def run(server, sockets):
        # asyncio は debug 時にハンドシェイク失敗を例外ハンドラーへ通知する。
        asyncio.run(serve(server, sockets), debug=True)

    return run
