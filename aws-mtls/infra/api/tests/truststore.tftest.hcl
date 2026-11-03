# 概要：Truststore の保存・更新・公開遮断・削除の設定を検証する。
# 方針：AWS をモックし、実際の証明書や秘密鍵を使わずに設定と参照関係を確認する。
# ケース：公開遮断と ACL 無効化、SSE-S3、バージョニング、HTTP 拒否、
#         CA ファイルの配置と更新検知、Truststore の参照情報、削除時の全バージョン整理。
# 実際の S3 のアクセス制御・配置内容・削除は AWS 上で別途確認する。
mock_provider "aws" {
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

  mock_resource "aws_s3_bucket" {
    defaults = {
      id     = "mtls-poc-truststore-test"
      bucket = "mtls-poc-truststore-test"
      arn    = "arn:aws:s3:::mtls-poc-truststore-test"
    }
  }

  mock_resource "aws_s3_object" {
    defaults = {
      version_id = "test-version"
    }
  }
}

variables {
  lambda_package_path = "tests/lambda-package.txt"
  truststore_path     = "tests/truststore-ca.txt"
}

run "truststore_settings" {
  command = apply

  assert {
    condition = (
      aws_s3_bucket_public_access_block.truststore.block_public_acls &&
      aws_s3_bucket_public_access_block.truststore.ignore_public_acls &&
      aws_s3_bucket_public_access_block.truststore.block_public_policy &&
      aws_s3_bucket_public_access_block.truststore.restrict_public_buckets &&
      one(aws_s3_bucket_ownership_controls.truststore.rule).object_ownership == "BucketOwnerEnforced"
    )
    error_message = "Truststore は公開アクセスと ACL を無効にしてください。"
  }

  assert {
    condition = (
      one(one(aws_s3_bucket_server_side_encryption_configuration.truststore.rule).apply_server_side_encryption_by_default).sse_algorithm == "AES256" &&
      aws_s3_object.truststore.server_side_encryption == "AES256"
    )
    error_message = "Truststore の保存時の暗号化には SSE-S3 を使用してください。"
  }

  assert {
    condition = (
      one(aws_s3_bucket_versioning.truststore.versioning_configuration).status == "Enabled" &&
      aws_s3_bucket.truststore.force_destroy
    )
    error_message = "Truststore はバージョンを保存し、検証用バケットの削除時には全バージョンを整理してください。"
  }

  assert {
    condition = jsondecode(aws_s3_bucket_policy.truststore.policy).Statement == [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = ["arn:aws:s3:::mtls-poc-truststore-test", "arn:aws:s3:::mtls-poc-truststore-test/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
    error_message = "Truststore のバケットとオブジェクトへの HTTP アクセスを拒否してください。"
  }

  assert {
    condition = (
      aws_s3_object.truststore.bucket == aws_s3_bucket.truststore.id &&
      aws_s3_object.truststore.key == "truststore.pem" &&
      aws_s3_object.truststore.source == var.truststore_path &&
      aws_s3_object.truststore.source_hash == filesha256(var.truststore_path)
    )
    error_message = "指定した CA ファイルを truststore.pem として配置し、内容の変更を検出してください。"
  }

  assert {
    condition = (
      output.truststore_bucket_name == "mtls-poc-truststore-test" &&
      output.truststore_uri == "s3://mtls-poc-truststore-test/truststore.pem" &&
      output.truststore_version_id == "test-version"
    )
    error_message = "Truststore のバケット名・URI・バージョンを参照できる必要があります。"
  }
}
