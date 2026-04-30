output "api_base_url" {
  value = aws_apigatewayv2_stage.default.invoke_url
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.frontend.id
}

output "frontend_bucket_name" {
  value = aws_s3_bucket.frontend.bucket
}

output "complaints_table_name" {
  value = aws_dynamodb_table.complaints.name
}

output "audit_table_name" {
  value = aws_dynamodb_table.audit.name
}
