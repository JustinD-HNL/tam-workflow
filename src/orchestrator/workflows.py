"""Workflow executors for each workflow type."""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.content.generator import generate_agenda, generate_health_assessment, generate_meeting_notes
from src.integrations.google import GoogleCalendarClient, GoogleDocsClient, GoogleDriveClient
from src.integrations.linear import LinearClient
from src.integrations.notion import NotionClient
from src.integrations.slack.client import SlackClient
from src.models.customer import Customer
from src.models.integration import MeetingDocument
from src.models.workflow import (
    ActionItem,
    ApprovalItem,
    ApprovalItemType,
    ApprovalStatus,
    Workflow,
    WorkflowStatus,
    WorkflowType,
)

logger = structlog.get_logger()


async def _fetch_template(template_key: str) -> str | None:
    """Fetch a template from the configured Google Doc URL.

    template_key: 'agenda_template_url' or 'notes_template_url'
    Returns the document text, or None if not configured or fetch fails.
    """
    from src.models.database import async_session as _async_session
    from src.models.app_settings import AppSetting

    try:
        async with _async_session() as session:
            result = await session.execute(
                select(AppSetting).where(AppSetting.key == template_key)
            )
            setting = result.scalar_one_or_none()
            if not setting or not setting.value:
                return None

            url = setting.value.strip()
            if not url:
                return None

            # Extract doc ID from URL
            docs_client = GoogleDocsClient()
            doc_id = docs_client.extract_doc_id_from_url(url)
            text = await docs_client.get_document_text(doc_id)

            if text and text.strip():
                logger.info("workflow.template_fetched", key=template_key, length=len(text))

                # Update last-fetched timestamp
                from datetime import datetime, timezone
                ts_key = template_key.replace("_url", "_last_fetched")
                ts_result = await session.execute(
                    select(AppSetting).where(AppSetting.key == ts_key)
                )
                ts_setting = ts_result.scalar_one_or_none()
                now_str = datetime.now(timezone.utc).isoformat()
                if ts_setting:
                    ts_setting.value = now_str
                else:
                    session.add(AppSetting(key=ts_key, value=now_str))
                await session.commit()

                return text
    except Exception as e:
        logger.warning("workflow.template_fetch_failed", key=template_key, error=str(e))

    return None


