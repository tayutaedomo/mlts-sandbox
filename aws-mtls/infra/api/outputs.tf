output "lambda_function_name" {
  description = "Lambda の手動呼び出しとログの確認に使う関数名"
  value       = aws_lambda_function.app.function_name
}

output "lambda_function_arn" {
  description = "API Gateway との統合に使う Lambda の ARN"
  value       = aws_lambda_function.app.arn
}

output "truststore_bucket_name" {
  description = "Truststore の設定と配置内容の確認に使う S3 バケット名"
  value       = aws_s3_bucket.truststore.id
}

output "truststore_uri" {
  description = "API Gateway の mTLS 設定で参照する Truststore の S3 URI"
  value       = "s3://${aws_s3_object.truststore.bucket}/${aws_s3_object.truststore.key}"
}

output "truststore_version_id" {
  description = "API Gateway が参照する Truststore のオブジェクトバージョン"
  value       = aws_s3_object.truststore.version_id
}

output "api_url" {
  description = "mTLS カスタムドメインで接続する API の URL"
  value       = "https://${aws_api_gateway_domain_name.api.domain_name}/"
}

output "api_dns_record" {
  description = "外部 DNS に手動登録する API 接続用の CNAME"
  value = {
    name  = aws_api_gateway_domain_name.api.domain_name
    type  = "CNAME"
    value = aws_api_gateway_domain_name.api.regional_domain_name
  }
}

output "api_id" {
  description = "API 設定とログを確認する REST API の ID"
  value       = aws_api_gateway_rest_api.api.id
}

output "stage_name" {
  description = "API を配置するステージ名"
  value       = aws_api_gateway_stage.poc.stage_name
}

output "api_log_groups" {
  description = "API Gateway のアクセスログと実行ログのグループ名"
  value = {
    access    = aws_cloudwatch_log_group.api_access.name
    execution = aws_cloudwatch_log_group.api_execution.name
  }
}
