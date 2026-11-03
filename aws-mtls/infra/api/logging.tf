# アクセスログは1リクエストの結果、実行ログは API Gateway 内部の処理を記録する。
resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/aws/apigateway/mtls-poc/access"
  retention_in_days = 7
}

# 標準実行ログ方式の名前は API-Gateway-Execution-Logs_{API ID}/{ステージ名} で固定。
# 任意の名前を使うには、CloudWatch Logs delivery で配信元・配信先・関連付けを追加する。
# この POC は mTLS とログの挙動を検証するため、標準方式を使用する。
# 規定名のグループをステージより先に作成し、保持期間と削除を Terraform で管理する。
# 方式の比較：https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-execution-logging.html
resource "aws_cloudwatch_log_group" "api_execution" {
  name              = "API-Gateway-Execution-Logs_${aws_api_gateway_rest_api.api.id}/${local.stage_name}"
  retention_in_days = 7
}

resource "aws_iam_role" "gateway_logs" {
  name_prefix = "mtls-poc-gateway-logs-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "apigateway.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# AWS が API Gateway のログ用に提供する標準ポリシー。
# このポリシーはロググループを限定せず、CloudWatch Logs の読み書きを許可する。
# ロールを引き受ける主体は、上の信頼ポリシーで API Gateway に限定する。
resource "aws_iam_role_policy_attachment" "gateway_logs" {
  role       = aws_iam_role.gateway_logs.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

# 共通設定の影響範囲
# ログ用ロールの参照は API 単位ではなく、同じアカウント・リージョン内で共有される。
# 各 API のログ出力先・ログレベルは、引き続き各ステージで設定する。
# 初回 apply 前に get-account で既存設定を確認し、別管理のロールがあれば適用しない。
#
# destroy 時の動作
# AWS プロバイダー v6 は共通のロール参照を未設定にする。以前の値を自動復元する動作ではない。
# この構成で作成した IAM ロールも削除するため、別の API が利用しているとログ出力に影響する。
# 削除前に他の API の依存を確認する。共有する場合は、共通設定とロールを POC と別に管理する。
resource "aws_api_gateway_account" "logs" {
  cloudwatch_role_arn = aws_iam_role.gateway_logs.arn

  depends_on = [aws_iam_role_policy_attachment.gateway_logs]
}
