"""Dashboard API routes."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import get_db
from src.models.customer import Customer, HealthStatus
from src.models.workflow import ApprovalItem, ApprovalStatus, Workflow, WorkflowStatus

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Get dashboard overview stats."""
    # Pending approvals count
    pending_result = await db.execute(
        select(func.count(ApprovalItem.id)).where(
            ApprovalItem.status.in_([ApprovalStatus.DRAFT, ApprovalStatus.IN_REVIEW])
        )
    )
    pending_approvals = pending_result.scalar() or 0

    # Customer health breakdown
    health_result = await db.execute(
        select(Customer.health_status, func.count(Customer.id)).group_by(Customer.health_status)
    )
    health_counts = {"green": 0, "yellow": 0, "red": 0}
    for status, count in health_result.all():
        if status:
            health_counts[status.value if hasattr(status, 'value') else str(status)] = count

    # Recent activity (last 10 approval items)
    recent_result = await db.execute(
        select(ApprovalItem)
        .order_by(ApprovalItem.created_at.desc())
        .limit(10)
    )
    recent_items = recent_result.scalars().all()
    recent_activity = [
        {
            "id": str(item.id),
            "title": item.title,
            "type": item.item_type.value if hasattr(item.item_type, 'value') else str(item.item_type),
            "status": item.status.value if hasattr(item.status, 'value') else str(item.status),
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in recent_items
    ]

    return {
        "upcoming_meetings": [],  # Requires Google Calendar integration to be connected
        "pending_approvals": pending_approvals,
        "recent_activity": recent_activity,
        "customer_health": health_counts,
    }
