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
