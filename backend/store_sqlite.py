from __future__ import annotations

import csv
import json
import os
import sqlite3
import time
from io import StringIO
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "complaints.json"
DB_PATH = Path(os.getenv("CUSTOMER_REPORT_DB", ROOT / "data" / "customer_report_agent.db"))

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


def connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS complaints (
                id TEXT PRIMARY KEY,
                customer TEXT NOT NULL,
                account TEXT NOT NULL,
                channel TEXT NOT NULL,
                issue TEXT NOT NULL,
                category TEXT NOT NULL,
                sentiment TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                summary TEXT NOT NULL,
                requested_action TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                trace_id TEXT PRIMARY KEY,
                tool TEXT NOT NULL,
                mcp_server TEXT NOT NULL,
                connection TEXT NOT NULL,
                source TEXT NOT NULL,
                latency_ms INTEGER NOT NULL,
                guarded INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        if count == 0:
            with DATA_PATH.open("r", encoding="utf-8") as handle:
                seed_complaints = json.load(handle)
            replace_complaints(seed_complaints, conn=conn)


def list_complaints() -> list[dict[str, Any]]:
    init_db()
    with connection() as conn:
        rows = conn.execute("SELECT * FROM complaints ORDER BY created_at DESC, id ASC").fetchall()
    return [dict(row) for row in rows]


def replace_complaints(complaints: list[dict[str, Any]], conn: sqlite3.Connection | None = None) -> int:
    normalized = [normalize_complaint(item) for item in complaints]
    active_conn = conn or connection()
    should_close = conn is None
    try:
        active_conn.execute("DELETE FROM complaints")
        active_conn.executemany(
            """
            INSERT INTO complaints (
                id, customer, account, channel, issue, category, sentiment,
                priority, status, created_at, summary, requested_action
            )
            VALUES (
                :id, :customer, :account, :channel, :issue, :category, :sentiment,
                :priority, :status, :created_at, :summary, :requested_action
            )
            """,
            normalized,
        )
        active_conn.commit()
    finally:
        if should_close:
            active_conn.close()
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
    init_db()
    with connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO audit_events (
                trace_id, tool, mcp_server, connection, source, latency_ms, guarded, created_at
            )
            VALUES (
                :traceId, :tool, :mcpServer, :connection, :source, :latencyMs, :guarded, :createdAt
            )
            """,
            {
                **event,
                "guarded": 1 if event.get("guarded") else 0,
            },
        )


def list_audit_events(limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT trace_id, tool, mcp_server, connection, source, latency_ms, guarded, created_at
            FROM audit_events
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "traceId": row["trace_id"],
            "tool": row["tool"],
            "mcpServer": row["mcp_server"],
            "connection": row["connection"],
            "source": row["source"],
            "latencyMs": row["latency_ms"],
            "guarded": bool(row["guarded"]),
            "createdAt": row["created_at"],
        }
        for row in reversed(rows)
    ]
