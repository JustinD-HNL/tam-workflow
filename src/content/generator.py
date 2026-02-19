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
    recent_issues: list[dict] = None,
    last_meeting_notes: str = "",
    open_action_items: list[str] = None,
    slack_activity_summary: str = "",
    web_content: str = "",
) -> str:
    """Generate a meeting agenda using Claude."""
    recent_issues = recent_issues or []
    open_action_items = open_action_items or []

    issues_text = ""
    if recent_issues:
        issues_text = "\n".join(
            f"- [{t.get('identifier', 'N/A')}] {t.get('title', '')} ({t.get('state', {}).get('name', '')})"
            for t in recent_issues
        )

    actions_text = "\n".join(f"- {item}" for item in open_action_items) if open_action_items else "None"

    web_content_section = ""
    if web_content:
        web_content_section = f"""
### Pre-fetched Web Content (use this to populate any template sections that reference URLs, changelogs, or product updates):
{web_content}
"""

    prompt = f"""Generate a meeting agenda for an upcoming customer call.

Customer: {customer_name}
Meeting Date: {meeting_date}

## Template Structure (follow this format):
{template_text}

## Context for agenda generation:

### Recent Linear Issues:
{issues_text or "No recent issues"}

### Last Meeting Notes Summary:
{last_meeting_notes or "No previous notes available"}

### Open Action Items:
{actions_text}

### Recent Slack Activity:
{slack_activity_summary or "No notable activity"}
{web_content_section}
## Instructions:
- Follow the template structure exactly
- Incorporate relevant context from issues, past notes, and action items
- Add specific discussion points based on the context
- Include time estimates for each section if the template has them
- Keep it concise but comprehensive
- Use professional TAM language
- CRITICAL: The template may contain meta-instructions, notes to the AI, verification reminders, or placeholder instructions (enclosed in underscores, curly braces, brackets, parentheses, or italics). These are INSTRUCTIONS FOR YOU — they must NEVER appear in your output. Examples of text you must strip and act on (not copy):
  - "*(Note: Verify and update ...)*"
  - "__{{search URL ...}}__"
  - "{{fetch: URL}}"
  - "(Note: ...)"
  - Any italicized instruction or parenthetical reminder about fetching, verifying, or updating content
  Replace these instructions with the actual content they are asking for, using the pre-fetched web content provided above. If no relevant content is available, simply omit the instruction text entirely.
- When listing product updates or changelog entries, format each as a bullet point with the date and a link to the full entry
- The final output must read as a polished, customer-ready agenda with NO meta-instructions, AI notes, or template directives visible"""

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
    prompt = f"""Analyze this meeting transcript and generate structured MEETING NOTES (NOT an agenda) with action items.

Customer: {customer_name}
Meeting Date: {meeting_date}

## Notes Template (follow this format):
{template_text}

## Transcript:
{transcript[:50000]}

## Instructions:
1. Generate meeting notes following the template structure. IMPORTANT: The title/header must say "Meeting Notes" (NOT "Meeting Agenda"). These are notes summarizing what was DISCUSSED, not a future agenda.
2. Extract ALL action items mentioned in the call
3. For each action item, identify: title, description, and who it's assigned to (if mentioned)
4. Each action item description should include enough context from the meeting that someone reading it in a task tracker (Linear) would understand WHY this task exists and WHAT was discussed. Include relevant background, decisions made, and any deadlines or dependencies mentioned.

## Output Format:
Return your response in exactly this format:

### MEETING NOTES ###
[Your structured meeting notes here, following the template]

### ACTION ITEMS ###
For each action item, use this exact format:
- TITLE: [brief, actionable title]
  DESCRIPTION: [Detailed description with meeting context. Include: what was discussed, why this matters, any relevant background, deadlines mentioned, and dependencies. This will be used as the Linear issue description so make it self-contained and useful for someone who wasn't on the call. Use markdown formatting.]
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

    # Parse the response — extract action items but keep them in the notes text too
    notes = raw
    action_items = []

    if "### ACTION ITEMS ###" in raw:
        parts = raw.split("### ACTION ITEMS ###")
        notes_part = parts[0].replace("### MEETING NOTES ###", "").strip()
        actions_part = parts[1].strip()

        # Parse action items into structured records (for Linear ticket creation)
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

        # Build a readable action items section to include in the notes
        action_lines = ["\n\n### Action Items"]
        for ai in action_items:
            assignee = ai.get("assignee", "Unassigned")
            action_lines.append(f"- **{ai.get('title', '')}** ({assignee})")
        notes = notes_part + "\n".join(action_lines)

    return {"notes": notes, "action_items": action_items}


async def generate_health_assessment(
    customer_name: str,
    meeting_notes: str = "",
    recent_slack_summary: str = "",
    open_issues_summary: str = "",
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

## Open Issues:
{open_issues_summary or "No open issues"}

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