async def _fetch_template_urls(template_text: str) -> dict[str, str]:
    """Scan template text for URL placeholders and pre-fetch their content.

    Looks for patterns like:
      __{search URL instructions}__
      {search URL instructions}
      [fetch: URL]
    or just any https:// URL on a line with instructional context.

    Returns a dict mapping URL -> fetched text content.
    """
    import re
    import httpx
    from html.parser import HTMLParser

    # Find URLs in template instruction-like patterns
    url_pattern = re.compile(
        r'(?:__\{|{\s*)search\s+(https?://[^\s}]+)'  # __{search URL ...}__ or {search URL ...}
        r'|'
        r'\[fetch:\s*(https?://[^\]]+)\]'              # [fetch: URL]
        r'|'
        r'(?:search|fetch|check|list.*from)\s+(https?://[^\s)}\]]+)',  # instructional text with URL
        re.IGNORECASE,
    )

    urls = set()
    for match in url_pattern.finditer(template_text):
        url = match.group(1) or match.group(2) or match.group(3)
        if url:
            urls.add(url.rstrip('_}]'))

    if not urls:
        return {}

    results = {}

    def _extract_changelog_entries(html: str, base_url: str, max_entries: int = 15) -> str:
        """Extract structured changelog entries from HTML with dates and links."""
        # Find entry links: /resources/changelog/333-title-slug/
        links = re.findall(r'href="(/resources/changelog/(\d+)-([^"]+)/)"', html)
        # Find dates near entries
        dates = re.findall(
            r'((?:January|February|March|April|May|June|July|August|September|October|November|December)'
            r'\s+\d+,?\s+\d{4})',
            html,
        )

        seen = set()
        entries = []
        for full_path, num, slug in links:
            if num in seen:
                continue
            seen.add(num)
            # Reconstruct readable title from slug
            title = slug.replace('-', ' ')
            # Fix version dots: "v2 dot 1 dot 0" -> "v2.1.0"
            title = re.sub(r'\bdot\s+', '.', title)
            # Known acronyms/initialisms to preserve uppercase
            acronyms = {'api', 'ci', 'gcp', 'ip', 'oidc', 'sdk', 'ui', 'cli', 'aws'}
            words = title.split()
            title = ' '.join(
                w.upper() if w.lower() in acronyms else w.capitalize()
                for w in words
            )
            entry_url = base_url.rstrip('/').rsplit('/resources/', 1)[0] + full_path
            entries.append((int(num), title, entry_url))

        entries.sort(key=lambda x: x[0], reverse=True)
        entries = entries[:max_entries]

        lines = []
        for i, (num, title, entry_url) in enumerate(entries):
            date = dates[i] if i < len(dates) else ""
            date_prefix = f"({date}) " if date else ""
            lines.append(f"- {date_prefix}{title}\n  {entry_url}")

        return "\n".join(lines) if lines else ""

    for url in urls:
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; TAMWorkflow/1.0)"
                })
                resp.raise_for_status()
                html = resp.text

                # Try structured extraction for changelog/release pages
                if "changelog" in url.lower() or "releases" in url.lower():
                    text = _extract_changelog_entries(html, url)
                    if text:
                        results[url] = text
                        logger.info("workflow.template_url_fetched", url=url, entries=text.count("\n-") + 1)
                        continue

                # Generic fallback: extract headings and list items
                headings = re.findall(r'<h[1-4][^>]*>(.*?)</h[1-4]>', html, re.DOTALL)
                list_items = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)
                tag_strip = re.compile(r'<[^>]+>')
                parts = []
                for h in headings[:20]:
                    clean = tag_strip.sub('', h).strip()
                    if clean:
                        parts.append(f"## {clean}")
                for li in list_items[:30]:
                    clean = tag_strip.sub('', li).strip()
                    if clean:
                        parts.append(f"- {clean}")
                text = "\n".join(parts) if parts else tag_strip.sub('', html)[:4000]

                results[url] = text[:8000]
                logger.info("workflow.template_url_fetched", url=url, length=len(text))
        except Exception as e:
            logger.warning("workflow.template_url_fetch_failed", url=url, error=str(e))
            results[url] = f"[Could not fetch content from {url}: {str(e)}]"

    return results


# Default template text when no Google Doc template is configured
DEFAULT_AGENDA_TEMPLATE = """# Meeting Agenda
## Date: {date}
## Customer: {customer}

### 1. Opening / Check-in (5 min)
### 2. Review Action Items from Last Meeting (5 min)
### 3. Current Topics (20 min)
### 4. Open Discussion (10 min)
### 5. Action Items & Next Steps (5 min)
"""

DEFAULT_NOTES_TEMPLATE = """# Meeting Notes
## Date: {date}
## Customer: {customer}
## Attendees:

### Key Discussion Points

### Decisions Made

### Action Items

### Follow-up Items
"""


