# AWS 用 Lambda アプリ

API Gateway REST API の Lambda イベントを、Mangum 経由で FastAPI に渡す学習例です。現在はローカルでイベント変換と応答生成を確認します。

## 目次

- [構成](#構成)
- [実行環境と準備](#実行環境と準備)
- [イベントからの呼び出し](#イベントからの呼び出し)
  - [確認の流れ](#確認の流れ)
  - [正常応答](#正常応答)
  - [HTTP エラー応答](#http-エラー応答)
- [自動テストと静的検査](#自動テストと静的検査)
- [検証の範囲](#検証の範囲)

## 構成

```text
.
├── lambda_app/
│   ├── __init__.py
│   ├── app.py                # FastAPI：HTTP のパス・メソッドと応答
│   └── handler.py            # Mangum：Lambda イベントと ASGI の変換
├── tests/
│   ├── events/get-root.json  # 手動確認とテストで共用する REST API イベント
│   └── test_handler.py
├── pyproject.toml
└── uv.lock
```

- Lambda の入口：`lambda_app.handler.handler(event, context)`。
- `local-mtls/` から独立した uv プロジェクト。既存アプリの import は不要。

## 実行環境と準備

- Python 3.13
- [uv](https://docs.astral.sh/uv/)

以降は `aws-mtls/` で実行します。

```sh
uv sync --locked --dev --python 3.13
```

- 実行依存：FastAPI・Mangum。
- 開発依存：pytest・Ruff。
- ハンドラーを直接呼び出すため、Uvicorn・Docker・AWS 認証情報は不要。

## イベントからの呼び出し

### 確認の流れ

```mermaid
flowchart TD
    A["準備：依存関係を同期"] --> B["サンプルの REST API イベントを読む"]
    subgraph cases["イベントのパス・メソッドを変えて比較"]
        C["GET / → 200 と JSON 本文"]
        D["GET /missing → 404"]
        E["POST / → 405"]
    end
    B --> C
    B --> D
    B --> E
    C --> F["Lambda プロキシ形式の応答を確認"]
    D --> F
    E --> F
```

- HTTP サーバーへの接続ではなく、Python 関数としてイベントを渡す。
- サンプルのホスト・識別子・IP は架空の値。
- `context` はこのアプリで参照しないため、ローカル確認では `None` を渡す。

### 正常応答

テストと同じ JSON ファイルを読み、実際の Mangum ハンドラーを呼び出します。

```sh
uv run --locked python - <<'PY'
import json
from pathlib import Path

from lambda_app.handler import handler

event = json.loads(Path("tests/events/get-root.json").read_text(encoding="utf-8"))
response = handler(event, None)
print(json.dumps(response, ensure_ascii=False, indent=2))
PY
```

| 応答フィールド | 期待する値・意味 |
| --- | --- |
| `statusCode` | `200` |
| `headers.content-type` | `application/json` |
| `body` | JSON 文字列 `{"message":"Hello from Lambda"}` |
| `isBase64Encoded` | `false`：本文は Base64 エンコードされていない |

- 外側の応答は Lambda プロキシ形式の辞書。
- `body` は文字列。JSON の値として読む場合は `json.loads(response["body"])` を使う。

### HTTP エラー応答

同じハンドラーに、パスとメソッドを変更したイベントを渡します。

```sh
uv run --locked python - <<'PY'
import json
from pathlib import Path

from lambda_app.handler import handler

for method, path in [("GET", "/missing"), ("POST", "/")]:
    event = json.loads(Path("tests/events/get-root.json").read_text(encoding="utf-8"))
    event["httpMethod"] = method
    event["path"] = path
    event["resource"] = "/{proxy+}" if path != "/" else "/"
    event["pathParameters"] = {"proxy": "missing"} if path != "/" else None
    event["requestContext"].update(
        httpMethod=method, path=f"/poc{path}", resourcePath=event["resource"]
    )
    response = handler(event, None)
    print(method, path, response["statusCode"], json.loads(response["body"]))
PY
```

| イベント | ステータス | 本文を JSON として読んだ値 |
| --- | --- | --- |
| `GET /missing` | `404` | `{"detail":"Not Found"}` |
| `POST /` | `405` | `{"detail":"Method Not Allowed"}` |

- FastAPI が HTTP エラーを生成し、Mangum が Lambda プロキシ形式に変換。
- ここでの 404・405 は HTTP の処理結果。証明書検証による接続拒否とは別のもの。

## 自動テストと静的検査

```sh
uv run --locked pytest
uv run --locked ruff format --check .
uv run --locked ruff check .
```

| ケース | 確認する内容 |
| --- | --- |
| `GET /` | ステータス・Content-Type・JSON 本文・Base64 フラグ |
| 未定義のパス | `404` と JSON エラー本文 |
| `POST /` | `405` と JSON エラー本文・許可メソッド |
| 同じハンドラーを連続呼び出し | どちらも正常応答を返す |

- イベント変換をモックせず、実際の Mangum を通して検証。
- 整形する場合は `uv run --locked ruff format .` を実行。

## 検証の範囲

| ローカルで確認できること | この構成で確認できないこと |
| --- | --- |
| REST API イベント → ASGI → Lambda 応答の変換 | 実際の API Gateway と Lambda の通信 |
| FastAPI の正常応答・HTTP エラー | TLS 接続・クライアント証明書の検証 |
| 同じハンドラーの連続呼び出し | 証明書拒否時の API Gateway のログ |

仕組みと役割は [Lambda 用アプリの POC 文書](../docs/poc/aws-lambda.md) を参照してください。
