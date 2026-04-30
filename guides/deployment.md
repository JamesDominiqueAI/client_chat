# Deployment

The intended deployment shape is:

- Frontend: Vercel Next.js app
- Backend: Vercel Python/FastAPI service, AWS Lambda, or container service
- Dataset: bundled JSON for the capstone demo
- Future data layer: database or support-system API

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
- provision the data layer with Terraform in [terraform/README.md](/home/ragive/projects/client_chat/terraform/README.md)
- prefer `*_PARAM` env vars so Lambda reads secrets from SSM parameter names at runtime

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
