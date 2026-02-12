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


@router.post("/mentions/{mention_id}/create-ticket")
async def create_ticket_from_mention(
    mention_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Create a Linear ticket from a Slack mention."""
    mention = await db.get(SlackMention, mention_id)
    if not mention:
        raise HTTPException(status_code=404, detail="Mention not found")
    raise HTTPException(
        status_code=503,
        detail="Linear integration not connected. Connect Linear in Settings to create tickets from mentions.",
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
    return {"id": str(mention.id), "handled": True}
