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

The repo uses separate workflows, modeled after `digital_twin`:

- `.github/workflows/ci-cd.yml`: backend tests, frontend production build, static export build, Terraform formatting check
- `.github/workflows/deploy.yml`: automatic `development` deploy on `main` pushes plus manual `development` or `production` deployment
- `.github/workflows/destroy.yml`: manual environment destruction with typed confirmation

Required GitHub secrets and environment configuration:

- shared or repeated values
  - `DEFAULT_AWS_REGION`
  - `TERRAFORM_STATE_BUCKET`
  - `TERRAFORM_LOCK_TABLE`
- development environment
  - `AWS_ROLE_ARN`
  - `MANAGER_PASSWORD`
  - `MANAGER_AUTH_SECRET`
- production environment
  - `AWS_ROLE_ARN`
  - `MANAGER_PASSWORD`
  - `MANAGER_AUTH_SECRET`

Remote state matters here. The deploy and destroy workflows run on fresh GitHub-hosted runners, so Terraform state must live in S3 with DynamoDB locking instead of staying local to the runner.

Optional environment secrets:

- `SLACK_WEBHOOK_URL`
- `ALARM_EMAIL`

Project and table naming are derived from the environment:

- `development` -> `client-chat-dev`, `client-chat-dev-complaints`, `client-chat-dev-audit`
- `production` -> `client-chat`, `client-chat-complaints`, `client-chat-audit`

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
