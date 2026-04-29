#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-$(aws configure get region)}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
PROJECT="${PROJECT:-customer-report-agent}"
TAG="${TAG:-latest}"

BACKEND_REPO="${PROJECT}-backend"
FRONTEND_REPO="${PROJECT}-frontend"
ROLE_NAME="${PROJECT}-apprunner-ecr-access"
BACKEND_SERVICE="${PROJECT}-backend"
FRONTEND_SERVICE="${PROJECT}-frontend"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "AWS account: $ACCOUNT_ID"
echo "AWS region:  $AWS_REGION"

ensure_repo() {
  local repo="$1"
  aws ecr describe-repositories --repository-names "$repo" --region "$AWS_REGION" >/dev/null 2>&1 ||
    aws ecr create-repository --repository-name "$repo" --region "$AWS_REGION" >/dev/null
}

ensure_role() {
  if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    aws iam create-role \
      --role-name "$ROLE_NAME" \
      --assume-role-policy-document "file://scripts/aws/apprunner-trust-policy.json" >/dev/null
    aws iam attach-role-policy \
      --role-name "$ROLE_NAME" \
      --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
    echo "Waiting for IAM role propagation..."
    sleep 12
  fi
  aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text
}

image_uri() {
  local repo="$1"
  echo "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${repo}:${TAG}"
}

create_or_update_service() {
  local service_name="$1"
  local image="$2"
  local port="$3"
  local access_role_arn="$4"
  local env_json="$5"

  local service_arn
  service_arn="$(aws apprunner list-services \
    --region "$AWS_REGION" \
    --query "ServiceSummaryList[?ServiceName=='${service_name}'].ServiceArn | [0]" \
    --output text)"

  local image_configuration
  image_configuration="{\"Port\":\"${port}\",\"RuntimeEnvironmentVariables\":${env_json}}"

  if [[ "$service_arn" == "None" || -z "$service_arn" ]]; then
    aws apprunner create-service \
      --region "$AWS_REGION" \
      --service-name "$service_name" \
      --source-configuration "{
        \"AuthenticationConfiguration\":{\"AccessRoleArn\":\"${access_role_arn}\"},
        \"AutoDeploymentsEnabled\":true,
        \"ImageRepository\":{
          \"ImageIdentifier\":\"${image}\",
          \"ImageRepositoryType\":\"ECR\",
          \"ImageConfiguration\":${image_configuration}
        }
      }" >/dev/null
  else
    aws apprunner update-service \
      --region "$AWS_REGION" \
      --service-arn "$service_arn" \
      --source-configuration "{
        \"AuthenticationConfiguration\":{\"AccessRoleArn\":\"${access_role_arn}\"},
        \"AutoDeploymentsEnabled\":true,
        \"ImageRepository\":{
          \"ImageIdentifier\":\"${image}\",
          \"ImageRepositoryType\":\"ECR\",
          \"ImageConfiguration\":${image_configuration}
        }
      }" >/dev/null
  fi
}

service_url() {
  local service_name="$1"
  aws apprunner list-services \
    --region "$AWS_REGION" \
    --query "ServiceSummaryList[?ServiceName=='${service_name}'].ServiceUrl | [0]" \
    --output text
}

wait_for_running() {
  local service_name="$1"
  local service_arn
  service_arn="$(aws apprunner list-services \
    --region "$AWS_REGION" \
    --query "ServiceSummaryList[?ServiceName=='${service_name}'].ServiceArn | [0]" \
    --output text)"

  echo "Waiting for $service_name to run..."
  aws apprunner wait service-running --region "$AWS_REGION" --service-arn "$service_arn"
}

ensure_repo "$BACKEND_REPO"
ensure_repo "$FRONTEND_REPO"
ACCESS_ROLE_ARN="$(ensure_role)"

aws ecr get-login-password --region "$AWS_REGION" |
  docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

BACKEND_IMAGE="$(image_uri "$BACKEND_REPO")"
FRONTEND_IMAGE="$(image_uri "$FRONTEND_REPO")"

docker build -f backend/Dockerfile -t "$BACKEND_IMAGE" .
docker push "$BACKEND_IMAGE"

BACKEND_ENV="{\"MANAGER_PASSWORD\":\"${MANAGER_PASSWORD:-manager-demo}\",\"MANAGER_AUTH_SECRET\":\"${MANAGER_AUTH_SECRET:-change-me-before-production}\",\"SLACK_WEBHOOK_URL\":\"${SLACK_WEBHOOK_URL:-}\"}"
create_or_update_service "$BACKEND_SERVICE" "$BACKEND_IMAGE" "8010" "$ACCESS_ROLE_ARN" "$BACKEND_ENV"
wait_for_running "$BACKEND_SERVICE"

BACKEND_URL="https://$(service_url "$BACKEND_SERVICE")"
echo "Backend URL: $BACKEND_URL"

docker build \
  -f frontend/Dockerfile \
  --build-arg NEXT_PUBLIC_API_URL="$BACKEND_URL" \
  -t "$FRONTEND_IMAGE" .
docker push "$FRONTEND_IMAGE"

FRONTEND_ENV="{\"NEXT_PUBLIC_API_URL\":\"${BACKEND_URL}\"}"
create_or_update_service "$FRONTEND_SERVICE" "$FRONTEND_IMAGE" "3000" "$ACCESS_ROLE_ARN" "$FRONTEND_ENV"
wait_for_running "$FRONTEND_SERVICE"

FRONTEND_URL="https://$(service_url "$FRONTEND_SERVICE")"

echo
echo "Deployment complete."
echo "Frontend: $FRONTEND_URL"
echo "Backend:  $BACKEND_URL"
