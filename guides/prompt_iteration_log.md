# Prompt Iteration Log

## Version 1: direct phrase routing

- Good at exact prompts like "show urgent complaints"
- Weak at manager-language follow-ups like "turn that into something leadership can review"
- Weak at making the MCP layer look like real tool discovery

## Version 2: MCP keyword discovery

Changes:

- moved routing keywords into MCP server metadata
- added keyword scoring over tool descriptions and aliases
- exposed discovery results in the API response so prompt-to-tool reasoning is visible

Why:

- makes tool selection look more like MCP discovery instead of a hard-coded `if` ladder
- improves report, Slack, CRM, and status-page detection with one registry abstraction

## Version 3: session-aware follow-ups

Changes:

- added `sessionId` to chat requests
- stored recent session context and last selected tool
- if a follow-up uses referential language like "that" or "same", the router can reuse the prior tool when discovery score is empty

Why:

- improves multi-turn manager workflows without adding opaque LLM routing

## Version 4: guardrail hardening

Unsafe requests containing phrases such as:

- `ignore previous instructions`
- `.env`
- `print secrets`
- `system prompt`
- `hidden tokens`

route to `security_guardrail`.

## Verification

- prompt-to-tool routing is exercised in `backend/tests/test_mcp_tools.py`
- `scripts/evaluate_project.py` writes `evaluation/summary.json` and `guides/evaluation_report.md`
