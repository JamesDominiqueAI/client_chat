# Prompt Iteration Log

## Baseline

Initial prompts such as "summarize complaints" and "show urgent complaints" routed correctly, but reporting prompts needed clearer matching for "manager-ready report."

## Routing Changes

- Added `urgent` and `priority` matching for `get_urgent_complaints`.
- Added `sentiment` and `mood` matching for `analyze_sentiment`.
- Added `action plan` and `next steps` matching for `generate_action_plan`.
- Added `report` and `manager-ready` matching for `generate_manager_report`.
- Added adapter keywords for CRM, ticketing, service status, Slack, and customer email.

## Guardrail Changes

Unsafe requests containing phrases such as "ignore previous instructions", ".env", "print secrets", and "system prompt" now route to `security_guardrail`.
