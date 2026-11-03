# Lambda のデプロイを Terraform で管理する

- Status: Accepted
- Date: 2026-11-03

## 目次

- [背景](#背景)
- [決定](#決定)
- [比較と採用理由](#比較と採用理由)
- [採用による影響](#採用による影響)
- [参考資料](#参考資料)

## 背景

Lambda アプリは、アプリ本体と依存パッケージを ZIP にまとめて配布する。Lambda の設定と ZIP のデプロイを Terraform でまとめて管理するか、デプロイを別の手段に任せるかを決める。

ZIP の採用理由は [ADR 0001：Lambda の配布方式に ZIP を採用する](0001-lambda-zip-deployment.md) を参照する。

## 決定

- Lambda の設定と ZIP のデプロイを Terraform で管理する。
- Terraform の実行前に、Lambda 用 ZIP をビルドする。
- ZIP のハッシュを使い、内容が変わった場合に Lambda のコードを更新する。

## 比較と採用理由

| 比較項目 | Terraform で管理（採用） | Terraform と分離して管理 |
| --- | --- | --- |
| Lambda の設定 | Terraform で管理 | Terraform で管理 |
| コード更新 | Terraform で ZIP を反映 | AWS CLI など、別の手段で ZIP を反映 |
| 初回作成 | アプリの ZIP を Terraform に渡す | 初期 ZIP を用意し、その後のコード更新を別の手段に任せる |
| 運用 | 構築とコード更新を Terraform にまとめる | アプリをインフラと独立して更新する |

| 観点 | Terraform で管理（採用） | Terraform と分離して管理 |
| --- | --- | --- |
| **利点** | • 設定変更とコード更新を同じ `plan`・`apply` で確認できる<br>• 別のデプロイ手順が不要 | • アプリをインフラと独立して更新できる<br>• アプリ更新の担当・権限をインフラ構築から分けやすい |
| **制約** | • Terraform の実行前に ZIP が必要<br>• アプリだけの更新でも Terraform の実行が必要 | • 初回 ZIP と、その後のデプロイ手順が必要<br>• 両者の管理範囲を分ける必要がある |

この POC では、AWS リソースを作成し、動作を確認した後に削除する。Lambda の構築とアプリの配置を同じ手順で確認できるため、Terraform で管理する。

どちらの方式も、手動または CI/CD から実行できる。

## 採用による影響

- アプリの変更時は ZIP を再ビルドし、Terraform で更新する。
- アプリのデプロイ頻度やチームの運用が変わった場合は、Terraform とデプロイ管理の分離を検討する。

## 参考資料

- [Terraform AWS provider：Lambda function](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function)
- [AWS：Lambda の ZIP デプロイ](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html)
