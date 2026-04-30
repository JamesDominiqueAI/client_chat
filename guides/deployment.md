# Deployment

The preferred AWS deployment shape is:

- Frontend: private S3 static export behind CloudFront
- Backend: AWS Lambda FastAPI app using Mangum behind API Gateway HTTP API
- Data: DynamoDB complaints and audit tables
- Secrets: SSM Parameter Store or Secrets Manager
- Monitoring: CloudWatch dashboard and SNS alarms through phased Terraform

## Environment Variables

Frontend:

```text
NEXT_PUBLIC_API_URL=https://your-backend.example.com
```

Backend:

```text
MANAGER_PASSWORD=replace-for-production
MANAGER_AUTH_SECRET=replace-with-a-long-random-secret
MANAGER_PASSWORD_PARAM=
MANAGER_AUTH_SECRET_PARAM=
CUSTOMER_REPORT_DB=data/customer_report_agent.db
STORE_BACKEND=sqlite
AWS_REGION=us-east-1
DYNAMODB_COMPLAINTS_TABLE=customer-report-agent-complaints
DYNAMODB_AUDIT_TABLE=customer-report-agent-audit
DYNAMODB_ENDPOINT_URL=
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_WEBHOOK_URL_PARAM=
CORS_ORIGINS=
CRM_WEBHOOK_URL=
TICKETING_WEBHOOK_URL=
STATUS_PAGE_URL=
EMAIL_WEBHOOK_URL=
```

`SLACK_WEBHOOK_URL` makes `external-slack-mcp` a real external connection. The other external MCP servers remain safe adapter stubs until their URLs are configured and their adapter functions are wired.

For the AWS-native deployment path:

- set `STORE_BACKEND=dynamodb`
- deploy the backend as Lambda through `backend/api/lambda_handler.py`
- use phased Terraform documented in [terraform/README.md](/home/ragive/projects/client_chat/terraform/README.md)
- prefer `*_PARAM` env vars so Lambda reads secrets from SSM parameter names at runtime
- use `bash scripts/deploy_aws.sh` as the normal deployment entrypoint
- use `.github/workflows/ci-cd.yml` for CI plus AWS dev/prod deployment orchestration

## GitHub Actions CI/CD

The repo uses a single workflow, modeled after `supplychain-ai`:

- `pull_request`: backend tests, frontend production build, static export build, Terraform formatting check
- `push` to `main`: automatic AWS deployment to the `development` GitHub environment
- `workflow_dispatch`: manual deployment to either `development` or `production`

Required GitHub secrets and environment configuration:

- shared or repeated values
  - `DEFAULT_AWS_REGION`
- development environment
  - `AWS_ROLE_ARN_DEV`
  - `PROJECT_NAME_DEV`
  - `COMPLAINTS_TABLE_NAME_DEV`
  - `AUDIT_TABLE_NAME_DEV`
  - `MANAGER_PASSWORD_DEV`
  - `MANAGER_AUTH_SECRET_DEV`
  - `SLACK_WEBHOOK_URL_DEV`
  - `ALARM_EMAIL_DEV`
  - `DEV_API_BASE_URL`
- production environment
  - `AWS_ROLE_ARN`
  - `PROJECT_NAME`
  - `COMPLAINTS_TABLE_NAME`
  - `AUDIT_TABLE_NAME`
  - `MANAGER_PASSWORD`
  - `MANAGER_AUTH_SECRET`
  - `SLACK_WEBHOOK_URL`
  - `ALARM_EMAIL`
  - `PROD_API_BASE_URL`

## Container Deployment

The repo includes:

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `docker-compose.yml`

Run:

```bash
docker compose up --build
```

Use this path for local production-like validation before deploying the frontend and backend separately.
