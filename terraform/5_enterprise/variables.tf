variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "customer-report-agent"
}

variable "lambda_function_name" {
  type = string
}

variable "alarm_email" {
  type    = string
  default = ""
}
