# ローカル mTLS

Python 標準ライブラリと OpenSSL を使い、ローカルで TLS と mTLS の動作を学ぶための領域です。

## 目次

- [実行環境](#実行環境)
- [HTTPS の確認](#https-の確認)
- [コード整形と静的検査](#コード整形と静的検査)
- [検証記録](#検証記録)

## 実行環境

- Python 3.13 以上
- [uv](https://docs.astral.sh/uv/)
- OpenSSL

実行時に必要な外部ライブラリはありません。`pytest` と Ruff は開発用依存関係として `pyproject.toml` で管理します。

## HTTPS の確認

このディレクトリで実行します。

```sh
uv sync
sh scripts/generate-certs.sh
```

ターミナル1で HTTPS サーバーを起動します。`server.crt` と `server.key` はサーバーの身元を示します。

```sh
uv run python -m mtls_poc.server \
  --certfile certs/generated/server.crt \
  --keyfile certs/generated/server.key
```

ターミナル2から、CA 証明書を指定して接続します。クライアントは CA 署名と URL のホスト名の両方を検証します。

```sh
uv run python -m mtls_poc.client \
  --url https://127.0.0.1:8443/ \
  --cafile certs/generated/ca.crt
```

信頼した CA がサーバー証明書を発行していれば接続でき、別の CA では検証に失敗します。サーバー側はまだクライアント証明書を要求しません。この段階ではクライアントがサーバーを検証する片方向の TLS です。

テストは一時ディレクトリに別々の CA と証明書を生成し、ループバック接続で成功と検証失敗の両方を確認します。

```sh
uv run pytest
```

## コード整形と静的検査

Ruff でコードを整形し、構文や未使用変数、import の並び順を検査します。

```sh
uv run ruff format .
uv run ruff check .
```

整形せずに差分の有無だけ確認する場合は、次を実行します。

```sh
uv run ruff format --check .
```

証明書と秘密鍵は `certs/generated/` に生成され、Git の管理対象にはなりません。

## 検証記録

目的、構成、検証結果、次の検証項目は [ローカル mTLS POC の検証記録](../docs/poc/local-mtls.md) にまとめています。
