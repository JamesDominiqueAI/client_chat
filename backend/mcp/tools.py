from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.request
from collections import Counter
from io import StringIO
from typing import Any

from backend.store import list_complaints


def load_complaints() -> list[dict[str, Any]]:
    return list_complaints()


def get_urgent_complaints() -> str:
    urgent = [item for item in load_complaints() if item["priority"] == "urgent" and item["status"] == "open"]
    if not urgent:
        return "No urgent open complaints are currently waiting."
    lines = ["Urgent open complaints:"]
    for item in urgent:
        lines.append(
            f"- {item['id']} | {item['customer']} ({item['account']}): {item['issue']}. "
            f"Requested action: {item['requested_action']}"
        )
    return "\n".join(lines)


def summarize_issues() -> str:
    complaints = load_complaints()
    category_counts = Counter(item["category"] for item in complaints)
    open_count = sum(1 for item in complaints if item["status"] == "open")
    urgent_count = sum(1 for item in complaints if item["priority"] == "urgent" and item["status"] == "open")
    lines = [
        f"Complaint snapshot: {len(complaints)} total complaints, {open_count} open, {urgent_count} urgent.",
        "Recurring issue themes:",
    ]
    for category, count in category_counts.most_common():
        examples = [item["issue"] for item in complaints if item["category"] == category][:2]
        lines.append(f"- {category}: {count} complaint(s). Examples: {', '.join(examples)}.")
    return "\n".join(lines)


def analyze_sentiment() -> str:
    complaints = load_complaints()
    counts = Counter(item["sentiment"] for item in complaints)
    total = len(complaints) or 1
    lines = ["Sentiment snapshot:"]
    for label in ("negative", "neutral", "positive"):
        count = counts.get(label, 0)
        lines.append(f"- {label.title()}: {count} ({round(count / total * 100)}%).")
    if counts.get("negative", 0) >= total / 2:
        lines.append("Manager note: negative sentiment is the dominant signal, so urgent outreach should happen before routine follow-up.")
    return "\n".join(lines)


def generate_action_plan() -> str:
    urgent = [item for item in load_complaints() if item["priority"] == "urgent" and item["status"] == "open"]
    lines = [
        "Manager action plan:",
        "1. Assign urgent open complaints to senior support before normal queue work.",
        "2. Send same-day status updates for shipping and damaged-order cases.",
        "3. Ask billing operations to verify refund traces for unresolved billing complaints.",
        "4. Review staffing coverage for live chat because wait-time frustration appears in high-priority feedback.",
    ]
    if urgent:
        lines.append(f"5. Start with {', '.join(item['id'] for item in urgent)} because they combine urgency, negative sentiment, and open status.")
    return "\n".join(lines)


def generate_manager_report() -> str:
    return "\n\n".join(
        [
            "# Customer Support Manager Report",
            summarize_issues(),
            analyze_sentiment(),
            get_urgent_complaints(),
            generate_action_plan(),
        ]
    )


def export_complaints_csv() -> str:
    complaints = load_complaints()
    output = StringIO()
    fieldnames = ["id", "customer", "account", "priority", "status", "category", "sentiment", "issue", "requested_action"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in complaints:
        writer.writerow({field: item[field] for field in fieldnames})
    return output.getvalue()


def lookup_crm_customer() -> str:
    urgent = [item["customer"] for item in load_complaints() if item["priority"] == "urgent" and item["status"] == "open"]
    return "CRM adapter is not configured. Would look up urgent customers: " + ", ".join(urgent) + "."


def create_ticket_escalation() -> str:
    urgent_ids = [item["id"] for item in load_complaints() if item["priority"] == "urgent" and item["status"] == "open"]
    return "Ticketing adapter is not configured. Would create escalations for: " + ", ".join(urgent_ids) + "."


def check_service_status() -> str:
    return "Service-status adapter is not configured. Demo status: support portal operational, carrier tracking degraded."


def send_slack_alert() -> str:
    urgent_ids = [item["id"] for item in load_complaints() if item["priority"] == "urgent" and item["status"] == "open"]
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    message = "Customer Report Agent urgent complaint alert: " + (", ".join(urgent_ids) if urgent_ids else "no urgent open complaints")
    if not webhook_url:
        return "Slack adapter is not configured. Would alert the support-manager channel with urgent complaint IDs."
    payload = json.dumps({"text": message}).encode("utf-8")
    request = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if 200 <= response.status < 300:
                return f"Slack alert sent for urgent complaints: {', '.join(urgent_ids) or 'none'}."
            return f"Slack webhook returned status {response.status}."
    except urllib.error.URLError as exc:
        return f"Slack adapter could not send the alert: {exc.reason}."


def send_customer_email_batch() -> str:
    return "Email adapter is not configured. Would draft customer updates for urgent open complaints."


TOOL_REGISTRY = {
    "get_urgent_complaints": get_urgent_complaints,
    "summarize_issues": summarize_issues,
    "generate_manager_report": generate_manager_report,
    "generate_action_plan": generate_action_plan,
    "analyze_sentiment": analyze_sentiment,
    "lookup_crm_customer": lookup_crm_customer,
    "create_ticket_escalation": create_ticket_escalation,
    "check_service_status": check_service_status,
    "send_slack_alert": send_slack_alert,
    "send_customer_email_batch": send_customer_email_batch,
}
