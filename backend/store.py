from __future__ import annotations

import os
from typing import Any

from backend import store_dynamodb, store_sqlite

DATA_PATH = store_sqlite.DATA_PATH
COMPLAINT_FIELDS = store_sqlite.COMPLAINT_FIELDS


def _backend_module():
    backend = os.getenv("STORE_BACKEND", "sqlite").strip().lower()
    if backend == "dynamodb":
        return store_dynamodb
    return store_sqlite


def active_store_backend() -> str:
    return os.getenv("STORE_BACKEND", "sqlite").strip().lower() or "sqlite"


def now_iso() -> str:
    return _backend_module().now_iso()


def init_db() -> None:
    _backend_module().init_db()


def list_complaints() -> list[dict[str, Any]]:
    return _backend_module().list_complaints()


def replace_complaints(complaints: list[dict[str, Any]], conn: Any = None) -> int:
    return _backend_module().replace_complaints(complaints, conn=conn)


def import_complaints_csv(csv_text: str) -> int:
    return _backend_module().import_complaints_csv(csv_text)


def record_audit_event(event: dict[str, Any]) -> None:
    _backend_module().record_audit_event(event)


def list_audit_events(limit: int = 200) -> list[dict[str, Any]]:
    return _backend_module().list_audit_events(limit=limit)
