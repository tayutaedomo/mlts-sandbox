# 認証とリージョンは実行環境の AWS 設定から取得する。
provider "aws" {}

locals {
  function_name = "mtls-poc"
}

# Lambda が引き受ける実行ロール。名前には自動生成の接尾辞を付ける。
resource "aws_iam_role" "lambda" {
  name_prefix = "mtls-poc-lambda-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Lambda の初回実行前に作り、Terraform で保持期間と削除を管理する。
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = 7
}

# グループは事前に作成済みのため、実行ロールにはストリームへの書き込みだけを許可する。
resource "aws_iam_role_policy" "lambda_logs" {
  name = "lambda-logs"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "${aws_cloudwatch_log_group.lambda.arn}:*"
    }]
  })
}

resource "aws_lambda_function" "app" {
  function_name    = local.function_name
  role             = aws_iam_role.lambda.arn
  filename         = var.lambda_package_path
  source_code_hash = filebase64sha256(var.lambda_package_path)
  handler          = "lambda_app.handler.handler"
  runtime          = "python3.14"
  architectures    = ["arm64"]
  memory_size      = 256
  timeout          = 10

  # Lambda は作成済みのロググループへ出力する。
  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.lambda.name
  }

  # ロールの権限とロググループを先に用意し、初回実行に備える。
  depends_on = [aws_iam_role_policy.lambda_logs]
}
