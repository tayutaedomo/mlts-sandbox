terraform {
  required_version = ">= 1.10, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # state 用 S3 を共有し、証明書とは異なるキーを init 時に指定する。
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
}
