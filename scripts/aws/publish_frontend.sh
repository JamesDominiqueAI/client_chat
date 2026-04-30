#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TERRAFORM_DIR="$ROOT_DIR/terraform"

API_BASE_URL="${API_BASE_URL:-$(cd "$TERRAFORM_DIR" && terraform output -raw api_base_url)}"
FRONTEND_BUCKET="${FRONTEND_BUCKET:-$(cd "$TERRAFORM_DIR" && terraform output -raw frontend_bucket_name)}"
CLOUDFRONT_DISTRIBUTION_ID="${CLOUDFRONT_DISTRIBUTION_ID:-$(cd "$TERRAFORM_DIR" && terraform output -raw cloudfront_distribution_id)}"

cd "$ROOT_DIR/frontend"
STATIC_EXPORT=1 NEXT_PUBLIC_API_URL="$API_BASE_URL" npm run build:static

aws s3 sync out/ "s3://${FRONTEND_BUCKET}" --delete
aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" --paths "/*" >/dev/null

echo "Published frontend to s3://${FRONTEND_BUCKET}"
echo "Invalidated CloudFront distribution ${CLOUDFRONT_DISTRIBUTION_ID}"
