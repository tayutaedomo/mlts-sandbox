# Truststore の仕組み
# S3 に Truststore 専用のモードはない。通常のバケットに、信頼する CA の証明書を保存する。
# API Gateway の mTLS 設定で、このファイルの S3 URI とバージョンを指定して使用する。
# CA 証明書には公開鍵が含まれる。秘密鍵の保管ではなく、信頼する CA の意図しない変更を防ぐことが重要。
# 以下では、一般的な S3 の保護設定、Truststore の版管理、POC の削除設定を定義する。

# state 用 S3 と用途・削除対象を分け、クライアント証明書の検証用 CA を保存する。
resource "aws_s3_bucket" "truststore" {
  bucket_prefix = "mtls-poc-truststore-"

  # POC の後片付け用の Terraform 設定。Truststore の要件やセキュリティ対策ではない。
  # バケット削除時に、過去バージョンと削除マーカーも含めて削除する。削除は取り消せない。
  force_destroy = true
}

# 一般的な保護：CA 証明書の配布用にバケットを公開する必要はない。
# 公開 ACL の新規設定を拒否・既存設定を無効化し、公開ポリシーの設定や公開アクセスも制限する。
resource "aws_s3_bucket_public_access_block" "truststore" {
  bucket = aws_s3_bucket.truststore.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# 一般的な保護：ACL による個別のアクセス許可を無効にし、IAM・バケットポリシーで制御する。
# 公開遮断や ACL 無効化だけでは、認証済みの主体の書き換えまでは防げない。書き込み権限も限定する。
resource "aws_s3_bucket_ownership_controls" "truststore" {
  bucket = aws_s3_bucket.truststore.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# 一般的な保護：S3 が管理する鍵で、保存するオブジェクトを暗号化する（SSE-S3）。
# 暗号化はアクセス制御とは別の対策であり、書き換えを防ぐための権限制御も必要。
resource "aws_s3_bucket_server_side_encryption_configuration" "truststore" {
  bucket = aws_s3_bucket.truststore.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Truststore の版管理：更新前の CA 証明書を保持し、API Gateway が参照する版を識別する。
# API Gateway のバージョン指定は任意だが、指定する場合は S3 のバージョニングが必要。
resource "aws_s3_bucket_versioning" "truststore" {
  bucket = aws_s3_bucket.truststore.id

  versioning_configuration {
    status = "Enabled"
  }
}

# 一般的な保護：バケットと全オブジェクトへの HTTP アクセスを拒否し、HTTPS を使用する。
# このポリシーはアクセス権を付与しない。読み書きを行う主体には、別途 IAM などの許可が必要。
resource "aws_s3_bucket_policy" "truststore" {
  bucket = aws_s3_bucket.truststore.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.truststore.arn, "${aws_s3_bucket.truststore.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

# Truststore の内容：信頼する発行元 CA からルート CA までの証明書チェーンを PEM 形式で配置する。
# この POC はルート CA が直接クライアント証明書を発行するため、配置する CA 証明書は1枚。
# 秘密鍵やクライアント証明書は Terraform に渡さない。
# truststore.pem は任意のファイル名。Content-Type の指定だけで Truststore になるわけではない。
resource "aws_s3_object" "truststore" {
  bucket                 = aws_s3_bucket.truststore.id
  key                    = "truststore.pem"
  source                 = var.truststore_path
  source_hash            = filesha256(var.truststore_path)
  content_type           = "application/x-pem-file"
  server_side_encryption = "AES256"

  # 初回アップロードからバージョンを取得し、保存時の暗号化も先に設定する。
  depends_on = [
    aws_s3_bucket_versioning.truststore,
    aws_s3_bucket_server_side_encryption_configuration.truststore,
  ]
}
