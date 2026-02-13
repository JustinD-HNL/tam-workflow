"""Slack-related API routes."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.customer import Customer
from src.models.database import get_db
from src.models.integration import SlackMention
from src.models.workflow import ActionItem, ApprovalItem, ApprovalItemType, ApprovalStatus

logger = structlog.get_logger()

router = APIRouter()


@router.get("/mentions")
async def list_mentions(
    customer_id: str | None = None,
    handled: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List Slack mentions with optional filters."""
    query = select(SlackMention).order_by(SlackMention.created_at.desc())
    if customer_id:
        query = query.where(SlackMention.customer_id == uuid.UUID(customer_id))
    if handled is not None:
        query = query.where(SlackMention.handled == handled)
    result = await db.execute(query)
    mentions = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "customer_id": str(m.customer_id) if m.customer_id else None,
            "workspace": m.workspace,
            "channel_id": m.channel_id,
            "channel_name": m.channel_name,
            "message_ts": m.message_ts,
            "thread_ts": m.thread_ts,
            "user_id": m.user_id,
            "user_name": m.user_name,
            "message_text": m.message_text,
            "permalink": m.permalink,
            "handled": m.handled,
            "linear_issue_id": m.linear_issue_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
        for m in mentions
    ]


@router.post("/mentions/{mention_id}/create-issue")
async def create_issue_from_mention(
    mention_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Create a draft Linear issue from a Slack mention for review/approval."""
    mention = await db.get(SlackMention, mention_id)
    if not mention:
        raise HTTPException(status_code=404, detail="Mention not found")

    if mention.linear_issue_id:
        raise HTTPException(status_code=400, detail="Issue already created from this mention")

    # Load customer for context
    customer = None
    if mention.customer_id:
        customer = await db.get(Customer, mention.customer_id)

    customer_name = customer.name if customer else "Unknown"
    source_info = f"Slack mention in #{mention.channel_name or mention.channel_id} ({mention.workspace})"
    if mention.permalink:
        source_info = f"[Slack mention in #{mention.channel_name or mention.channel_id}]({mention.permalink})"

    description = f"**Source:** {source_info}\n**From:** {mention.user_name or mention.user_id}\n\n{mention.message_text}"

    # Create parent ApprovalItem
    approval_item = ApprovalItem(
        item_type=ApprovalItemType.LINEAR_ISSUE,
        status=ApprovalStatus.DRAFT,
        title=f"Slack mention: {customer_name}",
        content=mention.message_text[:2000],
        customer_id=mention.customer_id,
    )
    db.add(approval_item)
    await db.flush()

    # Create ActionItem (draft Linear issue)
    action_item = ActionItem(
        title=f"Slack mention: {customer_name} — {mention.user_name or mention.user_id}",
        description=description,
        status=ApprovalStatus.DRAFT,
        approval_item_id=approval_item.id,
    )
    db.add(action_item)

    # Mark mention as handled
    mention.handled = True
    await db.flush()

    logger.info("slack.issue_created_from_mention", mention_id=str(mention_id), customer=customer_name)

    return {
        "id": str(action_item.id),
        "title": action_item.title,
        "description": action_item.description,
        "status": "draft",
        "message": "Draft issue created — review and approve it in Linear Issues.",
    }


@router.post("/mentions/{mention_id}/handled")
async def mark_mention_handled(
    mention_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Mark a Slack mention as handled."""
    mention = await db.get(SlackMention, mention_id)
    if not mention:
        raise HTTPException(status_code=404, detail="Mention not found")
    mention.handled = True
    await db.flush()
    await db.refresh(mention)
    return {
        "id": str(mention.id),
        "customer_id": str(mention.customer_id) if mention.customer_id else None,
        "workspace": mention.workspace,
        "channel_id": mention.channel_id,
        "channel_name": mention.channel_name,
        "message_ts": mention.message_ts,
        "thread_ts": mention.thread_ts,
        "user_id": mention.user_id,
        "user_name": mention.user_name,
        "message_text": mention.message_text,
        "permalink": mention.permalink,
        "handled": mention.handled,
        "linear_issue_id": mention.linear_issue_id,
        "created_at": mention.created_at.isoformat() if mention.created_at else None,
        "updated_at": mention.updated_at.isoformat() if mention.updated_at else None,
    }
