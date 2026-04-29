# Deployment

The intended deployment shape is:

- Frontend: Vercel Next.js app
- Backend: Vercel Python/FastAPI service, AWS Lambda, or container service
- Dataset: bundled JSON for the capstone demo
- Future data layer: database or support-system API

## Environment Variables

Frontend:

```text
NEXT_PUBLIC_API_URL=https://your-backend.example.com
```

Backend:

```text
MANAGER_PASSWORD=replace-for-production
MANAGER_AUTH_SECRET=replace-with-a-long-random-secret
CUSTOMER_REPORT_DB=data/customer_report_agent.db
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
CRM_WEBHOOK_URL=
TICKETING_WEBHOOK_URL=
STATUS_PAGE_URL=
EMAIL_WEBHOOK_URL=
```

`SLACK_WEBHOOK_URL` makes `external-slack-mcp` a real external connection. The other external MCP servers remain safe adapter stubs until their URLs are configured and their adapter functions are wired.

## Container Deployment

The repo includes:

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `docker-compose.yml`

Run:

```bash
docker compose up --build
```

Use this path for local production-like validation before deploying the frontend and backend separately.
