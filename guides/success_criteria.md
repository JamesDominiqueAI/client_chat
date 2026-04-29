# Success Criteria

- A manager can ask for urgent complaints and receive only open urgent cases.
- A manager can ask for issue summaries and see recurring categories.
- A manager can ask for sentiment and receive a count-based sentiment snapshot.
- A manager can generate an action plan and a manager-ready report.
- The MCP registry exposes 10 servers: 5 internal and 5 external.
- The Slack external MCP server can send a real webhook alert when `SLACK_WEBHOOK_URL` is configured.
- Manager login protects CSV import.
- CSV import replaces the SQLite complaint dataset.
- Audit events persist in SQLite instead of only memory.
- CSV export returns the same complaint dataset used by the tools.
- Markdown report download returns the same manager-ready report produced by the report tool.
- Observability metrics show recent tool usage, guardrail count, source counts, and latency.
- Unsafe prompt-injection requests are blocked by a guardrail response.
- Every chat response includes `mcpServer`, `connection`, `tool`, `source`, `traceId`, and `latencyMs`.
- Tests cover routing, MCP tool output, adapter stubs, and security guardrails.
