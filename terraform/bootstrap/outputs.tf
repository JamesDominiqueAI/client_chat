output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "aws_role_arn" {
  value = aws_iam_role.github_actions_deploy.arn
}

output "aws_role_name" {
  value = aws_iam_role.github_actions_deploy.name
}

output "terraform_state_bucket" {
  value = aws_s3_bucket.terraform_state.bucket
}

output "terraform_lock_table" {
  value = aws_dynamodb_table.terraform_locks.name
}

output "github_repository" {
  value = var.github_repository
}
