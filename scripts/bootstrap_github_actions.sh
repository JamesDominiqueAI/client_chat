#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AWS_REGION="${DEFAULT_AWS_REGION:-us-east-1}"

echo "Bootstrapping GitHub Actions AWS resources in ${AWS_REGION}..."

terraform -chdir="$ROOT_DIR/terraform/bootstrap" init -input=false
terraform -chdir="$ROOT_DIR/terraform/bootstrap" apply -auto-approve \
  -var="aws_region=${AWS_REGION}"

AWS_ROLE_ARN="$(terraform -chdir="$ROOT_DIR/terraform/bootstrap" output -raw aws_role_arn)"
TERRAFORM_STATE_BUCKET="$(terraform -chdir="$ROOT_DIR/terraform/bootstrap" output -raw terraform_state_bucket)"
TERRAFORM_LOCK_TABLE="$(terraform -chdir="$ROOT_DIR/terraform/bootstrap" output -raw terraform_lock_table)"

echo
echo "Bootstrap complete."
echo "Set these in GitHub for both deployment environments:"
echo "AWS_ROLE_ARN=${AWS_ROLE_ARN}"
echo "DEFAULT_AWS_REGION=${AWS_REGION}"
echo "TERRAFORM_STATE_BUCKET=${TERRAFORM_STATE_BUCKET}"
echo "TERRAFORM_LOCK_TABLE=${TERRAFORM_LOCK_TABLE}"
