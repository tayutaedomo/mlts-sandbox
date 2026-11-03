# 認証とリージョンは AWS_PROFILE・AWS_REGION などの実行環境から読み込む。
provider "aws" {}

resource "aws_acm_certificate" "server" {
  domain_name       = var.domain_name
  validation_method = "DNS"
  key_algorithm     = "RSA_2048"

  # API Gateway に関連付ける証明書。秘密鍵のエクスポートは許可しない。
  options {
    export = "DISABLED"
  }

  # ドメイン変更時などは、新しい証明書を先に申請する。
  lifecycle {
    create_before_destroy = true
  }
}
