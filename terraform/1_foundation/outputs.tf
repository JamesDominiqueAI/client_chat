output "aws_region" {
  value = var.aws_region
}

output "project_name" {
  value = var.project_name
}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}
