# -----------------------------------------------------------------------------
# IMPORTANT: Add these NS records at your domain registrar for your subdomain
# -----------------------------------------------------------------------------

output "nameservers" {
  description = "Add these NS records at your domain registrar for 'go' subdomain"
  value       = aws_route53_zone.subdomain.name_servers
}

output "nameservers_instructions" {
  description = "Instructions for your domain registrar DNS setup"
  value       = <<-EOT
    At your domain registrar, create NS records for the 'go' subdomain:
    go  NS  ${join("\n    go  NS  ", aws_route53_zone.subdomain.name_servers)}
  EOT
}

output "api_endpoint" {
  description = "Base URL for the API Gateway"
  value       = aws_apigatewayv2_api.http_api.api_endpoint
}

output "shorten_endpoint" {
  description = "Endpoint to create short URLs"
  value       = "${aws_apigatewayv2_api.http_api.api_endpoint}/shorten"
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.urls.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.urls.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.shortener.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.shortener.arn
}

output "custom_domain" {
  description = "Custom domain for the URL shortener"
  value       = "https://${var.custom_domain}"
}

output "custom_domain_shorten_endpoint" {
  description = "Custom domain endpoint to create short URLs"
  value       = "https://${var.custom_domain}/shorten"
}

output "example_create_command" {
  description = "Example curl command to create a short URL"
  value       = "curl -X POST https://${var.custom_domain}/shorten -H 'Content-Type: application/json' -d '{\"url\": \"https://example.com\"}'"
}
