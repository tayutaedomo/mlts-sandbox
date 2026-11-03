# 概要：Lambda、実行ロール、ロググループの設定を検証する。
# 方針：AWS プロバイダーをモックし、apply の結果と入力ファイルのハッシュを確認する。
# ケース：実行環境・ZIP の更新検知・Lambda の信頼関係・ログの保存と権限。
# AWS での起動、実行権限、ログ出力、削除は実機で別途確認する。
mock_provider "aws" {
  mock_resource "aws_api_gateway_rest_api" {
    defaults = { execution_arn = "arn:aws:execute-api:us-east-1:123456789012:test-api" }
  }
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/mtls-poc-lambda"
    }
  }

  mock_resource "aws_cloudwatch_log_group" {
    defaults = {
      arn = "arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/mtls-poc"
    }
  }
}

variables {
  domain_name         = "mtls-poc.example.com"
  certificate_arn     = "arn:aws:acm:us-east-1:123456789012:certificate/00000000-0000-0000-0000-000000000000"
  lambda_package_path = "tests/lambda-package.txt"
  truststore_path     = "tests/truststore-ca.txt"
}

run "lambda_settings" {
  # モックで apply し、プロバイダーが返す ARN を参照する権限も確認する。
  command = apply

  assert {
    condition = (
      aws_lambda_function.app.runtime == "python3.14" &&
      aws_lambda_function.app.architectures == tolist(["arm64"]) &&
      aws_lambda_function.app.handler == "lambda_app.handler.handler" &&
      aws_lambda_function.app.memory_size == 256 && aws_lambda_function.app.timeout == 10
    )
    error_message = "Lambda の Python・CPU・ハンドラー・メモリ・タイムアウトが想定と異なります。"
  }

  assert {
    condition = (
      aws_lambda_function.app.filename == "tests/lambda-package.txt" &&
      aws_lambda_function.app.source_code_hash == filebase64sha256("tests/lambda-package.txt")
    )
    error_message = "入力した配布物とそのハッシュを Lambda に設定してください。"
  }

  assert {
    condition = (
      jsondecode(aws_iam_role.lambda.assume_role_policy).Statement[0].Principal.Service == "lambda.amazonaws.com" &&
      jsondecode(aws_iam_role.lambda.assume_role_policy).Statement[0].Action == "sts:AssumeRole"
    )
    error_message = "Lambda が実行ロールを引き受けられる必要があります。"
  }

  assert {
    condition = (
      aws_cloudwatch_log_group.lambda.name == "/aws/lambda/mtls-poc" &&
      aws_cloudwatch_log_group.lambda.retention_in_days == 7 &&
      one(aws_lambda_function.app.logging_config).log_group == aws_cloudwatch_log_group.lambda.name
    )
    error_message = "Lambda のロググループと保持期間を明示してください。"
  }

  assert {
    condition = (
      toset(jsondecode(aws_iam_role_policy.lambda_logs.policy).Statement[0].Action) ==
      toset(["logs:CreateLogStream", "logs:PutLogEvents"]) &&
      jsondecode(aws_iam_role_policy.lambda_logs.policy).Statement[0].Resource ==
      "arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/mtls-poc:*"
    )
    error_message = "実行ロールのログ権限は対象ロググループに限定してください。"
  }
}
