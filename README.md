# mTLS sandbox

需給調整市場向け RA システムで使う、AC と RA 間の HTTPS クライアント証明書認証・mTLS を学習、検証するためのリポジトリです。

## 目次

- [ディレクトリ構成](#ディレクトリ構成)
- [ドキュメント](#ドキュメント)
- [CI](#ci)

## ディレクトリ構成

```text
.
├── local-mtls/         # Python と OpenSSL によるローカル検証
│   ├── tls/            # HTTPS サーバーと urllib・Requests 版クライアント
│   ├── mtls/           # mTLS サーバーと urllib・Requests 版クライアント
│   ├── mtls_fastapi/   # FastAPI + Uvicorn による mTLS
│   ├── tests/          # 証明書検証のテスト
│   └── scripts/        # 証明書生成スクリプトと拡張設定
├── aws-mtls/           # Lambda イベント変換と AWS 基盤
│   ├── lambda_app/     # FastAPI アプリと Lambda ハンドラー
│   ├── infra/state/    # CloudFormation による Terraform state 用 S3
│   ├── scripts/        # Lambda 用 ZIP のビルド
│   └── tests/          # REST API イベントによる検証
├── docs/
│   ├── poc/     # POC の目的、検証内容、結果の記録
│   └── adr/     # 設計判断と採用理由
└── .github/     # CI、Dependabot、PR テンプレート
```

## ドキュメント

- [ローカル mTLS POC の検証記録](docs/poc/local-mtls.md)
- [ローカル環境のセットアップ・実行・テスト・Ruff の手順](local-mtls/README.md)
- [AWS 用 Lambda アプリの実行・検証手順](aws-mtls/README.md)
- [Terraform state 用 S3 の作成・設定確認・削除](aws-mtls/infra/state/README.md)
- [Lambda 用アプリのイベント変換の検証記録](docs/poc/aws-lambda.md)
- [AWS mTLS の構成と認証の流れ](docs/poc/aws-mtls.md)
- [Lambda の配布方式に ZIP を採用する](docs/adr/0001-lambda-zip-deployment.md)

## CI

[GitHub Actions](.github/workflows/ci.yml) は、PR 全体の差分と main への push に含まれる変更から、検査対象を判定します。

| 変更箇所 | 実行する検査 |
| --- | --- |
| `local-mtls/` | ローカル mTLS の pytest・Ruff |
| `aws-mtls/`（`infra/` を除く） | Lambda 用アプリの pytest・Ruff・ZIP ビルド |
| `aws-mtls/infra/state/` | CloudFormation の cfn-lint |
| `aws-mtls/pyproject.toml`・`uv.lock` | Lambda 用アプリと CloudFormation の両方 |
| `.github/workflows/` | 全検査 |
| Markdown 文書のみ | 変更範囲の判定だけを実行し、検査ジョブはスキップ |

手動実行（`workflow_dispatch`）では全検査を実行します。変更判定が失敗した場合も全検査を実行します。
