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
        handler=TOOL_REGISTRY["get_urgent_complaints"],
    ),
    "summarize_issues": MCPServer(
        name="internal-issue-summary-mcp",
        tool="summarize_issues",
        connection="internal",
        description="Summarizes recurring complaint categories and open-case volume.",
        handler=TOOL_REGISTRY["summarize_issues"],
    ),
    "generate_manager_report": MCPServer(
        name="internal-manager-report-mcp",
        tool="generate_manager_report",
        connection="internal",
        description="Builds the manager-ready complaint report.",
        handler=TOOL_REGISTRY["generate_manager_report"],
    ),
    "generate_action_plan": MCPServer(
        name="internal-action-plan-mcp",
        tool="generate_action_plan",
        connection="internal",
        description="Turns current complaint signals into manager next steps.",
        handler=TOOL_REGISTRY["generate_action_plan"],
    ),
    "analyze_sentiment": MCPServer(
        name="internal-sentiment-mcp",
        tool="analyze_sentiment",
        connection="internal",
        description="Computes complaint sentiment counts and manager notes.",
        handler=TOOL_REGISTRY["analyze_sentiment"],
    ),
    "lookup_crm_customer": MCPServer(
        name="external-crm-mcp",
        tool="lookup_crm_customer",
        connection="external",
        description="CRM lookup adapter for urgent customer records.",
        handler=TOOL_REGISTRY["lookup_crm_customer"],
    ),
    "create_ticket_escalation": MCPServer(
        name="external-ticketing-mcp",
        tool="create_ticket_escalation",
        connection="external",
        description="Ticketing adapter for complaint escalation creation.",
        handler=TOOL_REGISTRY["create_ticket_escalation"],
    ),
    "check_service_status": MCPServer(
        name="external-status-page-mcp",
        tool="check_service_status",
        connection="external",
        description="Status-page adapter for service incident checks.",
        handler=TOOL_REGISTRY["check_service_status"],
    ),
    "send_slack_alert": MCPServer(
        name="external-slack-mcp",
        tool="send_slack_alert",
        connection="external",
        description="Slack adapter for support team alerts.",
        handler=TOOL_REGISTRY["send_slack_alert"],
    ),
    "send_customer_email_batch": MCPServer(
        name="external-email-mcp",
        tool="send_customer_email_batch",
        connection="external",
        description="Email adapter for customer update batches.",
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
            }
            for server in MCP_SERVERS.values()
        ]

    def counts(self) -> dict[str, int]:
        servers = self.list_servers()
        internal = sum(1 for server in servers if server["connection"] == "internal")
        external = sum(1 for server in servers if server["connection"] == "external")
        return {"total": len(servers), "internal": internal, "external": external}


mcp_registry = FastMCPRegistry()
