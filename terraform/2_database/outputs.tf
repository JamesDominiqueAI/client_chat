output "complaints_table_name" {
  value = aws_dynamodb_table.complaints.name
}

output "audit_table_name" {
  value = aws_dynamodb_table.audit.name
}

output "complaints_table_arn" {
  value = aws_dynamodb_table.complaints.arn
}

output "audit_table_arn" {
  value = aws_dynamodb_table.audit.arn
}
