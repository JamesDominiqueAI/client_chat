# Terraform AWS Deployment

This stack provisions the AWS-native architecture:

- CloudFront
- S3 static frontend
- API Gateway HTTP API
- Lambda FastAPI app using Mangum
- DynamoDB complaints and audit tables
- SSM-style secret variables passed through Terraform variables
- CloudWatch logs via the Lambda execution role

## Deploy

1. Package the Lambda:

```bash
chmod +x scripts/aws/package_lambda.sh
./scripts/aws/package_lambda.sh
```

2. Build the static frontend:

```bash
cd frontend
NEXT_PUBLIC_API_URL="REPLACE_AFTER_TERRAFORM_APPLY" npm run build
```

3. Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars` and set values.

4. Apply Terraform:

```bash
cd terraform
terraform init
terraform apply
```

5. Rebuild the frontend with the `api_base_url` Terraform output, then upload `frontend/out` to the provisioned S3 bucket.

Or use the helper:

```bash
chmod +x scripts/aws/publish_frontend.sh
./scripts/aws/publish_frontend.sh
```

## Notes

- `STORE_BACKEND` is set to `dynamodb` in Lambda.
- Lambda reads manager password, auth secret, and Slack webhook from SSM parameter names injected by Terraform.
- SQLite remains available locally for development and tests.
- The backend allows CloudFront origins by default and can be tightened further with `CORS_ORIGINS`.
