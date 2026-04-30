from __future__ import annotations

import time
import uuid
from pathlib import Path
import sys
import base64
import hashlib
import hmac
import os
from collections import Counter
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.mcp.server import mcp_registry
from backend.mcp.tools import TOOL_REGISTRY, export_complaints_csv, generate_manager_report, load_complaints
from backend.runtime_config import config_value
from backend.store import active_store_backend, import_complaints_csv, list_audit_events, now_iso, record_audit_event

MAX_MESSAGE_LENGTH = 1200
BLOCKED_PHRASES = [
    "ignore previous instructions",
    "print secrets",
    "show secrets",
    ".env",
    "exfiltrate",
    "system prompt",
]


def auth_secret() -> str:
    return config_value("MANAGER_AUTH_SECRET", "MANAGER_AUTH_SECRET_PARAM", "") or manager_password() or "change-me-local-demo-secret"


def manager_password() -> str:
    return config_value("MANAGER_PASSWORD", "MANAGER_PASSWORD_PARAM", "manager-demo")


def sign_token(payload: str) -> str:
    signature = hmac.new(auth_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}.{signature}".encode("utf-8")).decode("utf-8")


def verify_token(token: str) -> bool:
    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        payload, signature = decoded.rsplit(".", 1)
    except Exception:
        return False
    expected = hmac.new(auth_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    token: str
    role: str = "manager"


class ImportRequest(BaseModel):
    csvText: str = Field(min_length=1)


class ImportResponse(BaseModel):
    imported: int
    message: str
    storeBackend: str


class ChatResponse(BaseModel):
    response: str
    tool: str
    mcpServer: str
    connection: str
    source: str
    traceId: str
    latencyMs: int


app = FastAPI(
    title="Customer Report Agent API",
    description="FastAPI backend for an MCP-architected support reporting chatbot.",
    version="0.1.0",
)


def cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_origin_regex=r"^https?://((localhost|127\.0\.0\.1)(:\d+)?|.+\.cloudfront\.net)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def is_unsafe(message: str) -> bool:
    lowered = message.lower()
    return any(phrase in lowered for phrase in BLOCKED_PHRASES)


def select_tool(message: str) -> str:
    lowered = message.lower()
    if is_unsafe(lowered):
        return "security_guardrail"
    if "crm" in lowered or "customer record" in lowered:
        return "lookup_crm_customer"
    if "ticket" in lowered or "escalation" in lowered:
        return "create_ticket_escalation"
    if "service status" in lowered or "status page" in lowered:
        return "check_service_status"
    if "slack" in lowered or "team alert" in lowered:
        return "send_slack_alert"
    if "email" in lowered or "customers about" in lowered:
        return "send_customer_email_batch"
    if "urgent" in lowered or "priority" in lowered:
        return "get_urgent_complaints"
    if "sentiment" in lowered or "mood" in lowered:
        return "analyze_sentiment"
    if "action plan" in lowered or "next steps" in lowered:
        return "generate_action_plan"
    if "report" in lowered or "manager-ready" in lowered:
        return "generate_manager_report"
    return "summarize_issues"


def run_selected_tool(tool_name: str) -> tuple[str, str, str, str]:
    if tool_name == "security_guardrail":
        return (
            "security_guardrail",
            "security-guardrail",
            "internal",
            "I cannot help with requests to bypass instructions, reveal secrets, or inspect private environment data.",
        )
    try:
        result = mcp_registry.call_tool(tool_name)
        return result.source, result.server, result.connection, result.content
    except Exception:
        if tool_name not in TOOL_REGISTRY:
            raise
        return "direct", "direct-python-fallback", "internal", TOOL_REGISTRY[tool_name]()


def record_chat_event(
    tool: str,
    source: str,
    mcp_server: str,
    connection: str,
    trace_id: str,
    latency_ms: int,
    guarded: bool,
) -> None:
    record_audit_event(
        {
            "traceId": trace_id,
            "tool": tool,
            "mcpServer": mcp_server,
            "connection": connection,
            "source": source,
            "latencyMs": latency_ms,
            "guarded": guarded,
            "createdAt": now_iso(),
        }
    )


def require_manager(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Manager login is required.")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid manager token.")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "customer-report-agent-api"}


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    if not hmac.compare_digest(payload.password, manager_password()):
        raise HTTPException(status_code=401, detail="Invalid manager password.")
    issued_at = str(int(time.time()))
    return LoginResponse(token=sign_token(f"manager:{issued_at}"))


