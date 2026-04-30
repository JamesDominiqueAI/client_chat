from __future__ import annotations

import csv
import json
import os
import time
from io import StringIO
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "complaints.json"
COMPLAINT_FIELDS = [
    "id",
    "customer",
    "account",
    "channel",
    "issue",
    "category",
    "sentiment",
    "priority",
    "status",
    "created_at",
    "summary",
    "requested_action",
]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def complaints_table_name() -> str:
    return os.getenv("DYNAMODB_COMPLAINTS_TABLE", "customer-report-agent-complaints")


def audit_table_name() -> str:
    return os.getenv("DYNAMODB_AUDIT_TABLE", "customer-report-agent-audit")


def dynamodb_resource():
    import boto3

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    kwargs = {"region_name": region} if region else {}
    endpoint_url = os.getenv("DYNAMODB_ENDPOINT_URL")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.resource("dynamodb", **kwargs)


def complaints_table():
    return dynamodb_resource().Table(complaints_table_name())


def audit_table():
    return dynamodb_resource().Table(audit_table_name())


def normalize_complaint(row: dict[str, Any]) -> dict[str, str]:
    normalized = {field: str(row.get(field, "")).strip() for field in COMPLAINT_FIELDS}
    required = ["id", "customer", "account", "issue", "category", "sentiment", "priority", "status", "created_at"]
    missing = [field for field in required if not normalized[field]]
    if missing:
        raise ValueError(f"Missing required complaint fields: {', '.join(missing)}")
    normalized["channel"] = normalized["channel"] or "unknown"
    normalized["summary"] = normalized["summary"] or normalized["issue"]
    normalized["requested_action"] = normalized["requested_action"] or "Review and respond to the customer."
    return normalized


def init_db() -> None:
    table = complaints_table()
    count = table.scan(Select="COUNT").get("Count", 0)
    if count == 0:
        with DATA_PATH.open("r", encoding="utf-8") as handle:
            seed_complaints = json.load(handle)
        replace_complaints(seed_complaints)


def list_complaints() -> list[dict[str, Any]]:
    init_db()
    response = complaints_table().scan()
    items = response.get("Items", [])
    return sorted(items, key=lambda item: (item["created_at"], item["id"]), reverse=True)


def replace_complaints(complaints: list[dict[str, Any]], conn: None = None) -> int:
    del conn
    normalized = [normalize_complaint(item) for item in complaints]
    table = complaints_table()
    existing = table.scan(ProjectionExpression="id").get("Items", [])
    with table.batch_writer() as batch:
        for item in existing:
            batch.delete_item(Key={"id": item["id"]})
        for item in normalized:
            batch.put_item(Item=item)
    return len(normalized)


def import_complaints_csv(csv_text: str) -> int:
    reader = csv.DictReader(StringIO(csv_text))
    if not reader.fieldnames:
        raise ValueError("CSV header row is required.")
    rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError("CSV must contain at least one complaint row.")
    return replace_complaints(rows)


def record_audit_event(event: dict[str, Any]) -> None:
    item = {
        "traceId": event["traceId"],
        "tool": event["tool"],
        "mcpServer": event["mcpServer"],
        "connection": event["connection"],
        "source": event["source"],
        "latencyMs": int(event["latencyMs"]),
        "guarded": bool(event["guarded"]),
        "createdAt": event["createdAt"],
    }
    audit_table().put_item(Item=item)


def list_audit_events(limit: int = 200) -> list[dict[str, Any]]:
    response = audit_table().scan()
    items = response.get("Items", [])
    items.sort(key=lambda item: item["createdAt"])
    return items[-limit:]
