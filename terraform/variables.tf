variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "customer-report-agent"
}

variable "frontend_bucket_name" {
  type = string
}

variable "lambda_zip_path" {
  type = string
}

variable "manager_password" {
  type      = string
  sensitive = true
}

variable "manager_auth_secret" {
  type      = string
  sensitive = true
}

variable "slack_webhook_url" {
  type      = string
  default   = ""
  sensitive = true
}
