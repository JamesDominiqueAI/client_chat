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
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.mcp.server import mcp_registry
from backend.mcp.tools import TOOL_REGISTRY, export_complaints_csv, generate_manager_report, load_complaints
from backend.runtime_config import config_value
from backend.session_store import get_session_state, record_session_turn
from backend.store import active_store_backend, import_complaints_csv, list_audit_events, now_iso, record_audit_event
from backend.telemetry import langfuse_flush, langfuse_trace, recent_spans, telemetry_status, traced_span

MAX_MESSAGE_LENGTH = 1200
BLOCKED_PHRASES = [
    "ignore previous instructions",
    "print secrets",
    "show secrets",
    "show me the",
    "environment variables",
    ".env",
    "exfiltrate",
    "system prompt",
    "hidden tokens",
    "admin access",
]


def estimate_tokens(text: str) -> int:
    """Estimate token count - approximate using word + char divided by 4."""
    if not text:
        return 0
    words = len(text.split())
    chars = len(text)
    # Rough approximation: avg 4 chars per token
    return max(1, (words + chars) // 4)


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
    sessionId: str = Field(min_length=8, max_length=120)


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
    sessionId: str
    tokenCount: int = 0
    discoveredTools: list[dict[str, Any]] = Field(default_factory=list)


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


def manager_workspace_auth_required() -> bool:
    return os.getenv("REQUIRE_MANAGER_AUTH", "1").strip().lower() not in {"0", "false", "no"}


def select_tool(message: str, session_id: str) -> tuple[str, list[dict[str, Any]]]:
    lowered = message.lower()
    if is_unsafe(lowered):
        return "security_guardrail", []
    session_state = get_session_state(session_id)
    discovered = mcp_registry.discover(message)
    return mcp_registry.best_match(message, session_state.last_tool), discovered


def run_selected_tool(tool_name: str, trace_id: str) -> tuple[str, str, str, str]:
    if tool_name == "security_guardrail":
        return (
            "security_guardrail",
            "security-guardrail",
            "internal",
            "I cannot help with requests to bypass instructions, reveal secrets, or inspect private environment data.",
        )
    try:
        with traced_span("mcp.call_tool", trace_id, {"tool": tool_name}):
            result = mcp_registry.call_tool(tool_name)
        return result.source, result.server, result.connection, result.content
    except Exception:
        if tool_name not in TOOL_REGISTRY:
            raise
        with traced_span("tool.direct_fallback", trace_id, {"tool": tool_name}):
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


def require_manager(authorization: str | None = None, token: str | None = None) -> None:
    bearer_token = token
    if not bearer_token and isinstance(authorization, str) and authorization.startswith("Bearer "):
        bearer_token = authorization.removeprefix("Bearer ").strip()
    if not bearer_token:
        raise HTTPException(status_code=401, detail="Manager login is required.")
    if not verify_token(bearer_token):
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
async def complaints(authorization: str | None = Header(default=None)) -> list[dict]:
    if manager_workspace_auth_required():
        require_manager(authorization)
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
async def export_csv(authorization: str | None = Header(default=None), token: str | None = None) -> Response:
    if manager_workspace_auth_required():
        require_manager(authorization, token)
    return Response(
        content=export_complaints_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="complaints.csv"'},
    )


@app.get("/api/report.md")
async def export_report(authorization: str | None = Header(default=None), token: str | None = None) -> Response:
    if manager_workspace_auth_required():
        require_manager(authorization, token)
    return Response(
        content=generate_manager_report(),
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="customer-support-report.md"'},
    )


@app.get("/api/observability/metrics")
async def observability_metrics(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if manager_workspace_auth_required():
        require_manager(authorization)
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
        "traces": {
            "status": telemetry_status(),
            "recentSpans": recent_spans(),
        },
        "notes": [
            f"Metrics are persisted through the active {active_store_backend()} store backend.",
            "Every chat response carries trace, tool, source, latency, and session metadata.",
        ],
    }


@app.get("/api/integrations")
async def integrations(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if manager_workspace_auth_required():
        require_manager(authorization)
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


@app.get("/api/mcp/registry")
async def mcp_registry_view(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if manager_workspace_auth_required():
        require_manager(authorization)
    return {
        "counts": mcp_registry.counts(),
        "servers": mcp_registry.list_servers(),
    }


@app.get("/api/mcp/discover")
async def mcp_discover(query: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if manager_workspace_auth_required():
        require_manager(authorization)
    return {"query": query, "matches": mcp_registry.discover(query)}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, authorization: str | None = Header(default=None)) -> ChatResponse:
    if manager_workspace_auth_required():
        require_manager(authorization)
    start = time.perf_counter()
    trace_id = str(uuid.uuid4())
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message is required.")
    
    # Send to Langfuse for full observability if configured
    langfuse_trace(
        name="chat.request",
        trace_id=trace_id,
        input_text=message,
        metadata={"session_id": payload.sessionId},
        start_time=start,
    )
    
    tool, discovered = select_tool(message, payload.sessionId)
    with traced_span("chat.request", trace_id, {"session.id": payload.sessionId, "tool.selected": tool}):
        source, mcp_server, connection, response = run_selected_tool(tool, trace_id)
    
    latency_ms = int((time.perf_counter() - start) * 1000)
    
    # Estimate token count
    token_count = estimate_tokens(message) + estimate_tokens(response)
    
    record_session_turn(payload.sessionId, message, tool)
    record_chat_event(
        tool=tool,
        source=source,
        mcp_server=mcp_server,
        connection=connection,
        trace_id=trace_id,
        latency_ms=latency_ms,
        guarded=tool == "security_guardrail",
    )
    
    # Flush Langfuse
    langfuse_flush()
    
    return ChatResponse(
        response=response,
        tool=tool,
        mcpServer=mcp_server,
        connection=connection,
        source=source,
        traceId=trace_id,
        latencyMs=latency_ms,
        sessionId=payload.sessionId,
        tokenCount=token_count,
        discoveredTools=discovered[:3],
    )


async def generate_chat_stream(response_text: str, tool: str, mcp_server: str, connection: str, source: str, trace_id: str, latency_ms: int, session_id: str, token_count: int, discovered_tools: list[dict[str, Any]]):
    """Generate streaming response with SSE."""
    import json
    import asyncio
    
    # Stream the response in chunks
    words = response_text.split()
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield f"data: {json.dumps({'chunk': chunk, 'type': 'content'})}\n\n"
        await asyncio.sleep(0.02)  # Simulate streaming delay
    
    # Send final metadata
    yield f"data: {json.dumps({'type': 'done', 'tool': tool, 'mcpServer': mcp_server, 'connection': connection, 'source': source, 'traceId': trace_id, 'latencyMs': latency_ms, 'sessionId': session_id, 'tokenCount': token_count, 'discoveredTools': discovered_tools})}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest, authorization: str | None = Header(default=None)) -> StreamingResponse:
    if manager_workspace_auth_required():
        require_manager(authorization)
    start = time.perf_counter()
    trace_id = str(uuid.uuid4())
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message is required.")
    
    # Send to Langfuse for full observability if configured
    langfuse_trace(
        name="chat.stream.request",
        trace_id=trace_id,
        input_text=message,
        metadata={"session_id": payload.sessionId, "streaming": True},
        start_time=start,
    )
    
    tool, discovered = select_tool(message, payload.sessionId)
    with traced_span("chat.stream.request", trace_id, {"session.id": payload.sessionId, "tool.selected": tool}):
        source, mcp_server, connection, response = run_selected_tool(tool, trace_id)
    
    latency_ms = int((time.perf_counter() - start) * 1000)
    
    # Estimate token count
    token_count = estimate_tokens(message) + estimate_tokens(response)
    
    record_session_turn(payload.sessionId, message, tool)
    record_chat_event(
        tool=tool,
        source=source,
        mcp_server=mcp_server,
        connection=connection,
        trace_id=trace_id,
        latency_ms=latency_ms,
        guarded=tool == "security_guardrail",
    )
    
    # Flush Langfuse
    langfuse_flush()
    
    return StreamingResponse(
        generate_chat_stream(response, tool, mcp_server, connection, source, trace_id, latency_ms, payload.sessionId, token_count, discovered[:3]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8010, reload=True)
