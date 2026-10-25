# mTLS sandbox

需給調整市場向け RA システムで使う、AC と RA 間の HTTPS クライアント証明書認証・mTLS を学習、検証するためのリポジトリです。

## ディレクトリ構成

```text
.
├── local-mtls/         # Python と OpenSSL によるローカル検証
│   ├── tls/            # HTTPS サーバーと urllib・Requests 版クライアント
│   ├── mtls/           # mTLS サーバーと urllib・Requests 版クライアント
│   ├── mtls_fastapi/   # FastAPI + Uvicorn による mTLS
│   ├── tests/          # 証明書検証のテスト
│   └── scripts/        # 証明書生成スクリプトと拡張設定
├── aws-mtls/           # FastAPI + Mangum の Lambda イベント変換
│   ├── lambda_app/     # FastAPI アプリと Lambda ハンドラー
│   └── tests/          # REST API イベントによる検証
├── docs/
│   └── poc/     # POC の目的、検証内容、結果の記録
└── .github/     # CI、Dependabot、PR テンプレート
```

## ドキュメント

- [ローカル mTLS POC の検証記録](docs/poc/local-mtls.md)
- [ローカル環境のセットアップ・実行・テスト・Ruff の手順](local-mtls/README.md)
- [AWS 用 Lambda アプリの実行・検証手順](aws-mtls/README.md)
- [Lambda 用アプリのイベント変換の検証記録](docs/poc/aws-lambda.md)
