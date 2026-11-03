variable "lambda_package_path" {
  description = "Linux arm64 向け Lambda ZIP のパス"
  type        = string
  default     = "../../dist/lambda.zip"
  nullable    = false
}

variable "truststore_path" {
  description = "クライアント証明書の発行元として信頼する CA 証明書の PEM ファイル"
  type        = string
  default     = "../../certs/generated/ca.crt"
  nullable    = false
}

variable "domain_name" {
  description = "mTLS カスタムドメインの完全なホスト名"
  type        = string
  nullable    = false
}

variable "certificate_arn" {
  description = "同じリージョンで発行済みの ACM サーバー証明書の ARN"
  type        = string
  nullable    = false
}
