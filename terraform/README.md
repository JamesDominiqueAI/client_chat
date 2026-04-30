# Terraform

The repository uses phased Terraform so each deployment concern can be applied and debugged independently.

Current phases:

- `bootstrap/`: one-time GitHub Actions IAM role plus Terraform remote-state resources.
- `1_foundation/`: shared provider/project foundation.
- `2_database/`: DynamoDB complaints and audit tables.
- `3_agents/`: reserved async-agent phase for future queue and worker expansion.
- `4_frontend/`: private S3 frontend bucket, CloudFront distribution, Lambda API, API Gateway, and SSM-backed runtime configuration.
- `5_enterprise/`: SNS alerts, CloudWatch dashboard, and operational monitoring.

The normal deployment path is:

```bash
bash scripts/bootstrap_github_actions.sh
```

Then:

```bash
bash scripts/deploy_aws.sh
```

That script packages the API, applies the needed Terraform layers, builds the frontend with the deployed API URL, uploads static assets, invalidates CloudFront, and applies monitoring.