@app.get("/api/auth/me")
async def auth_me(authorization: str | None = Header(default=None)) -> dict[str, str]:
    require_manager(authorization)
    return {"role": "manager", "status": "authenticated"}


@app.get("/api/complaints")
async def complaints() -> list[dict]:
    return load_complaints()


@app.post("/api/complaints/import", response_model=ImportResponse)
async def import_complaints(payload: ImportRequest, authorization: str | None = Header(default=None)) -> ImportResponse:
    require_manager(authorization)
    try:
        imported = import_complaints_csv(payload.csvText)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    backend = active_store_backend()
    return ImportResponse(
        imported=imported,
        message=f"Imported {imported} complaints into {backend}.",
        storeBackend=backend,
    )


@app.get("/api/export.csv")
async def export_csv() -> Response:
    return Response(
        content=export_complaints_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="complaints.csv"'},
    )


@app.get("/api/report.md")
async def export_report() -> Response:
    return Response(
        content=generate_manager_report(),
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="customer-support-report.md"'},
    )


@app.get("/api/observability/metrics")
async def observability_metrics() -> dict[str, Any]:
    events = list_audit_events()
    tools = Counter(event["tool"] for event in events)
    servers = Counter(event["mcpServer"] for event in events)
    sources = Counter(event["source"] for event in events)
    latencies = sorted(event["latencyMs"] for event in events)
    p95_index = int(len(latencies) * 0.95) - 1 if latencies else 0
    return {
        "requests": {
            "total": len(events),
            "guarded": sum(1 for event in events if event["guarded"]),
            "p95LatencyMs": latencies[max(p95_index, 0)] if latencies else 0,
        },
        "storage": {
            "backend": active_store_backend(),
        },
        "tools": dict(tools),
        "mcpServers": {
            "counts": mcp_registry.counts(),
            "configured": mcp_registry.list_servers(),
            "usage": dict(servers),
        },
        "sources": dict(sources),
        "recentEvents": events[-10:],
        "notes": [
            f"Metrics are persisted through the active {active_store_backend()} store backend.",
            "Every chat response carries trace, tool, source, and latency metadata.",
        ],
    }


@app.get("/api/integrations")
async def integrations() -> dict[str, Any]:
    statuses = [
        {
            "name": "CRM",
            "mcpServer": "external-crm-mcp",
            "status": "connected" if os.getenv("CRM_WEBHOOK_URL") else "not_configured",
            "envVar": "CRM_WEBHOOK_URL",
        },
        {
            "name": "Ticketing",
            "mcpServer": "external-ticketing-mcp",
            "status": "connected" if os.getenv("TICKETING_WEBHOOK_URL") else "not_configured",
            "envVar": "TICKETING_WEBHOOK_URL",
        },
        {
            "name": "Status page",
            "mcpServer": "external-status-page-mcp",
            "status": "connected" if os.getenv("STATUS_PAGE_URL") else "not_configured",
            "envVar": "STATUS_PAGE_URL",
        },
        {
            "name": "Slack",
            "mcpServer": "external-slack-mcp",
            "status": "connected" if os.getenv("SLACK_WEBHOOK_URL") else "not_configured",
            "envVar": "SLACK_WEBHOOK_URL",
        },
        {
            "name": "Email",
            "mcpServer": "external-email-mcp",
            "status": "connected" if os.getenv("EMAIL_WEBHOOK_URL") else "not_configured",
            "envVar": "EMAIL_WEBHOOK_URL",
        },
    ]
    return {"integrations": statuses}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    start = time.perf_counter()
    trace_id = str(uuid.uuid4())
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message is required.")
    tool = select_tool(message)
    source, mcp_server, connection, response = run_selected_tool(tool)
    latency_ms = int((time.perf_counter() - start) * 1000)
    record_chat_event(
        tool=tool,
        source=source,
        mcp_server=mcp_server,
        connection=connection,
        trace_id=trace_id,
        latency_ms=latency_ms,
        guarded=tool == "security_guardrail",
    )
    return ChatResponse(
        response=response,
        tool=tool,
        mcpServer=mcp_server,
        connection=connection,
        source=source,
        traceId=trace_id,
        latencyMs=latency_ms,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8010, reload=True)
