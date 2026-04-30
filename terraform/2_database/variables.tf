variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "customer-report-agent"
}

variable "complaints_table_name" {
  type = string
}

variable "audit_table_name" {
  type = string
}

variable "enable_point_in_time_recovery" {
  type    = bool
  default = true
}
