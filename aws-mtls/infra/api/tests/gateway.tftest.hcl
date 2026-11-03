# 概要：mTLS の入口、Lambda への転送、ログと削除対象の設定を検証する。
# 方針：AWS をモックし、実ドメイン・証明書・認証情報を使わずに参照関係を確認する。
# ケース：Regional API、既定 URL の無効化、root/proxy の ANY 統合、ステージ限定の呼び出し権限、
#         TLS と Truststore の版、ルートへの割り当て、ログの保持期間・本文トレース無効化・出力項目。
# DNS、TLS 接続、実際のログ出力、削除の動作は AWS 上で別途確認する。
mock_provider "aws" {
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/mtls-poc-test" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:us-east-1:123456789012:log-group:mtls-poc-test" }
  }
  mock_resource "aws_api_gateway_rest_api" {
    defaults = {
      id               = "test-api"
      root_resource_id = "test-root"
      execution_arn    = "arn:aws:execute-api:us-east-1:123456789012:test-api"
    }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { id = "mtls-poc-truststore-test", arn = "arn:aws:s3:::mtls-poc-truststore-test" }
  }
  mock_resource "aws_s3_object" {
    defaults = { version_id = "test-version" }
  }
}

variables {
  lambda_package_path = "tests/lambda-package.txt"
  truststore_path     = "tests/truststore-ca.txt"
  domain_name         = "mtls-poc.example.com"
  certificate_arn     = "arn:aws:acm:us-east-1:123456789012:certificate/00000000-0000-0000-0000-000000000000"
}

run "gateway_settings" {
  command = apply

  assert {
    condition = (
      aws_api_gateway_rest_api.api.disable_execute_api_endpoint &&
      one(aws_api_gateway_rest_api.api.endpoint_configuration).types == tolist(["REGIONAL"])
    )
    error_message = "Regional API を使用し、mTLS を迂回する既定 URL を無効にしてください。"
  }
  assert {
    condition = (
      aws_api_gateway_resource.proxy.path_part == "{proxy+}" &&
      aws_api_gateway_resource.proxy.parent_id == aws_api_gateway_rest_api.api.root_resource_id &&
      aws_api_gateway_method.request["root"].resource_id == aws_api_gateway_rest_api.api.root_resource_id &&
      aws_api_gateway_method.request["proxy"].resource_id == aws_api_gateway_resource.proxy.id &&
      alltrue([for method in aws_api_gateway_method.request : method.http_method == "ANY" && method.authorization == "NONE"]) &&
      alltrue([for key, integration in aws_api_gateway_integration.lambda :
        integration.type == "AWS_PROXY" && integration.integration_http_method == "POST" &&
        integration.http_method == aws_api_gateway_method.request[key].http_method &&
        integration.resource_id == aws_api_gateway_method.request[key].resource_id &&
        integration.uri == aws_lambda_function.app.invoke_arn
      ])
    )
    error_message = "root と proxy の全メソッドを Lambda プロキシ統合で転送してください。"
  }
  assert {
    condition = (
      aws_lambda_permission.gateway.principal == "apigateway.amazonaws.com" &&
      aws_lambda_permission.gateway.action == "lambda:InvokeFunction" &&
      aws_lambda_permission.gateway.function_name == aws_lambda_function.app.function_name &&
      aws_lambda_permission.gateway.source_arn == "${aws_api_gateway_rest_api.api.execution_arn}/poc/*/*"
    )
    error_message = "Lambda の呼び出し元を、この API の poc ステージに限定してください。"
  }
  assert {
    condition = (
      aws_api_gateway_domain_name.api.domain_name == var.domain_name &&
      aws_api_gateway_domain_name.api.regional_certificate_arn == var.certificate_arn &&
      aws_api_gateway_domain_name.api.security_policy == "TLS_1_2" &&
      one(aws_api_gateway_domain_name.api.endpoint_configuration).types == tolist(["REGIONAL"]) &&
      one(aws_api_gateway_domain_name.api.mutual_tls_authentication).truststore_uri == output.truststore_uri &&
      one(aws_api_gateway_domain_name.api.mutual_tls_authentication).truststore_version == "test-version" &&
      aws_api_gateway_base_path_mapping.api.base_path == "" &&
      aws_api_gateway_base_path_mapping.api.api_id == aws_api_gateway_rest_api.api.id &&
      aws_api_gateway_base_path_mapping.api.stage_name == "poc"
    )
    error_message = "mTLS のドメイン・証明書・Truststore の版と、ルートから poc への割り当てを設定してください。"
  }
  assert {
    condition = (
      aws_api_gateway_stage.poc.stage_name == "poc" &&
      aws_api_gateway_stage.poc.deployment_id == aws_api_gateway_deployment.api.id &&
      aws_cloudwatch_log_group.api_access.retention_in_days == 7 &&
      aws_cloudwatch_log_group.api_execution.retention_in_days == 7 &&
      aws_cloudwatch_log_group.api_execution.name == "API-Gateway-Execution-Logs_test-api/poc" &&
      one(aws_api_gateway_stage.poc.access_log_settings).destination_arn == aws_cloudwatch_log_group.api_access.arn &&
      aws_api_gateway_method_settings.logs.method_path == "*/*" &&
      one(aws_api_gateway_method_settings.logs.settings).logging_level == "INFO" &&
      !one(aws_api_gateway_method_settings.logs.settings).data_trace_enabled &&
      aws_api_gateway_account.logs.cloudwatch_role_arn == aws_iam_role.gateway_logs.arn
    )
    error_message = "アクセス・実行ログを事前作成し、本文トレースを無効にして7日保持してください。"
  }
  assert {
    condition = (
      jsondecode(aws_iam_role.gateway_logs.assume_role_policy).Statement[0].Principal.Service == "apigateway.amazonaws.com" &&
      aws_iam_role_policy_attachment.gateway_logs.role == aws_iam_role.gateway_logs.name &&
      aws_iam_role_policy_attachment.gateway_logs.policy_arn == "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
    )
    error_message = "API Gateway 用のログロールに、AWS 標準のログ用ポリシーを設定してください。"
  }
  assert {
    condition = (
      jsondecode(one(aws_api_gateway_stage.poc.access_log_settings).format) == {
        requestId            = "$context.requestId"
        extendedRequestId    = "$context.extendedRequestId"
        requestTime          = "$context.requestTime"
        path                 = "$context.path"
        httpMethod           = "$context.httpMethod"
        status               = "$context.status"
        errorResponseType    = "$context.error.responseType"
        integrationRequestId = "$context.integration.requestId"
        clientSubject        = "$context.identity.clientCert.subjectDN"
        clientIssuer         = "$context.identity.clientCert.issuerDN"
        clientSerial         = "$context.identity.clientCert.serialNumber"
        clientNotBefore      = "$context.identity.clientCert.validity.notBefore"
        clientNotAfter       = "$context.identity.clientCert.validity.notAfter"
      } &&
      output.api_url == "https://mtls-poc.example.com/" &&
      output.api_id == "test-api" && output.stage_name == "poc" &&
      output.api_dns_record.type == "CNAME" && output.api_dns_record.name == var.domain_name &&
      output.api_dns_record.value == aws_api_gateway_domain_name.api.regional_domain_name &&
      output.api_log_groups.access == aws_cloudwatch_log_group.api_access.name &&
      output.api_log_groups.execution == aws_cloudwatch_log_group.api_execution.name
    )
    error_message = "照合用のログ項目と、API・DNS・ログの参照情報を出力してください。"
  }
}
