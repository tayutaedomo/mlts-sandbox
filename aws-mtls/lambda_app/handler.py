from mangum import Mangum

from lambda_app.app import app

# Mangum が REST API の Lambda イベントを ASGI に変換して FastAPI を呼び出し、
# HTTP 応答を API Gateway 用の Lambda プロキシ形式へ戻す。
# このインスタンス自体が handler(event, context) として呼び出せる入口になる。
handler = Mangum(app)
