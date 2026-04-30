# Architecture

Customer Report Agent keeps deterministic support-reporting logic as the source of truth and routes manager chat requests through an MCP-style tool boundary.

## MCP Server Inventory

The project registers 10 MCP servers:

- 5 internal MCP servers: urgent complaints, issue summary, manager report, action plan, sentiment.
- 5 external MCP servers: CRM, ticketing, status page, Slack, email.

The external servers are integration-shaped adapters. In the demo they are safe and deterministic: if real credentials or URLs are not configured, they return a "not configured" response rather than breaking the workflow.

## Request Flow

```text
Frontend chat or voice prompt
  -> POST /api/chat
  -> guardrail validation
  -> deterministic route selection
  -> MCP registry call
  -> one of 10 named MCP servers
  -> direct Python fallback if registry execution fails
  -> response with mcpServer, connection, tool, source, traceId, and latencyMs
```

## Why Deterministic Routing

The capstone demo needs repeatable behavior for known manager workflows. Deterministic routing makes tests reliable and keeps the MCP tools auditable. A later version can add LLM-based intent classification while preserving the same tool contract.

## Data Boundary

`data/complaints.json` seeds the first local SQLite workspace. After startup, complaint reads, CSV import, CSV export, and MCP tools use `data/customer_report_agent.db` by default in local development. For AWS deployment, the same store interface can switch to DynamoDB through `STORE_BACKEND=dynamodb`.

## Real External MCP Connection

`external-slack-mcp` becomes a live external connection when `SLACK_WEBHOOK_URL` is configured. The Slack tool posts an urgent-complaint alert to the webhook. Without the env var, it returns a deterministic "not configured" message for safe demos.

## AWS Deployment Shape

The intended AWS-native architecture is:

```text
User
  -> CloudFront
  -> S3 static frontend
  -> API Gateway HTTP API
  -> Lambda FastAPI app using Mangum
  -> DynamoDB complaints + audit events
  -> SSM Parameter Store / Secrets Manager
  -> CloudWatch logs and metrics
  -> Slack webhook external MCP
```

## Production Upgrade Path

- Replace JSON with Postgres, DynamoDB, or a support-system API.
- Add manager authentication and role-gated exports.
- Send trace events to Langfuse, LangSmith, or OpenTelemetry.
- Wire adapters to CRM, ticketing, Slack, email, and status-page services.
