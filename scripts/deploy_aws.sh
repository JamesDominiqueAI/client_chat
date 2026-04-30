#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AWS_REGION="${DEFAULT_AWS_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-customer-report-agent}"
COMPLAINTS_TABLE_NAME="${COMPLAINTS_TABLE_NAME:-${PROJECT_NAME}-complaints}"
AUDIT_TABLE_NAME="${AUDIT_TABLE_NAME:-${PROJECT_NAME}-audit}"
ALARM_EMAIL="${ALARM_EMAIL:-}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

required_env=(
  MANAGER_PASSWORD
  MANAGER_AUTH_SECRET
)

for env_name in "${required_env[@]}"; do
  if [[ -z "${!env_name:-}" ]]; then
    echo "Missing required environment variable: ${env_name}" >&2
    exit 1
  fi
done

echo "Deploying ${PROJECT_NAME} to AWS region ${AWS_REGION}."

echo "Applying foundation layer..."
terraform -chdir="$ROOT_DIR/terraform/1_foundation" init -input=false
terraform -chdir="$ROOT_DIR/terraform/1_foundation" apply -auto-approve \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}"

echo "Packaging backend Lambda..."
"$ROOT_DIR/scripts/aws/package_lambda.sh" >/dev/null

echo "Applying database layer..."
terraform -chdir="$ROOT_DIR/terraform/2_database" init -input=false
terraform -chdir="$ROOT_DIR/terraform/2_database" apply -auto-approve \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}" \
  -var="complaints_table_name=${COMPLAINTS_TABLE_NAME}" \
  -var="audit_table_name=${AUDIT_TABLE_NAME}"

COMPLAINTS_TABLE_ARN="$(terraform -chdir="$ROOT_DIR/terraform/2_database" output -raw complaints_table_arn)"
AUDIT_TABLE_ARN="$(terraform -chdir="$ROOT_DIR/terraform/2_database" output -raw audit_table_arn)"

echo "Applying frontend/API layer..."
terraform -chdir="$ROOT_DIR/terraform/4_frontend" init -input=false
terraform -chdir="$ROOT_DIR/terraform/4_frontend" apply -auto-approve \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}" \
  -var="lambda_zip_path=${ROOT_DIR}/dist/customer-report-agent-lambda.zip" \
  -var="complaints_table_name=${COMPLAINTS_TABLE_NAME}" \
  -var="audit_table_name=${AUDIT_TABLE_NAME}" \
  -var="complaints_table_arn=${COMPLAINTS_TABLE_ARN}" \
  -var="audit_table_arn=${AUDIT_TABLE_ARN}" \
  -var="manager_password=${MANAGER_PASSWORD}" \
  -var="manager_auth_secret=${MANAGER_AUTH_SECRET}" \
  -var="slack_webhook_url=${SLACK_WEBHOOK_URL:-}"

API_BASE_URL="$(terraform -chdir="$ROOT_DIR/terraform/4_frontend" output -raw api_base_url)"
FRONTEND_BUCKET="$(terraform -chdir="$ROOT_DIR/terraform/4_frontend" output -raw frontend_bucket_name)"
CLOUDFRONT_DISTRIBUTION_ID="$(terraform -chdir="$ROOT_DIR/terraform/4_frontend" output -raw cloudfront_distribution_id)"
CLOUDFRONT_DOMAIN_NAME="$(terraform -chdir="$ROOT_DIR/terraform/4_frontend" output -raw cloudfront_domain_name)"

echo "Building and publishing frontend..."
(
  cd "$ROOT_DIR/frontend"
  STATIC_EXPORT=1 NEXT_PUBLIC_API_URL="$API_BASE_URL" npm run build:static
)
aws s3 sync "$ROOT_DIR/frontend/out/" "s3://${FRONTEND_BUCKET}" --delete
aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" --paths "/*" >/dev/null

echo "Applying enterprise monitoring layer..."
terraform -chdir="$ROOT_DIR/terraform/5_enterprise" init -input=false
terraform -chdir="$ROOT_DIR/terraform/5_enterprise" apply -auto-approve \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}" \
  -var="lambda_function_name=${PROJECT_NAME}-api" \
  -var="alarm_email=${ALARM_EMAIL}"

echo
echo "Deployment complete."
echo "Frontend: https://${CLOUDFRONT_DOMAIN_NAME}"
echo "API:      ${API_BASE_URL}"
