"""Linear ticket API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import get_db
from src.models.workflow import ApprovalItem, ApprovalItemType, ApprovalStatus

router = APIRouter()


@router.get("/tickets")
async def list_tickets(
    customer_id: str | None = None,
    status: str | None = None,
    approval_status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List Linear ticket approval items."""
    query = (
        select(ApprovalItem)
        .where(ApprovalItem.item_type == ApprovalItemType.LINEAR_TICKET)
        .order_by(ApprovalItem.created_at.desc())
    )
    if customer_id:
        query = query.where(ApprovalItem.customer_id == uuid.UUID(customer_id))
    if approval_status:
        query = query.where(ApprovalItem.status == approval_status)
    result = await db.execute(query)
    items = result.scalars().all()
    return [
        {
            "id": str(item.id),
            "title": item.title,
            "description": item.content,
            "status": item.status.value if hasattr(item.status, "value") else str(item.status),
            "customer_id": str(item.customer_id),
            "linear_issue_id": item.linear_issue_id,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items
    ]


@router.post("/tickets")
async def create_ticket(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """Create a Linear ticket (queued for approval)."""
    customer_id = data.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=422, detail="customer_id is required")
    item = ApprovalItem(
        item_type=ApprovalItemType.LINEAR_TICKET,
        status=ApprovalStatus.DRAFT,
        title=data.get("title", "New Linear Ticket"),
        content=data.get("description", ""),
        customer_id=uuid.UUID(customer_id),
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return {
        "id": str(item.id),
        "title": item.title,
        "description": item.content,
        "status": str(item.status.value if hasattr(item.status, "value") else item.status),
        "customer_id": str(item.customer_id),
    }
