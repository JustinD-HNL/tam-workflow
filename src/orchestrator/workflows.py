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

    # Step 5: Get template
    template_text = DEFAULT_AGENDA_TEMPLATE.format(
        date=meeting_date, customer=customer.name
    )
    steps.append("template_loaded")

    # Step 6: Generate agenda with all available context
    agenda_text = await generate_agenda(
        customer_name=customer.name,
        meeting_date=meeting_date,
        template_text=template_text,
        recent_issues=recent_issues,
        last_meeting_notes=last_notes[:5000],
        open_action_items=open_action_items,
        slack_activity_summary=slack_activity,
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

    # Step 2: Get template
    template_text = DEFAULT_NOTES_TEMPLATE.format(
        date=meeting_date, customer=customer.name
    )
    steps.append("template_loaded")

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


async def publish_approval_item(item: ApprovalItem, customer: Customer, db: AsyncSession):
    """Execute publish side effects for an approved item."""
    steps_done = []

    if item.item_type == ApprovalItemType.AGENDA:
        # Post to internal Slack
        if customer.slack_internal_channel_id and not item.published_to_slack_internal:
            try:
                slack = SlackClient("internal")
                date_str = item.meeting_date.strftime("%Y-%m-%d") if item.meeting_date else "TBD"
                blocks = slack.format_agenda_blocks(customer.name, date_str, item.content or "")
                await slack.post_message(
                    customer.slack_internal_channel_id,
                    text=f"Meeting Agenda: {customer.name} — {date_str}",
                    blocks=blocks,
                )
                item.published_to_slack_internal = True
                steps_done.append("slack_internal")
            except Exception as e:
                logger.error("publish.slack_internal_failed", error=str(e))

        # Post to external Slack
        if customer.slack_external_channel_id and not item.published_to_slack_external:
            try:
                slack = SlackClient("external")
                date_str = item.meeting_date.strftime("%Y-%m-%d") if item.meeting_date else "TBD"
                blocks = slack.format_agenda_blocks(customer.name, date_str, item.content or "")
                await slack.post_message(
                    customer.slack_external_channel_id,
                    text=f"Meeting Agenda: {customer.name} — {date_str}",
                    blocks=blocks,
                )
                item.published_to_slack_external = True
                steps_done.append("slack_external")
            except Exception as e:
                logger.error("publish.slack_external_failed", error=str(e))

    elif item.item_type == ApprovalItemType.MEETING_NOTES:
        # Post to internal Slack only
        if customer.slack_internal_channel_id and not item.published_to_slack_internal:
            try:
                slack = SlackClient("internal")
                date_str = item.meeting_date.strftime("%Y-%m-%d") if item.meeting_date else "TBD"
                blocks = slack.format_notes_blocks(customer.name, date_str, item.content or "")
                await slack.post_message(
                    customer.slack_internal_channel_id,
                    text=f"Meeting Notes: {customer.name} — {date_str}",
                    blocks=blocks,
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
