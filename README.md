# mTLS sandbox

需給調整市場向け RA システムで使う、AC と RA 間の HTTPS クライアント証明書認証・mTLS を学習、検証するためのリポジトリです。

## ディレクトリ構成

```text
.
├── local-mtls/         # Python と OpenSSL によるローカル検証
│   ├── tls/            # 標準ライブラリによる HTTPS
│   ├── mtls/           # 標準ライブラリによる mTLS
│   ├── mtls_fastapi/   # FastAPI + Uvicorn による mTLS
│   ├── tests/          # 証明書検証のテスト
│   └── scripts/        # 証明書生成スクリプトと拡張設定
├── docs/
│   └── poc/     # POC の目的、検証内容、結果の記録
└── .github/     # CI、Dependabot、PR テンプレート
```

## ドキュメント

- [ローカル mTLS POC の検証記録](docs/poc/local-mtls.md)
- [ローカル環境のセットアップ・実行・テスト・Ruff の手順](local-mtls/README.md)
