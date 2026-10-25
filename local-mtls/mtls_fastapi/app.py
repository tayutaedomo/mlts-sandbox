from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

# FastAPI は URL と HTTP の応答を定義する。TLS の設定は server.py が担当する。
app = FastAPI()


@app.get("/", response_class=PlainTextResponse)
def hello() -> str:
    """標準ライブラリ版と同じ本文を返し、サーバー実装を比較できるようにする。"""
    # JSON 文字列ではなく、改行を含むプレーンテキストとして応答する。
    return "ローカル mTLS サーバーからの応答です。\n"
