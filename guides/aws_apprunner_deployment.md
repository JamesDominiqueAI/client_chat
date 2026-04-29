# AWS App Runner Deployment

This deployment path packages the existing Docker backend and frontend and deploys both services to AWS App Runner.

## Why App Runner

App Runner is the quickest AWS path for the current app because the repo already has Dockerfiles. It is good for a public demo deployment.

For a more production-grade AWS deployment, migrate SQLite to DynamoDB or RDS first.

## Prerequisites

- AWS CLI configured
- Docker running locally
- IAM permissions for ECR, IAM roles, and App Runner

If deployment fails with `AccessDeniedException`, attach the policy in:

```text
scripts/aws/required-deploy-policy.json
```

to the IAM user or role running the deployment. The current deploy script needs permission to create ECR repositories, push images, create/update App Runner services, and create/pass one App Runner ECR access role.

## Deploy

From the repo root:

```bash
chmod +x scripts/aws/deploy_apprunner.sh
MANAGER_PASSWORD="replace-this" \
MANAGER_AUTH_SECRET="replace-with-long-random-secret" \
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." \
./scripts/aws/deploy_apprunner.sh
```

`SLACK_WEBHOOK_URL` is optional. If omitted, Slack remains safely `not_configured`.

The script creates:

- ECR repository for backend image
- ECR repository for frontend image
- IAM role for App Runner ECR access
- App Runner backend service on port `8010`
- App Runner frontend service on port `3000`

## Important Limitation

The current backend uses SQLite. On App Runner, that works for a demo, but the filesystem is not the right long-term production database. Redeploys or scaling can lose local writes.

Production AWS upgrade:

- DynamoDB for complaints and audit events
- Secrets Manager or SSM Parameter Store for secrets
- CloudWatch dashboards for observability
- S3 upload flow for larger CSV imports
