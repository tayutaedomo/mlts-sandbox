# 概要：外部 DNS で検証する ACM 証明書の申請設定を検証する。
# 方針：AWS プロバイダーをモック化し、plan の設定を確認する。AWS には接続しない。
# ケース：対象ドメイン、DNS 検証、RSA 鍵、エクスポート不可の設定。
# 証明書の実発行・DNS の伝播・IAM 権限は、README の実機手順で確認する。
mock_provider "aws" {}

variables {
  domain_name = "mtls-poc.example.com"
}

run "requests_non_exportable_dns_certificate" {
  command = plan

  assert {
    condition     = aws_acm_certificate.server.domain_name == "mtls-poc.example.com"
    error_message = "指定したドメインのサーバー証明書を申請する必要があります。"
  }

  assert {
    condition     = aws_acm_certificate.server.validation_method == "DNS"
    error_message = "外部 DNS で所有確認するため、DNS 検証を使用してください。"
  }

  assert {
    condition     = aws_acm_certificate.server.key_algorithm == "RSA_2048"
    error_message = "サーバー証明書の鍵は RSA 2048 bit を使用してください。"
  }

  assert {
    condition     = one(aws_acm_certificate.server.options).export == "DISABLED"
    error_message = "エクスポート不可の証明書を申請してください。"
  }
}
