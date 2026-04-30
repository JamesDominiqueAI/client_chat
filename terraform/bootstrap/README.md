# Bootstrap Terraform

This stack creates the one-time AWS resources that GitHub Actions needs before the main phased deployment can work:

- GitHub Actions OIDC IAM role
- S3 bucket for Terraform remote state
- DynamoDB table for Terraform state locking

Run this stack locally with your existing AWS credentials. After it succeeds, copy the outputs into GitHub:

- `AWS_ROLE_ARN`
- `DEFAULT_AWS_REGION`
- `TERRAFORM_STATE_BUCKET`
- `TERRAFORM_LOCK_TABLE`

## Usage

```bash
cd terraform/bootstrap
terraform init
terraform apply
```

Or use the helper script from the repo root:

```bash
bash scripts/bootstrap_github_actions.sh
```

## Existing OIDC Provider

If your AWS account already has the GitHub OIDC provider, set `existing_github_oidc_provider_arn` in `terraform.tfvars` instead of creating another one.
