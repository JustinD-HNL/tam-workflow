"""Customer health dashboard routes."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import HealthUpdateRequest
from src.models.customer import Customer, HealthStatus
from src.models.database import get_db
from src.models.workflow import ApprovalItem, ApprovalItemType, ApprovalStatus

router = APIRouter()


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
