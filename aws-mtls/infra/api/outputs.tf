output "lambda_function_name" {
  description = "Lambda の手動呼び出しとログの確認に使う関数名"
  value       = aws_lambda_function.app.function_name
}

output "lambda_function_arn" {
  description = "API Gateway との統合に使う Lambda の ARN"
  value       = aws_lambda_function.app.arn
}
