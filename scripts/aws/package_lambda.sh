#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/lambda"
DIST_DIR="$ROOT_DIR/dist"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

python3 -m pip install -r "$ROOT_DIR/backend/api/requirements.txt" -t "$BUILD_DIR"

cp -R "$ROOT_DIR/backend" "$BUILD_DIR/backend"
cp -R "$ROOT_DIR/data" "$BUILD_DIR/data"

(
  cd "$BUILD_DIR"
  zip -rq "$DIST_DIR/customer-report-agent-lambda.zip" .
)

echo "$DIST_DIR/customer-report-agent-lambda.zip"
