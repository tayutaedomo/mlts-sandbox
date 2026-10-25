"""Lambda ハンドラーのイベント変換と HTTP 応答を検証する。

概要:
    API Gateway REST API のイベントを入力し、FastAPI の応答が
    Lambda プロキシ形式で返ることを確認する。

方針:
    - 手動確認と同じ JSON サンプルをテストごとに読み直し、ケース間の変更を分離する。
    - 実際の Mangum ハンドラーを呼び出し、イベント変換をモックしない。
    - context を参照しないアプリのため None を渡し、AWS 接続・TLS 検証は行わない。

テストケース一覧:
    - GET /: 200、JSON の Content-Type・本文、Base64 フラグ false。
    - GET /missing: 404 と JSON エラー本文、Base64 フラグ false。
    - POST /: 405 と JSON エラー本文、許可メソッド GET、Base64 フラグ false。
    - 連続呼び出し: 同じハンドラーが、どちらの呼び出しでも正常応答を返す。
"""

import json
from pathlib import Path

import pytest

from lambda_app.handler import handler

EVENT_FILE = Path(__file__).parent / "events" / "get-root.json"


@pytest.fixture
def event():
    """手動確認と同じ REST API イベントを、テストごとに読み直す。"""
    return json.loads(EVENT_FILE.read_text(encoding="utf-8"))


def assert_hello_response(response):
    # FastAPI の応答が Lambda プロキシ形式に変換されたことを確認する。
    assert response["statusCode"] == 200
    assert response["headers"]["content-type"].split(";")[0] == "application/json"
    assert json.loads(response["body"]) == {"message": "Hello from Lambda"}
    assert response["isBase64Encoded"] is False


def test_returns_json_for_get_root(event):
    # 今回のアプリは Lambda context を使わないため、直接呼び出す際は None を渡せる。
    assert_hello_response(handler(event, None))


def test_returns_404_for_unknown_path(event):
    # API Gateway のプロキシリソースから未知のパスが届いた場合を再現する。
    event["resource"] = "/{proxy+}"
    event["path"] = "/missing"
    event["pathParameters"] = {"proxy": "missing"}
    event["requestContext"].update(path="/poc/missing", resourcePath="/{proxy+}")

    response = handler(event, None)

    assert response["statusCode"] == 404
    assert json.loads(response["body"]) == {"detail": "Not Found"}
    assert response["isBase64Encoded"] is False


def test_returns_405_for_post_root(event):
    event["httpMethod"] = "POST"
    event["requestContext"]["httpMethod"] = "POST"

    response = handler(event, None)

    assert response["statusCode"] == 405
    assert json.loads(response["body"]) == {"detail": "Method Not Allowed"}
    assert "GET" in response["headers"]["allow"]
    assert response["isBase64Encoded"] is False


def test_handles_repeated_invocations(event):
    # 同じアダプターを再利用し、連続した Lambda 呼び出しに対応できることを確認する。
    first = handler(event, None)
    second = handler(event, None)

    assert_hello_response(first)
    assert_hello_response(second)
