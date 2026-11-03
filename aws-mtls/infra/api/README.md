# API Gateway による mTLS の AWS 基盤

API Gateway の mTLS カスタムドメインから、FastAPI + Mangum の Lambda アプリへ転送する構成を Terraform で管理します。S3 Truststore、実行ロール、API Gateway と Lambda の CloudWatch Logs も作成・削除します。

## 目次

- [構成と確認の流れ](#構成と確認の流れ)
- [準備](#準備)
- [作成](#作成)
- [API とログ設定の確認](#api-とログ設定の確認)
- [DNS の登録](#dns-の登録)
- [Truststore の設定と内容の確認](#truststore-の設定と内容の確認)
- [呼び出しとログの確認](#呼び出しとログの確認)
- [削除](#削除)
- [ローカルの検証](#ローカルの検証)

## 構成と確認の流れ

```mermaid
flowchart TD
    A["ZIP・CA・ACM 証明書・state・AWS 認証を準備"] --> B["API Gateway の既存ログ設定を確認"]
    B --> C["terraform apply：差分を確認して構築"]
    C --> D["API・mTLS・ログ・Truststore の設定を確認"]
    D --> E["出力された CNAME を外部 DNS に登録"]
    E --> F["Requests でカスタムドメインへ接続"]
```

| 対象 | 設定・役割 |
| --- | --- |
| Lambda | `mtls-poc`、Python 3.14、arm64、メモリ256 MB、タイムアウト10秒 |
| 配布物 | `../../dist/lambda.zip`。内容のハッシュで ZIP の更新を検出 |
| ハンドラー | `lambda_app.handler.handler` |
| 実行ロール | Lambda から対象ロググループへの書き込みを許可 |
| ロググループ | `/aws/lambda/mtls-poc`、保持期間7日。Terraform が作成・削除 |
| REST API | Regional。`/` と `/{proxy+}` の `ANY` を Lambda プロキシ統合に転送 |
| カスタムドメイン | `TLS_1_2` と mTLS。既定の `execute-api` URL は無効 |
| ステージ | `poc`。空のベースパスに割り当て、URL にステージ名を付けず接続 |
| API のログ | アクセスログと実行ログを7日保持。実行ログは `INFO`、本文トレースは無効 |
| API のログ用ロール | AWS 管理ポリシー `AmazonAPIGatewayPushToCloudWatchLogs` を使用。ロググループを限定しない権限 |
| Truststore | state 用とは別の S3 バケットに、CA 証明書を `truststore.pem` として保存 |
| state | 既存の state 用 S3 の `api/terraform.tfstate`。証明書用とは別のキー |

Truststore のバケット名には `mtls-poc-truststore-` に一意な接尾辞を付けます。名前・S3 URI・オブジェクトのバージョンは Terraform の出力で取得します。

| Truststore の設定 | 役割 |
| --- | --- |
| Block Public Access | 公開アクセスを遮断する4設定を有効化 |
| ACL | `BucketOwnerEnforced` で無効化 |
| 保存時の暗号化 | SSE-S3（`AES256`）を使用 |
| 通信 | バケットとオブジェクトへの HTTP アクセスを拒否 |
| バージョニング | CA 証明書の更新前後を識別し、参照する版を指定可能にする |
| 削除 | `force_destroy = true`。バケット削除時に過去バージョンも削除 |

## 準備

- Terraform 1.10 以上、2.0 未満、AWS CLI と AWS 認証を用意します。
- [state 用 S3](../state/README.md) を作成し、S3・Lambda・IAM・CloudWatch Logs・API Gateway を操作できる権限を用意します。
- IAM ロールとポリシーの作成、および Lambda に実行ロールを渡す `iam:PassRole` が必要です。
- 動作確認には `lambda:InvokeFunction` と、CloudWatch Logs の読み取り権限も必要です。
- [クライアント証明書の生成手順](../../README.md#証明書の生成) で、検証用 CA 証明書を用意します。Truststore には CA 証明書だけを指定します。

| 入力変数 | 既定値（このディレクトリからの相対パス） |
| --- | --- |
| `domain_name` | なし。mTLS カスタムドメインのホスト名 |
| `certificate_arn` | なし。同じリージョンで発行済みの ACM 証明書 ARN |
| `lambda_package_path` | `../../dist/lambda.zip` |
| `truststore_path` | `../../certs/generated/ca.crt` |

[ACM 証明書の手順](../certificate/README.md)で証明書を発行し、`ISSUED` になっていることを確認します。`aws-mtls/infra/api/` で次を実行し、コピー先のドメイン名と証明書 ARN を実際の値に変更します。

```sh
cp terraform.tfvars.example terraform.tfvars
```

別の CA を使う場合は、同じ `terraform.tfvars` で `truststore_path` にその PEM ファイルを指定します。

`aws-mtls/` で ZIP を生成してから、Terraform のディレクトリに移動します。

```sh
sh scripts/build-lambda.sh
cd infra/api
```

使用する AWS リージョンと state 用 S3 の情報を用意し、backend 設定を生成します。state 基盤が別リージョンにある場合は、CloudFormation のコマンドにその `--region` を指定します。

```sh
export AWS_REGION="$(aws configure get region)"
test -n "$AWS_REGION"
aws sts get-caller-identity

STATE_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name mtls-poc-state \
  --query 'Stacks[0].Outputs[?OutputKey==`StateBucketName`].OutputValue | [0]' \
  --output text)
STATE_REGION=$(aws cloudformation describe-stacks \
  --stack-name mtls-poc-state \
  --query 'Stacks[0].Outputs[?OutputKey==`StateBucketRegion`].OutputValue | [0]' \
  --output text)

umask 077
cat > backend.hcl <<EOF
bucket = "$STATE_BUCKET"
region = "$STATE_REGION"
key    = "api/terraform.tfstate"
EOF
```

## 作成

以下は `aws-mtls/infra/api/` で実行します。

`aws_api_gateway_account` は、同じ AWS アカウント・リージョン内で共有する API Gateway のログ用 IAM ロール参照を管理します。ロールの変更は、同じ共通設定を使う他の API にも影響します。

| 設定 | 適用範囲 |
| --- | --- |
| ログ用 IAM ロールの参照 | アカウント・リージョン内で共有 |
| ログ出力先・ログレベル | 各 API のステージで指定 |

初回作成前に既存設定を確認します。別管理のロール ARN が表示された場合は適用せず、管理方法を整理してください。未設定の場合は、この構成で専用ロールを作成します。

```sh
aws apigateway get-account --query cloudwatchRoleArn --output text
```

未設定の場合は `None` が表示されます。この構成の適用後は、作成した専用ロールの ARN が表示されます。

```sh
terraform init -backend-config=backend.hcl
terraform fmt -check -recursive
terraform validate
```

次のコマンドで差分が表示されます。API Gateway・カスタムドメイン・Lambda・IAM・ログ・Truststore の変更内容を確認し、問題なければ `yes` を入力して適用します。

```sh
terraform apply
```

アプリを変更した場合は ZIP を再生成してから `terraform apply` を実行します。生成物のハッシュが変わると Lambda のコードが更新されます。Truststore も CA ファイルの内容のハッシュで変更を検出し、更新時に新しいオブジェクトバージョンを作成します。

| 出力 | 用途 |
| --- | --- |
| `api_url` | クライアントが接続する URL |
| `api_dns_record` | 外部 DNS に登録する CNAME の名前・種類・宛先 |
| `api_id`・`stage_name` | API とステージの設定確認 |
| `api_log_groups` | アクセスログと実行ログのグループ名 |
| `lambda_function_name` | Lambda の直接呼び出し |
| `lambda_function_arn` | Lambda を識別する ARN |
| `truststore_bucket_name` | S3 の設定と配置内容の確認 |
| `truststore_uri` | mTLS で参照する Truststore の S3 URI |
| `truststore_version_id` | 参照する CA 証明書のオブジェクトバージョン |

## API とログ設定の確認

```sh
API_ID=$(terraform output -raw api_id)
API_DOMAIN=$(terraform output -json api_dns_record | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')

aws apigateway get-rest-api --rest-api-id "$API_ID" \
  --query '{Endpoint:endpointConfiguration.types,DefaultEndpointDisabled:disableExecuteApiEndpoint}'
aws apigateway get-domain-name --domain-name "$API_DOMAIN" \
  --query '{Status:domainNameStatus,TLS:securityPolicy,MutualTLS:mutualTlsAuthentication}'
aws apigateway get-base-path-mappings --domain-name "$API_DOMAIN"
aws apigateway get-stage --rest-api-id "$API_ID" --stage-name poc \
  --query '{Deployment:deploymentId,AccessLog:accessLogSettings,Methods:methodSettings}'
terraform output api_log_groups
```

| 確認対象 | 期待する設定 |
| --- | --- |
| API | `REGIONAL`、`DefaultEndpointDisabled = true` |
| カスタムドメイン | `AVAILABLE`、`TLS_1_2`、Truststore の URI・バージョンが Terraform の出力と一致 |
| Truststore の警告 | `truststoreWarnings` が空、または項目なし |
| ベースパス | ルートを表す `(none)` が、この API の `poc` ステージに対応 |
| アクセスログ | 作成したアクセスロググループと JSON 形式が設定されている |
| 実行ログ | `*/*` で `loggingLevel = INFO`、`dataTraceEnabled = false` |

## DNS の登録

```sh
terraform output api_dns_record
```

出力の `name`・`type`・`value` を使い、外部 DNS に API 接続用の CNAME を登録します。ドメイン部分や末尾の `.` を自動補完する入力欄では、その画面の仕様に合わせ、確認画面の完全な名前と宛先を照合します。

- API 接続用 CNAME は、ACM の所有確認用 CNAME と別のレコードです。所有確認用は維持します。
- 空のベースパスにより、接続 URL に `/poc` を付ける必要はありません。
- 接続には [Requests クライアント](../../README.md#requests-クライアント)と、Truststore が信頼する CA のクライアント証明書を使います。

## Truststore の設定と内容の確認

Terraform の出力から対象を取得し、S3 の設定を確認します。

```sh
TRUSTSTORE_BUCKET=$(terraform output -raw truststore_bucket_name)
TRUSTSTORE_VERSION=$(terraform output -raw truststore_version_id)

aws s3api get-public-access-block --bucket "$TRUSTSTORE_BUCKET"
aws s3api get-bucket-ownership-controls --bucket "$TRUSTSTORE_BUCKET"
aws s3api get-bucket-encryption --bucket "$TRUSTSTORE_BUCKET"
aws s3api get-bucket-versioning --bucket "$TRUSTSTORE_BUCKET"
aws s3api get-bucket-policy --bucket "$TRUSTSTORE_BUCKET" --query Policy --output text
aws s3api head-object \
  --bucket "$TRUSTSTORE_BUCKET" --key truststore.pem \
  --version-id "$TRUSTSTORE_VERSION" \
  --query '{VersionId:VersionId,Encryption:ServerSideEncryption}'
```

各設定が「構成と確認の流れ」の表と一致し、オブジェクトのバージョンが出力値と一致することを確認します。

配置したファイルを取得し、元の CA 証明書と比較します。以下は既定の `truststore_path` を使う場合の例です。入力を変更した場合は、`cmp` の比較元も同じファイルに変更します。

```sh
TRUSTSTORE_COPY=$(mktemp)
aws s3api get-object \
  --bucket "$TRUSTSTORE_BUCKET" --key truststore.pem \
  --version-id "$TRUSTSTORE_VERSION" "$TRUSTSTORE_COPY"
cmp ../../certs/generated/ca.crt "$TRUSTSTORE_COPY"
openssl x509 -in "$TRUSTSTORE_COPY" -noout -subject -issuer
rm "$TRUSTSTORE_COPY"
```

`cmp` が出力なし・終了コード `0` で終了すれば内容は一致しています。Truststore の証明書チェーンとバージョン指定の仕様は [API Gateway の mTLS](https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-mutual-tls.html) を参照してください。

## 呼び出しとログの確認

REST API のサンプルイベントを Lambda に直接渡します。

```sh
LAMBDA_RESPONSE=$(mktemp)
aws lambda invoke \
  --function-name "$(terraform output -raw lambda_function_name)" \
  --payload fileb://../../tests/events/get-root.json \
  "$LAMBDA_RESPONSE"
cat "$LAMBDA_RESPONSE"
rm "$LAMBDA_RESPONSE"
```

CLI に表示される呼び出し結果と、ファイルに保存されるアプリの応答を確認します。

| 確認対象 | 期待する値・意味 |
| --- | --- |
| CLI の `StatusCode` | `200`。Lambda の同期呼び出しが成功 |
| CLI の `FunctionError` | 項目がない。関数実行でエラーが発生していない |
| 応答の `statusCode` | `200`。FastAPI の正常応答 |
| 応答の `body` | JSON 文字列 `{"message":"Hello from Lambda"}` |

`StatusCode = 200` だけでは、関数実行やアプリの処理が成功したとは判断できません。呼び出し結果の仕様は [AWS CLI の invoke](https://docs.aws.amazon.com/cli/latest/reference/lambda/invoke.html) を参照してください。

```sh
aws logs tail /aws/lambda/mtls-poc --since 10m
```

Lambda の実行ログを確認します。API Gateway を経由する mTLS 通信は、この直接呼び出しでは検証しません。

## 削除

削除前に、同じアカウント・リージョン内で、このログ用ロールを使う他の API がないことを確認します。共有している場合は、共通設定とロールを POC とは別の基盤として管理してから、POC を削除してください。

次のコマンドで削除対象が表示されます。対象を確認し、問題なければ `yes` を入力して削除します。

```sh
terraform destroy
terraform state list
```

API Gateway・カスタムドメイン・Lambda・IAM・ロググループ・Truststore の削除と、state が空になったことを確認します。Truststore バケットの `force_destroy` により、過去バージョンや削除マーカーを含む全オブジェクトも削除されます。この削除は取り消せません。仕様は [Terraform の S3 バケット](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket) を参照してください。

| 対象 | destroy 時の動作 |
| --- | --- |
| 共通の `cloudWatchRoleArn` | AWS プロバイダー v6 が参照を解除し、未設定にする |
| この構成で作成したログ用 IAM ロール | ポリシーの関連付けとロールを削除する |
| 他の API と、そのロググループ | この構成の管理対象外。ただし、共通ロールを使う API のログ出力には影響する |

共通設定は、以前の値を自動復元する仕組みではありません。未設定から作成し、他の API が依存していなければ、destroy 後は適用前と同じ未設定の状態になります。削除動作の仕様は [AWS プロバイダー v6 の変更点](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/guides/version-6-upgrade#resource-aws_api_gateway_account) を参照してください。

外部 DNS の API 接続用 CNAME は手動で削除します。

state 用 S3 は別の CloudFormation スタックで管理しています。整理する手順は [state 基盤の削除](../state/README.md#削除) を参照してください。

## ローカルの検証

実環境の backend で初期化したディレクトリとは別のコピーで実行します。AWS 認証と実際の ZIP は不要です。初期化時には Terraform Registry への接続が必要です。

```sh
terraform init -backend=false -input=false -lockfile=readonly
terraform fmt -check -recursive
terraform validate
terraform test
```

テストはモックとテスト用のファイルを使い、Lambda の実行設定・ロール・ログ権限と、Truststore の保護・版管理・配置、API の転送・mTLS・呼び出し権限・ログ設定を確認します。AWS での実際の起動・ログ出力・S3 の設定と配置内容は、上記の手順で確認します。

プロバイダーの更新後は、開発環境の Mac arm64 と CI の Linux amd64 のハッシュを記録します。

```sh
terraform providers lock -platform=darwin_arm64 -platform=linux_amd64
```