async def execute_workflow(workflow_id: uuid.UUID, db: AsyncSession):
    """Execute a workflow by type."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        logger.error("workflow.not_found", workflow_id=str(workflow_id))
        return

    # Load customer
    cust_result = await db.execute(select(Customer).where(Customer.id == workflow.customer_id))
    customer = cust_result.scalar_one_or_none()
    if not customer:
        workflow.status = WorkflowStatus.FAILED
        workflow.error_message = "Customer not found"
        await db.flush()
        return

    workflow.status = WorkflowStatus.RUNNING
    workflow.started_at = datetime.now(timezone.utc)
    await db.flush()

    try:
        if workflow.workflow_type == WorkflowType.AGENDA_GENERATION:
            await _execute_agenda_generation(workflow, customer, db)
        elif workflow.workflow_type == WorkflowType.MEETING_NOTES:
            await _execute_meeting_notes(workflow, customer, db)
        elif workflow.workflow_type == WorkflowType.HEALTH_UPDATE:
            await _execute_health_update(workflow, customer, db)
        else:
            raise ValueError(f"Unknown workflow type: {workflow.workflow_type}")

        workflow.status = WorkflowStatus.COMPLETED
        workflow.completed_at = datetime.now(timezone.utc)
    except Exception as e:
        logger.error("workflow.failed", workflow_id=str(workflow_id), error=str(e))
        workflow.status = WorkflowStatus.FAILED
        workflow.error_message = str(e)

    await db.flush()


async def _execute_agenda_generation(
    workflow: Workflow, customer: Customer, db: AsyncSession
):
    """Execute the agenda generation workflow. Resilient — uses whatever context is available."""
    context = workflow.context or {}
    meeting_date = context.get("meeting_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    steps = []

    # Step 1: Get open/in-progress Linear issues (resilient)
    recent_issues = []
    try:
        if customer.linear_project_id:
            linear = LinearClient()
            recent_issues = await linear.list_project_issues(
                customer.linear_project_id, limit=20, include_completed=False
            )
            steps.append(f"fetched_linear_issues:{len(recent_issues)}")
            logger.info("workflow.agenda.linear_ok", count=len(recent_issues))
    except Exception as e:
        logger.warning("workflow.agenda.linear_failed", error=str(e))
        steps.append("linear_issues_skipped")

    # Step 2: Get last meeting notes from approval items (most recent published notes)
    last_notes = ""
    try:
        notes_result = await db.execute(
            select(ApprovalItem)
            .where(
                ApprovalItem.customer_id == customer.id,
                ApprovalItem.item_type == ApprovalItemType.MEETING_NOTES,
                ApprovalItem.status == ApprovalStatus.PUBLISHED,
            )
            .order_by(ApprovalItem.meeting_date.desc())
            .limit(1)
        )
        last_approval = notes_result.scalar_one_or_none()
        if last_approval and last_approval.content:
            last_notes = last_approval.content
            steps.append("fetched_last_notes")
            logger.info("workflow.agenda.last_notes_ok", length=len(last_notes))
        else:
            # Fallback: check MeetingDocument table
            doc_result = await db.execute(
                select(MeetingDocument)
                .where(
                    MeetingDocument.customer_id == customer.id,
                    MeetingDocument.document_type == "notes",
                )
                .order_by(MeetingDocument.meeting_date.desc())
                .limit(1)
            )
            last_doc = doc_result.scalar_one_or_none()
            if last_doc and last_doc.content:
                last_notes = last_doc.content
                steps.append("fetched_last_notes_from_docs")
            else:
                steps.append("no_previous_notes")
    except Exception as e:
        logger.warning("workflow.agenda.notes_fetch_failed", error=str(e))
        steps.append("last_notes_skipped")

    # Step 3: Get open action items from previous meetings (resilient)
    open_action_items = []
    try:
        action_result = await db.execute(
            select(ActionItem)
            .join(ActionItem.approval_item)
            .where(
                ApprovalItem.customer_id == customer.id,
                ActionItem.status.in_([ApprovalStatus.DRAFT, ApprovalStatus.IN_REVIEW, ApprovalStatus.APPROVED]),
            )
            .order_by(ActionItem.created_at.desc())
            .limit(20)
        )
        items = action_result.scalars().all()
        open_action_items = [f"{ai.title} — {ai.description or ''}" for ai in items]
        if open_action_items:
            steps.append(f"fetched_open_actions:{len(open_action_items)}")
        else:
            steps.append("no_open_actions")
    except Exception as e:
        logger.warning("workflow.agenda.actions_fetch_failed", error=str(e))
        steps.append("open_actions_skipped")

    # Step 4: Get recent Slack activity (resilient)
    slack_activity = ""
    try:
        from src.models.integration import SlackMention
        mentions_result = await db.execute(
            select(SlackMention)
            .where(SlackMention.customer_id == customer.id)
            .order_by(SlackMention.created_at.desc())
            .limit(10)
        )
        mentions = mentions_result.scalars().all()
        if mentions:
            slack_activity = "\n".join(
                f"- [{m.user_name or m.user_id}] {m.message_text[:200]}"
                for m in mentions
            )
            steps.append(f"fetched_slack_mentions:{len(mentions)}")
        else:
            steps.append("no_slack_mentions")
    except Exception as e:
        logger.warning("workflow.agenda.slack_failed", error=str(e))
        steps.append("slack_skipped")

    # Step 5: Get template (try Google Doc first, fall back to default)
    fetched_template = await _fetch_template("agenda_template_url")
    if fetched_template:
        template_text = fetched_template
        steps.append("template_fetched_from_google_doc")
    else:
        template_text = DEFAULT_AGENDA_TEMPLATE.format(
            date=meeting_date, customer=customer.name
        )
        steps.append("template_default")

    # Step 5b: Pre-fetch any URLs referenced in the template (e.g., changelog)
    web_content = ""
    try:
        url_content = await _fetch_template_urls(template_text)
        if url_content:
            web_parts = []
            for url, content in url_content.items():
                web_parts.append(f"### Content from {url}:\n{content}")
            web_content = "\n\n".join(web_parts)
            steps.append(f"fetched_web_content:{len(url_content)}_urls")
            logger.info("workflow.agenda.web_content_fetched", urls=list(url_content.keys()))
    except Exception as e:
        logger.warning("workflow.agenda.web_content_failed", error=str(e))
        steps.append("web_content_skipped")

    # Step 6: Generate agenda with all available context
    agenda_text = await generate_agenda(
        customer_name=customer.name,
        meeting_date=meeting_date,
        template_text=template_text,
        recent_issues=recent_issues,
        last_meeting_notes=last_notes[:5000],
        open_action_items=open_action_items,
        slack_activity_summary=slack_activity,
        web_content=web_content,
    )
    steps.append("agenda_generated")

    # Step 7: Create approval item
    approval = ApprovalItem(
        item_type=ApprovalItemType.AGENDA,
        status=ApprovalStatus.DRAFT,
        title=f"Agenda — {customer.name} — {meeting_date}",
        content=agenda_text,
        customer_id=customer.id,
        workflow_id=workflow.id,
        meeting_date=datetime.fromisoformat(meeting_date) if meeting_date else None,
    )
    db.add(approval)
    steps.append("approval_item_created")

    workflow.steps_completed = steps
    await db.flush()
    logger.info("workflow.agenda.complete", customer=customer.name, steps=steps)


async def _execute_meeting_notes(
    workflow: Workflow, customer: Customer, db: AsyncSession
):
    """Execute the meeting notes generation workflow."""
    context = workflow.context or {}
    transcript_doc_id = context.get("transcript_document_id")
    meeting_date = context.get("meeting_date", "")
    steps = []

    # Step 1: Load transcript
    if not transcript_doc_id:
        raise ValueError("No transcript document ID in workflow context")

    doc_result = await db.execute(
        select(MeetingDocument).where(MeetingDocument.id == uuid.UUID(transcript_doc_id))
    )
    transcript_doc = doc_result.scalar_one_or_none()
    if not transcript_doc or not transcript_doc.content:
        raise ValueError("Transcript document not found or empty")
    steps.append("transcript_loaded")

    # Step 2: Get template (try Google Doc first, fall back to default)
    fetched_template = await _fetch_template("notes_template_url")
    if fetched_template:
        template_text = fetched_template
        steps.append("template_fetched_from_google_doc")
    else:
        template_text = DEFAULT_NOTES_TEMPLATE.format(
            date=meeting_date, customer=customer.name
        )
        steps.append("template_default")

    # Step 3: Generate notes
    result = await generate_meeting_notes(
        customer_name=customer.name,
        meeting_date=meeting_date,
        transcript=transcript_doc.content,
        template_text=template_text,
    )
    steps.append("notes_generated")

    # Step 4: Store generated notes as a document
    notes_doc = MeetingDocument(
        customer_id=customer.id,
        document_type="notes",
        title=f"Notes — {customer.name} — {meeting_date}",
        content=result["notes"],
        meeting_date=datetime.fromisoformat(meeting_date) if meeting_date else None,
    )
    db.add(notes_doc)
    steps.append("notes_document_stored")

    # Step 5: Create approval item for notes
    approval = ApprovalItem(
        item_type=ApprovalItemType.MEETING_NOTES,
        status=ApprovalStatus.DRAFT,
        title=f"Meeting Notes — {customer.name} — {meeting_date}",
        content=result["notes"],
        customer_id=customer.id,
        workflow_id=workflow.id,
        meeting_date=datetime.fromisoformat(meeting_date) if meeting_date else None,
    )
    db.add(approval)
    await db.flush()
    steps.append("notes_approval_created")

    # Step 6: Create action items
    for ai in result.get("action_items", []):
        action_item = ActionItem(
            title=ai.get("title", "Untitled"),
            description=ai.get("description", ""),
            assignee=ai.get("assignee", ""),
            status=ApprovalStatus.DRAFT,
            approval_item_id=approval.id,
        )
        db.add(action_item)
    steps.append(f"action_items_created:{len(result.get('action_items', []))}")

    workflow.steps_completed = steps
    await db.flush()


async def _execute_health_update(
    workflow: Workflow, customer: Customer, db: AsyncSession
):
    """Execute the customer health update workflow."""
    context = workflow.context or {}
    steps = []

    # Gather context
    meeting_notes = context.get("meeting_notes", "")

    # Get recent issues summary
    issues_summary = ""
    try:
        if customer.linear_project_id:
            linear = LinearClient()
            issues = await linear.list_project_issues(customer.linear_project_id, limit=10)
            issues_summary = "\n".join(
                f"- [{t.get('identifier')}] {t.get('title')} ({t.get('state', {}).get('name', '')})"
                for t in issues
            )
        steps.append("issues_fetched")
    except Exception as e:
        logger.warning("workflow.health.issues_failed", error=str(e))
        steps.append("issues_skipped")

    # Generate health assessment
    result = await generate_health_assessment(
        customer_name=customer.name,
        meeting_notes=meeting_notes,
        open_issues_summary=issues_summary,
        previous_health_status=customer.health_status or "",
    )
    steps.append("health_generated")

    # Create approval item
    approval = ApprovalItem(
        item_type=ApprovalItemType.HEALTH_UPDATE,
        status=ApprovalStatus.DRAFT,
        title=f"Health Update — {customer.name}",
        content=result.get("summary", ""),
        customer_id=customer.id,
        workflow_id=workflow.id,
        metadata_json={
            "health_status": result.get("health_status", "green"),
            "key_risks": result.get("key_risks", ""),
            "opportunities": result.get("opportunities", ""),
        },
    )
    db.add(approval)
    steps.append("approval_created")

    workflow.steps_completed = steps
    await db.flush()


async def _get_tam_identity(customer: Customer, workspace: str) -> tuple[str | None, str | None]:
    """Look up the TAM's display name and profile photo for posting as them."""
    if not customer.tam_slack_user_id:
        return None, None
    try:
        slack = SlackClient(workspace)
        name = await slack.get_user_display_name(customer.tam_slack_user_id)
        photo = await slack.get_user_profile_photo(customer.tam_slack_user_id)
        return name, photo
    except Exception:
        return None, None


