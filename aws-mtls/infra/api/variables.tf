variable "lambda_package_path" {
  description = "Linux arm64 向け Lambda ZIP のパス"
  type        = string
  default     = "../../dist/lambda.zip"
  nullable    = false
}
