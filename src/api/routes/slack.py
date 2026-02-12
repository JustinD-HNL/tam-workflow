"""Slack-related API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import get_db
from src.models.integration import SlackMention

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
    """Create a Linear issue from a Slack mention."""
    mention = await db.get(SlackMention, mention_id)
    if not mention:
        raise HTTPException(status_code=404, detail="Mention not found")
    raise HTTPException(
        status_code=503,
        detail="Linear integration not connected. Connect Linear in Settings to create issues from mentions.",
    )


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
