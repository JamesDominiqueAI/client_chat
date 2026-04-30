from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .tools import TOOL_REGISTRY


@dataclass(frozen=True)
class MCPServer:
    name: str
    tool: str
    connection: str
    description: str
    keywords: tuple[str, ...]
    handler: Callable[[], str]


@dataclass(frozen=True)
class ToolResult:
    tool: str
    content: str
    server: str
    connection: str
    source: str = "mcp"


MCP_SERVERS: dict[str, MCPServer] = {
    "get_urgent_complaints": MCPServer(
        name="internal-urgent-complaints-mcp",
        tool="get_urgent_complaints",
        connection="internal",
        description="Finds open urgent complaints that need manager review.",
        keywords=("urgent", "priority", "critical", "escalate", "open"),
        handler=TOOL_REGISTRY["get_urgent_complaints"],
    ),
    "summarize_issues": MCPServer(
        name="internal-issue-summary-mcp",
        tool="summarize_issues",
        connection="internal",
        description="Summarizes recurring complaint categories and open-case volume.",
        keywords=("summary", "summarize", "recurring", "issues", "categories", "complaints"),
        handler=TOOL_REGISTRY["summarize_issues"],
    ),
    "generate_manager_report": MCPServer(
        name="internal-manager-report-mcp",
        tool="generate_manager_report",
        connection="internal",
        description="Builds the manager-ready complaint report.",
        keywords=("report", "manager-ready", "briefing", "leadership", "markdown"),
        handler=TOOL_REGISTRY["generate_manager_report"],
    ),
    "generate_action_plan": MCPServer(
        name="internal-action-plan-mcp",
        tool="generate_action_plan",
        connection="internal",
        description="Turns current complaint signals into manager next steps.",
        keywords=("action", "plan", "next", "steps", "recommendation"),
        handler=TOOL_REGISTRY["generate_action_plan"],
    ),
    "analyze_sentiment": MCPServer(
        name="internal-sentiment-mcp",
        tool="analyze_sentiment",
        connection="internal",
        description="Computes complaint sentiment counts and manager notes.",
        keywords=("sentiment", "mood", "tone", "negative", "positive"),
        handler=TOOL_REGISTRY["analyze_sentiment"],
    ),
    "lookup_crm_customer": MCPServer(
        name="external-crm-mcp",
        tool="lookup_crm_customer",
        connection="external",
        description="CRM lookup adapter for urgent customer records.",
        keywords=("crm", "customer record", "customer history", "account lookup"),
        handler=TOOL_REGISTRY["lookup_crm_customer"],
    ),
    "create_ticket_escalation": MCPServer(
        name="external-ticketing-mcp",
        tool="create_ticket_escalation",
        connection="external",
        description="Ticketing adapter for complaint escalation creation.",
        keywords=("ticket", "ticketing", "escalation", "jira", "zendesk"),
        handler=TOOL_REGISTRY["create_ticket_escalation"],
    ),
    "check_service_status": MCPServer(
        name="external-status-page-mcp",
        tool="check_service_status",
        connection="external",
        description="Status-page adapter for service incident checks.",
        keywords=("status", "status page", "incident", "service status", "outage"),
        handler=TOOL_REGISTRY["check_service_status"],
    ),
    "send_slack_alert": MCPServer(
        name="external-slack-mcp",
        tool="send_slack_alert",
        connection="external",
        description="Slack adapter for support team alerts.",
        keywords=("slack", "alert", "team alert", "channel", "notify"),
        handler=TOOL_REGISTRY["send_slack_alert"],
    ),
    "send_customer_email_batch": MCPServer(
        name="external-email-mcp",
        tool="send_customer_email_batch",
        connection="external",
        description="Email adapter for customer update batches.",
        keywords=("email", "mail", "customer update", "sendgrid", "batch"),
        handler=TOOL_REGISTRY["send_customer_email_batch"],
    ),
}


class FastMCPRegistry:
    """Small local registry shaped like the FastMCP boundary used in production."""

    def call_tool(self, tool_name: str) -> ToolResult:
        if tool_name not in MCP_SERVERS:
            raise KeyError(f"Unknown MCP tool: {tool_name}")
        server = MCP_SERVERS[tool_name]
        return ToolResult(
            tool=tool_name,
            content=server.handler(),
            server=server.name,
            connection=server.connection,
        )

    def list_servers(self) -> list[dict[str, str]]:
        return [
            {
                "name": server.name,
                "tool": server.tool,
                "connection": server.connection,
                "description": server.description,
                "keywords": ", ".join(server.keywords),
            }
            for server in MCP_SERVERS.values()
        ]

    def discover(self, query: str) -> list[dict[str, str | int]]:
        lowered = query.lower()
        ranked: list[tuple[int, MCPServer]] = []
        for server in MCP_SERVERS.values():
            score = 0
            for keyword in server.keywords:
                if keyword in lowered:
                    score += max(2, len(keyword.split()))
            if server.tool.replace("_", " ") in lowered:
                score += 5
            if score:
                ranked.append((score, server))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "tool": server.tool,
                "name": server.name,
                "connection": server.connection,
                "description": server.description,
                "score": score,
            }
            for score, server in ranked
        ]

    def best_match(self, query: str, last_tool: str | None = None) -> str:
        discovered = self.discover(query)
        if discovered:
            return str(discovered[0]["tool"])
        lowered = query.lower()
        if last_tool and any(token in lowered for token in ("that", "those", "them", "same", "follow up", "follow-up")):
            return last_tool
        return "summarize_issues"

    def counts(self) -> dict[str, int]:
        servers = self.list_servers()
        internal = sum(1 for server in servers if server["connection"] == "internal")
        external = sum(1 for server in servers if server["connection"] == "external")
        return {"total": len(servers), "internal": internal, "external": external}


mcp_registry = FastMCPRegistry()
