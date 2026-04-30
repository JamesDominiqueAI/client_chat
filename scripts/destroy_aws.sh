#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AWS_REGION="${DEFAULT_AWS_REGION:-us-east-1}"
DEPLOY_ENVIRONMENT="${DEPLOY_ENVIRONMENT:-${1:-development}}"
PROJECT_NAME="${PROJECT_NAME:-customer-report-agent}"
COMPLAINTS_TABLE_NAME="${COMPLAINTS_TABLE_NAME:-${PROJECT_NAME}-complaints}"
AUDIT_TABLE_NAME="${AUDIT_TABLE_NAME:-${PROJECT_NAME}-audit}"
TERRAFORM_STATE_BUCKET="${TERRAFORM_STATE_BUCKET:-}"
MANAGER_PASSWORD="${MANAGER_PASSWORD:-destroy-placeholder}"
MANAGER_AUTH_SECRET="${MANAGER_AUTH_SECRET:-destroy-placeholder-secret}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
ALARM_EMAIL="${ALARM_EMAIL:-}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

required_env=(
  TERRAFORM_STATE_BUCKET
)

for env_name in "${required_env[@]}"; do
  if [[ -z "${!env_name:-}" ]]; then
    echo "Missing required environment variable: ${env_name}" >&2
    exit 1
  fi
done

terraform_init() {
  local phase_dir="$1"

  terraform -chdir="$ROOT_DIR/$phase_dir" init -input=false -reconfigure \
    -backend-config="bucket=${TERRAFORM_STATE_BUCKET}" \
    -backend-config="key=${DEPLOY_ENVIRONMENT}/${phase_dir}/terraform.tfstate" \
    -backend-config="region=${AWS_REGION}" \
    -backend-config="use_lockfile=true" \
    -backend-config="encrypt=true"
}

ensure_lambda_zip() {
  local dist_dir="$ROOT_DIR/dist"
  local zip_path="$dist_dir/customer-report-agent-lambda.zip"

  if [[ -f "$zip_path" ]]; then
    return
  fi

  mkdir -p "$dist_dir"
  (
    cd "$dist_dir"
    printf 'placeholder\n' > placeholder.txt
    zip -q customer-report-agent-lambda.zip placeholder.txt
    rm -f placeholder.txt
  )
}

echo "Destroying ${PROJECT_NAME} (${DEPLOY_ENVIRONMENT}) in AWS region ${AWS_REGION}."

ensure_lambda_zip

terraform_init "terraform/4_frontend"
FRONTEND_BUCKET="$(terraform -chdir="$ROOT_DIR/terraform/4_frontend" output -raw frontend_bucket_name 2>/dev/null || true)"

if [[ -n "$FRONTEND_BUCKET" ]]; then
  echo "Emptying frontend bucket ${FRONTEND_BUCKET}..."
  aws s3 rm "s3://${FRONTEND_BUCKET}" --recursive || true
fi

echo "Destroying enterprise monitoring layer..."
terraform_init "terraform/5_enterprise"
terraform -chdir="$ROOT_DIR/terraform/5_enterprise" destroy -auto-approve \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}" \
  -var="lambda_function_name=${PROJECT_NAME}-api" \
  -var="alarm_email=${ALARM_EMAIL}"

echo "Destroying frontend/API layer..."
terraform_init "terraform/4_frontend"
COMPLAINTS_TABLE_ARN="arn:aws:dynamodb:${AWS_REGION}:000000000000:table/${COMPLAINTS_TABLE_NAME}"
AUDIT_TABLE_ARN="arn:aws:dynamodb:${AWS_REGION}:000000000000:table/${AUDIT_TABLE_NAME}"

terraform -chdir="$ROOT_DIR/terraform/4_frontend" destroy -auto-approve \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}" \
  -var="lambda_zip_path=${ROOT_DIR}/dist/customer-report-agent-lambda.zip" \
  -var="complaints_table_name=${COMPLAINTS_TABLE_NAME}" \
  -var="audit_table_name=${AUDIT_TABLE_NAME}" \
  -var="complaints_table_arn=${COMPLAINTS_TABLE_ARN}" \
  -var="audit_table_arn=${AUDIT_TABLE_ARN}" \
  -var="manager_password=${MANAGER_PASSWORD}" \
  -var="manager_auth_secret=${MANAGER_AUTH_SECRET}" \
  -var="slack_webhook_url=${SLACK_WEBHOOK_URL}"

echo "Destroying database layer..."
terraform_init "terraform/2_database"
terraform -chdir="$ROOT_DIR/terraform/2_database" destroy -auto-approve \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}" \
  -var="complaints_table_name=${COMPLAINTS_TABLE_NAME}" \
  -var="audit_table_name=${AUDIT_TABLE_NAME}"

echo "Destroying foundation layer..."
terraform_init "terraform/1_foundation"
terraform -chdir="$ROOT_DIR/terraform/1_foundation" destroy -auto-approve \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}"

echo
echo "Destroy complete."
