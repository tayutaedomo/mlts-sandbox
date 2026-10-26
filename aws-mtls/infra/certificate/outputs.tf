output "certificate_arn" {
  description = "発行状況の確認と API Gateway の設定に使う証明書 ARN"
  value       = aws_acm_certificate.server.arn
}

output "validation_records" {
  description = "外部 DNS に手動登録する所有確認用 CNAME"
  value = [
    for record in aws_acm_certificate.server.domain_validation_options : {
      name  = record.resource_record_name
      type  = record.resource_record_type
      value = record.resource_record_value
    }
  ]
}
