from fastapi import FastAPI

# FastAPI は HTTP のパス・メソッドと応答を定義する。
# TLS 接続や証明書検証は、このアプリでは処理しない。
app = FastAPI()


@app.get("/")
def hello() -> dict[str, str]:
    """イベント変換を確認するための、最小の JSON 応答を返す。"""
    return {"message": "Hello from Lambda"}
