"""Claude-powered content generation for agendas, notes, and health assessments."""

from typing import Optional

import anthropic
from anthropic import AsyncAnthropic
import structlog

from src.config.settings import settings

logger = structlog.get_logger()

MODEL = "claude-opus-4-6"


def _get_client() -> AsyncAnthropic:
    """Get async Anthropic client."""
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


async def generate_agenda(
    customer_name: str,
    meeting_date: str,
    template_text: str,
    recent_tickets: list[dict] = None,
    last_meeting_notes: str = "",
    open_action_items: list[str] = None,
    slack_activity_summary: str = "",
) -> str:
    """Generate a meeting agenda using Claude."""
    recent_tickets = recent_tickets or []
    open_action_items = open_action_items or []

    tickets_text = ""
    if recent_tickets:
        tickets_text = "\n".join(
            f"- [{t.get('identifier', 'N/A')}] {t.get('title', '')} ({t.get('state', {}).get('name', '')})"
            for t in recent_tickets
        )

    actions_text = "\n".join(f"- {item}" for item in open_action_items) if open_action_items else "None"

    prompt = f"""Generate a meeting agenda for an upcoming customer call.

Customer: {customer_name}
Meeting Date: {meeting_date}

## Template Structure (follow this format):
{template_text}

## Context for agenda generation:

### Recent Linear Tickets:
{tickets_text or "No recent tickets"}

### Last Meeting Notes Summary:
{last_meeting_notes or "No previous notes available"}

### Open Action Items:
{actions_text}

### Recent Slack Activity:
{slack_activity_summary or "No notable activity"}

## Instructions:
- Follow the template structure exactly
- Incorporate relevant context from tickets, past notes, and action items
- Add specific discussion points based on the context
- Include time estimates for each section if the template has them
- Keep it concise but comprehensive
- Use professional TAM language"""

    client = _get_client()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    result = response.content[0].text
    logger.info("content.agenda_generated", customer=customer_name, length=len(result))
    return result


async def generate_meeting_notes(
    customer_name: str,
    meeting_date: str,
    transcript: str,
    template_text: str,
) -> dict:
    """Generate meeting notes and extract action items from a transcript.

    Returns:
        dict with keys: "notes" (str), "action_items" (list of dicts with title, description, assignee)
    """
    prompt = f"""Analyze this meeting transcript and generate structured meeting notes with action items.

Customer: {customer_name}
Meeting Date: {meeting_date}

## Notes Template (follow this format):
{template_text}

## Transcript:
{transcript[:50000]}

## Instructions:
1. Generate meeting notes following the template structure
2. Extract ALL action items mentioned in the call
3. For each action item, identify: title, description, and who it's assigned to (if mentioned)

## Output Format:
Return your response in exactly this format:

### MEETING NOTES ###
[Your structured meeting notes here, following the template]

### ACTION ITEMS ###
For each action item, use this exact format:
- TITLE: [brief title]
  DESCRIPTION: [detailed description]
  ASSIGNEE: [person responsible, or "Unassigned"]

Be thorough in extracting action items — capture every commitment, follow-up, and task mentioned."""

    client = _get_client()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    logger.info("content.notes_generated", customer=customer_name, length=len(raw))

    # Parse the response
    notes = raw
    action_items = []

    if "### ACTION ITEMS ###" in raw:
        parts = raw.split("### ACTION ITEMS ###")
        notes_part = parts[0].replace("### MEETING NOTES ###", "").strip()
        actions_part = parts[1].strip()

        notes = notes_part

        # Parse action items
        current_item = {}
        for line in actions_part.split("\n"):
            line = line.strip()
            if line.startswith("- TITLE:"):
                if current_item:
                    action_items.append(current_item)
                current_item = {"title": line.replace("- TITLE:", "").strip()}
            elif line.startswith("DESCRIPTION:"):
                current_item["description"] = line.replace("DESCRIPTION:", "").strip()
            elif line.startswith("ASSIGNEE:"):
                current_item["assignee"] = line.replace("ASSIGNEE:", "").strip()

        if current_item:
            action_items.append(current_item)

    return {"notes": notes, "action_items": action_items}


async def generate_health_assessment(
    customer_name: str,
    meeting_notes: str = "",
    recent_slack_summary: str = "",
    open_tickets_summary: str = "",
    previous_health_status: str = "",
    previous_health_summary: str = "",
) -> dict:
    """Generate a customer health assessment.

    Returns:
        dict with keys: "health_status" (green/yellow/red), "summary", "key_risks", "opportunities"
    """
    prompt = f"""Assess the health of this customer relationship based on the provided context.

Customer: {customer_name}

## Previous Health Status: {previous_health_status or "Unknown"}
## Previous Health Summary: {previous_health_summary or "None"}

## Recent Meeting Notes:
{meeting_notes or "No recent meeting notes"}

## Recent Slack Activity:
{recent_slack_summary or "No notable Slack activity"}

## Open Tickets/Issues:
{open_tickets_summary or "No open tickets"}

## Instructions:
Assess the customer's health and provide:
1. A RAG status (green, yellow, or red)
2. A brief summary (2-3 sentences)
3. Key risks (if any)
4. Opportunities (if any)

## Output Format (use exactly this):
STATUS: [green/yellow/red]
SUMMARY: [2-3 sentence summary]
KEY_RISKS: [comma-separated list of risks, or "None"]
OPPORTUNITIES: [comma-separated list of opportunities, or "None"]"""

    client = _get_client()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    logger.info("content.health_generated", customer=customer_name)

    # Parse response
    result = {
        "health_status": "green",
        "summary": "",
        "key_risks": "",
        "opportunities": "",
    }

    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("STATUS:"):
            status = line.replace("STATUS:", "").strip().lower()
            if status in ("green", "yellow", "red"):
                result["health_status"] = status
        elif line.startswith("SUMMARY:"):
            result["summary"] = line.replace("SUMMARY:", "").strip()
        elif line.startswith("KEY_RISKS:"):
            result["key_risks"] = line.replace("KEY_RISKS:", "").strip()
        elif line.startswith("OPPORTUNITIES:"):
            result["opportunities"] = line.replace("OPPORTUNITIES:", "").strip()

    return result
