"""Customer health dashboard routes."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas import HealthUpdateRequest
from src.models.customer import Customer, HealthStatus
from src.models.database import get_db
from src.models.workflow import ApprovalItem, ApprovalItemType, ApprovalStatus

router = APIRouter()


def _format_health_item(item: ApprovalItem) -> dict:
    """Format an ApprovalItem (health_update) into the shape the frontend expects."""
    metadata = item.metadata_json or {}
    customer_name = item.customer.name if item.customer else None
    return {
        "id": str(item.id),
        "customer_id": str(item.customer_id),
        "customer_name": customer_name,
        "previous_status": metadata.get("previous_status"),
        "new_status": metadata.get("health_status"),
        "summary": item.content,
        "key_risks": metadata.get("key_risks"),
        "opportunities": metadata.get("opportunities"),
        "last_meeting_date": item.meeting_date.isoformat() if item.meeting_date else None,
        "approval_status": item.status.value if hasattr(item.status, "value") else str(item.status),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }


@router.get("")
async def list_health_updates(
    customer_id: Optional[uuid.UUID] = Query(None),
    approval_status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List health update approval items with optional filters."""
    query = (
        select(ApprovalItem)
        .options(selectinload(ApprovalItem.customer))
        .where(ApprovalItem.item_type == ApprovalItemType.HEALTH_UPDATE)
        .order_by(ApprovalItem.created_at.desc())
    )
    if customer_id:
        query = query.where(ApprovalItem.customer_id == customer_id)
    if approval_status:
        query = query.where(ApprovalItem.status == approval_status)
    result = await db.execute(query)
    items = result.scalars().all()
    return [_format_health_item(item) for item in items]


@router.get("/history/{customer_id}")
async def get_health_history(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get health update history for a specific customer."""
    query = (
        select(ApprovalItem)
        .options(selectinload(ApprovalItem.customer))
        .where(
            ApprovalItem.item_type == ApprovalItemType.HEALTH_UPDATE,
            ApprovalItem.customer_id == customer_id,
        )
        .order_by(ApprovalItem.created_at.desc())
    )
    result = await db.execute(query)
    items = result.scalars().all()
    return [_format_health_item(item) for item in items]


@router.get("/dashboard")
async def health_dashboard(db: AsyncSession = Depends(get_db)):
    """Get health overview for all customers."""
    result = await db.execute(select(Customer).order_by(Customer.name))
    customers = result.scalars().all()

    # Get pending health updates
    pending_result = await db.execute(
        select(ApprovalItem).where(
            ApprovalItem.item_type == ApprovalItemType.HEALTH_UPDATE,
            ApprovalItem.status.in_([ApprovalStatus.DRAFT, ApprovalStatus.IN_REVIEW]),
        )
    )
    pending_updates = pending_result.scalars().all()

    return {
        "customers": [
            {
                "id": str(c.id),
                "name": c.name,
                "slug": c.slug,
                "health_status": c.health_status,
                "last_health_update": c.last_health_update,
            }
            for c in customers
        ],
        "pending_updates": [
            {
                "id": str(p.id),
                "customer_id": str(p.customer_id),
                "title": p.title,
                "status": p.status,
                "content": p.content,
            }
            for p in pending_updates
        ],
    }


@router.post("/update")
async def request_health_update(
    data: HealthUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a health update for approval."""
    result = await db.execute(select(Customer).where(Customer.id == data.customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    item = ApprovalItem(
        item_type=ApprovalItemType.HEALTH_UPDATE,
        status=ApprovalStatus.DRAFT,
        title=f"Health Update — {customer.name}",
        content=data.summary,
        customer_id=data.customer_id,
        metadata_json={"health_status": data.health_status},
    )
    db.add(item)
    await db.flush()

    return {
        "message": "Health update queued for approval",
        "approval_item_id": str(item.id),
    }
