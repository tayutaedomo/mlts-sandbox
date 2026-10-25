# ローカル mTLS

Python 標準ライブラリと OpenSSL を使い、ローカルで TLS と mTLS の動作を学ぶための領域です。

## 目次

- [実行環境](#実行環境)
- [HTTPS の確認](#https-の確認)
  - [接続成功の確認](#接続成功の確認)
  - [証明書検証失敗の確認](#証明書検証失敗の確認)
  - [自動テスト](#自動テスト)
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

### 接続成功の確認

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

### 証明書検証失敗の確認

ターミナル1のサーバーを起動したまま、ターミナル2で別の CA を生成します。元の証明書を上書きしないよう、出力先を分けます。

```sh
sh scripts/generate-certs.sh certs/generated/untrusted
```

このスクリプトは別の CA とサーバー証明書一式を生成します。今回クライアントに指定するのは、そのうちの `ca.crt` だけです。稼働中のサーバーは元の証明書を使い続けます。

```sh
uv run python -m mtls_poc.client \
  --url https://127.0.0.1:8443/ \
  --cafile certs/generated/untrusted/ca.crt
```

`CERTIFICATE_VERIFY_FAILED` を含むエラーで終了することを確認します。`Connection refused` などはサーバーの起動状態や通信の問題で、今回確認する証明書検証の失敗とは異なります。

元の CA を指定すると、再び接続できます。

```sh
uv run python -m mtls_poc.client \
  --url https://127.0.0.1:8443/ \
  --cafile certs/generated/ca.crt
```

| クライアントの `--cafile` | 期待する結果 |
| --- | --- |
| `certs/generated/ca.crt` | 接続成功。応答本文を取得する |
| `certs/generated/untrusted/ca.crt` | 証明書検証に失敗する |

サーバーと接続先 URL を変えず、クライアントが信頼する CA だけを変えて結果を比較します。確認後はターミナル1で `Ctrl+C` を押してサーバーを停止します。

### 自動テスト

テストは一時ディレクトリに別々の CA と証明書を生成し、ループバック接続で成功と検証失敗の両方を確認します。

```sh
uv run pytest
```

証明書検証の失敗を期待するテストも、期待どおり接続が拒否されればテスト結果は成功になります。

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
