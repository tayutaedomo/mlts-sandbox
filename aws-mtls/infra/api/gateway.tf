locals {
  stage_name = "poc"
  # ルートと、それ以外のパスを同じ設定で Lambda へ転送する。
  api_resources = {
    root  = aws_api_gateway_rest_api.api.root_resource_id
    proxy = aws_api_gateway_resource.proxy.id
  }
}

resource "aws_api_gateway_rest_api" "api" {
  name = "mtls-poc"

  # mTLS はカスタムドメインに設定するため、既定 URL からの迂回を防ぐ。
  disable_execute_api_endpoint = true
  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "request" {
  for_each = local.api_resources

  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = each.value
  http_method = "ANY"
  # クライアント証明書の検証はカスタムドメインで行う。IAM 認証は追加しない。
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda" {
  for_each = local.api_resources

  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = each.value
  http_method = aws_api_gateway_method.request[each.key].http_method
  type        = "AWS_PROXY"
  # 利用者の HTTP メソッドにかかわらず、Lambda Invoke API 自体は POST で呼び出す。
  integration_http_method = "POST"
  uri                     = aws_lambda_function.app.invoke_arn
}

resource "aws_lambda_permission" "gateway" {
  statement_id  = "AllowApiGatewayPoc"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "apigateway.amazonaws.com"
  # この API の poc ステージに限定する。末尾は HTTP メソッドとパス。
  source_arn = "${aws_api_gateway_rest_api.api.execution_arn}/${local.stage_name}/*/*"
}

# デプロイは API 定義のスナップショット。メソッドや統合の変更時に作り直す。
resource "aws_api_gateway_deployment" "api" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  triggers = {
    redeployment = sha1(jsonencode({
      resources = local.api_resources
      methods = [for method in aws_api_gateway_method.request : {
        http_method = method.http_method
        auth        = method.authorization
      }]
      integrations = [for integration in aws_api_gateway_integration.lambda : {
        type   = integration.type
        method = integration.integration_http_method
        uri    = integration.uri
      }]
      disable_execute_api_endpoint = aws_api_gateway_rest_api.api.disable_execute_api_endpoint
    }))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "poc" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  deployment_id = aws_api_gateway_deployment.api.id
  stage_name    = local.stage_name

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    # 本文・秘密鍵・証明書の全文は記録せず、リクエストと証明書の識別情報を照合する。
    format = jsonencode({
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
    })
  }

  # AWS にロググループを自動作成させず、保持期間と削除を Terraform で管理する。
  depends_on = [aws_api_gateway_account.logs, aws_cloudwatch_log_group.api_execution]
}

resource "aws_api_gateway_method_settings" "logs" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  stage_name  = aws_api_gateway_stage.poc.stage_name
  method_path = "*/*"

  settings {
    logging_level      = "INFO"
    data_trace_enabled = false
  }
}

# クライアントが検証するサーバー証明書と、クライアントを検証する CA は別に指定する。
resource "aws_api_gateway_domain_name" "api" {
  domain_name              = var.domain_name
  regional_certificate_arn = var.certificate_arn
  security_policy          = "TLS_1_2"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
  mutual_tls_authentication {
    truststore_uri     = "s3://${aws_s3_object.truststore.bucket}/${aws_s3_object.truststore.key}"
    truststore_version = aws_s3_object.truststore.version_id
  }
}

# 空のベースパスにより、URL に /poc を付けずにアクセスする。
resource "aws_api_gateway_base_path_mapping" "api" {
  api_id      = aws_api_gateway_rest_api.api.id
  stage_name  = aws_api_gateway_stage.poc.stage_name
  domain_name = aws_api_gateway_domain_name.api.domain_name
  base_path   = ""

  depends_on = [aws_api_gateway_method_settings.logs, aws_lambda_permission.gateway]
}
