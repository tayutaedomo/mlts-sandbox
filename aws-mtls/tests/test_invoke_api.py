"""Requests クライアントの入力・表示・エラーの区別を検証する。

概要:
    HTTP 応答と通信エラーを区別し、証明書検証を有効にしたまま接続する。

方針:
    - HTTP 通信だけを置き換え、実際の CLI の引数解析と出力を確認する。
    - 実際の TLS 認証と API Gateway の拒否は、AWS への接続時に確認する。

テストケース一覧:
    - 接続: 証明書の有無とメソッドを渡し、ステータス・本文・照合用ヘッダーを表示する。
    - HTTP エラー: 403 の応答を表示し、通信エラーとは異なる終了コードを返す。
    - 通信エラー: TLS・接続・タイムアウトの例外を、種類とともに表示する。
    - 入力: 証明書と鍵の片方だけの指定、および HTTP の URL は接続前に拒否する。
"""

import pytest
import requests

from scripts.invoke_api import main

URL = "https://mtls-poc.example.com/"


@pytest.fixture
def response():
    result = requests.Response()
    result.status_code = 200
    result.headers.update(
        {"Content-Type": "application/json", "x-amzn-RequestId": "sample-request", "x-amz-apigw-id": "sample-gateway"}
    )
    result._content = b'{"message":"Hello from Lambda"}'
    result.encoding = "utf-8"
    return result


@pytest.mark.parametrize(
    ("arguments", "method", "certificate"),
    [
        ([], "GET", None),
        (
            ["--method", "POST", "--certfile", "client.crt", "--keyfile", "client.key"],
            "POST",
            ("client.crt", "client.key"),
        ),
    ],
)
def test_connects_with_verification_and_displays_response(
    monkeypatch, capsys, response, arguments, method, certificate
):
    def request(actual_method, url, **options):
        assert actual_method == method and url == URL
        assert options == {"cert": certificate, "verify": True, "timeout": 5, "allow_redirects": False}
        return response

    monkeypatch.setattr("scripts.invoke_api.requests.request", request)

    assert main(["--url", URL, *arguments]) == 0
    output = capsys.readouterr()
    assert "HTTP 200" in output.out
    assert "Content-Type: application/json" in output.out
    assert "x-amzn-RequestId: sample-request" in output.out
    assert "x-amz-apigw-id: sample-gateway" in output.out
    assert '{"message":"Hello from Lambda"}' in output.out
    assert output.err == ""


def test_displays_http_error_as_response(monkeypatch, capsys, response):
    response.status_code = 403
    response._content = b'{"message":"Forbidden"}'
    monkeypatch.setattr("scripts.invoke_api.requests.request", lambda *args, **kwargs: response)

    assert main(["--url", URL]) == 1
    output = capsys.readouterr()
    assert "HTTP 403" in output.out and '{"message":"Forbidden"}' in output.out
    assert output.err == ""


@pytest.mark.parametrize("error_type", [requests.exceptions.SSLError, requests.ConnectionError, requests.Timeout])
def test_displays_transport_error_separately(monkeypatch, capsys, error_type):
    def request(*args, **kwargs):
        raise error_type("接続できませんでした")

    monkeypatch.setattr("scripts.invoke_api.requests.request", request)

    assert main(["--url", URL]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert f"通信エラー ({error_type.__name__})" in output.err


@pytest.mark.parametrize(
    "arguments",
    [
        ["--url", URL, "--certfile", "client.crt"],
        ["--url", URL, "--keyfile", "client.key"],
        ["--url", "http://example.com/"],
    ],
)
def test_rejects_invalid_arguments_before_connecting(monkeypatch, arguments):
    def unexpected_request(*args, **kwargs):
        pytest.fail("入力不備のまま接続してはいけません")

    monkeypatch.setattr("scripts.invoke_api.requests.request", unexpected_request)

    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2