async def publish_approval_item(
    item: ApprovalItem,
    customer: Customer,
    db: AsyncSession,
    *,
    publish_external: bool = False,
):
    """Execute publish side effects for an approved item."""
    steps_done = []

    if item.item_type == ApprovalItemType.AGENDA:
        # Post to internal Slack
        if customer.slack_internal_channel_id and not item.published_to_slack_internal:
            try:
                slack = SlackClient("internal")
                tam_name, tam_photo = await _get_tam_identity(customer, "internal")
                date_str = item.meeting_date.strftime("%Y-%m-%d") if item.meeting_date else "TBD"
                blocks = slack.format_agenda_blocks(customer.name, date_str, item.content or "")
                await slack.post_message(
                    customer.slack_internal_channel_id,
                    text=f"Meeting Agenda: {customer.name} — {date_str}",
                    blocks=blocks,
                    username=tam_name,
                    icon_url=tam_photo,
                )
                item.published_to_slack_internal = True
                steps_done.append("slack_internal")
            except Exception as e:
                logger.error("publish.slack_internal_failed", error=str(e))

        # Post to external Slack (only when explicitly opted in)
        if publish_external and customer.slack_external_channel_id and not item.published_to_slack_external:
            try:
                slack = SlackClient("external")
                tam_name, tam_photo = await _get_tam_identity(customer, "external")
                date_str = item.meeting_date.strftime("%Y-%m-%d") if item.meeting_date else "TBD"
                blocks = slack.format_agenda_blocks(customer.name, date_str, item.content or "")
                await slack.post_message(
                    customer.slack_external_channel_id,
                    text=f"Meeting Agenda: {customer.name} — {date_str}",
                    blocks=blocks,
                    username=tam_name,
                    icon_url=tam_photo,
                )
                item.published_to_slack_external = True
                steps_done.append("slack_external")
            except Exception as e:
                logger.error("publish.slack_external_failed", error=str(e))

        # Create a draft Linear issue with the full agenda content
        try:
            date_str = item.meeting_date.strftime("%Y-%m-%d") if item.meeting_date else "TBD"
            agenda_action = ActionItem(
                title=f"Agenda: {customer.name} — {date_str}",
                description=item.content or "",
                status=ApprovalStatus.DRAFT,
                approval_item_id=item.id,
            )
            db.add(agenda_action)
            steps_done.append("agenda_issue_queued")
            logger.info("publish.agenda_issue_queued", customer=customer.name)
        except Exception as e:
            logger.error("publish.agenda_issue_failed", error=str(e))

    elif item.item_type == ApprovalItemType.MEETING_NOTES:
        # Post to internal Slack only
        if customer.slack_internal_channel_id and not item.published_to_slack_internal:
            try:
                slack = SlackClient("internal")
                tam_name, tam_photo = await _get_tam_identity(customer, "internal")
                date_str = item.meeting_date.strftime("%Y-%m-%d") if item.meeting_date else "TBD"
                blocks = slack.format_notes_blocks(customer.name, date_str, item.content or "")
                await slack.post_message(
                    customer.slack_internal_channel_id,
                    text=f"Meeting Notes: {customer.name} — {date_str}",
                    blocks=blocks,
                    username=tam_name,
                    icon_url=tam_photo,
                )
                item.published_to_slack_internal = True
                steps_done.append("slack_internal")
            except Exception as e:
                logger.error("publish.slack_internal_failed", error=str(e))

        # Queue action items for review in Linear Issues page (don't create in Linear yet)
        # Issues will be created in Linear when individually approved via /api/linear/issues/{id}/approve
        if item.action_items:
            steps_done.append("action_items_queued")
            logger.info("publish.action_items_queued", count=len(item.action_items))

        # Create a draft Linear issue with the full meeting notes content
        try:
            date_str = item.meeting_date.strftime("%Y-%m-%d") if item.meeting_date else "TBD"
            notes_action = ActionItem(
                title=f"Meeting Notes: {customer.name} — {date_str}",
                description=item.content or "",
                status=ApprovalStatus.DRAFT,
                approval_item_id=item.id,
            )
            db.add(notes_action)
            steps_done.append("notes_issue_queued")
            logger.info("publish.notes_issue_queued", customer=customer.name)
        except Exception as e:
            logger.error("publish.notes_issue_failed", error=str(e))

        # Auto-trigger health update generation after notes are published
        try:
            health_workflow = Workflow(
                workflow_type=WorkflowType.HEALTH_UPDATE,
                status=WorkflowStatus.PENDING,
                customer_id=customer.id,
                context={
                    "meeting_notes": item.content or "",
                    "meeting_date": item.meeting_date.isoformat() if item.meeting_date else None,
                    "triggered_by": "meeting_notes_publish",
                },
            )
            db.add(health_workflow)
            await db.flush()
            await _execute_health_update(health_workflow, customer, db)
            health_workflow.status = WorkflowStatus.COMPLETED
            steps_done.append("health_update_triggered")
            logger.info("publish.health_update_triggered", customer=customer.name)
        except Exception as e:
            logger.error("publish.health_trigger_failed", error=str(e))

    elif item.item_type == ApprovalItemType.HEALTH_UPDATE:
        # Update Notion
        if customer.notion_page_id and not item.published_to_notion:
            try:
                notion = NotionClient()
                meta = item.metadata_json or {}
                date_str = item.meeting_date.strftime("%Y-%m-%d") if item.meeting_date else None
                await notion.update_customer_health(
                    page_id=customer.notion_page_id,
                    health_status=meta.get("health_status", "green"),
                    summary=item.content or "",
                    last_meeting_date=date_str,
                    key_risks=meta.get("key_risks", ""),
                    opportunities=meta.get("opportunities", ""),
                )
                item.published_to_notion = True
                # Also update the customer model
                customer.health_status = meta.get("health_status", customer.health_status)
                customer.last_health_update = datetime.now(timezone.utc)
                steps_done.append("notion_updated")
            except Exception as e:
                logger.error("publish.notion_failed", error=str(e))

    item.published_at = datetime.now(timezone.utc)
    item.status = ApprovalStatus.PUBLISHED
    await db.flush()

    logger.info("publish.completed", item_id=str(item.id), steps=steps_done)
    return steps_done
