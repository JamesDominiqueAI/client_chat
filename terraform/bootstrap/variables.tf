variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_slug" {
  type    = string
  default = "client-chat"
}

variable "github_repository" {
  type    = string
  default = "JamesDominiqueAI/client_chat"
}

variable "github_actions_role_name" {
  type    = string
  default = "client-chat-github-actions"
}

variable "terraform_state_bucket_name" {
  type    = string
  default = null
}

variable "terraform_lock_table_name" {
  type    = string
  default = null
}

variable "existing_github_oidc_provider_arn" {
  type    = string
  default = null
}
