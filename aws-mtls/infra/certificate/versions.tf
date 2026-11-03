terraform {
  # S3 ネイティブロックは 1.10 以降、モックを使うテストは 1.7 以降で利用できる。
  required_version = ">= 1.10, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # バケット・リージョン・state キーは init 時に backend.hcl から渡す。
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
}
