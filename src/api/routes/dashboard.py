"""Dashboard API routes."""

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import get_db
from src.models.customer import Customer, HealthStatus
from src.models.workflow import ApprovalItem, ApprovalStatus, Workflow, WorkflowStatus

logger = structlog.get_logger()
router = APIRouter()


async def _fetch_upcoming_meetings(customers: list, days_ahead: int = 14) -> list[dict]:
    """Fetch upcoming customer meetings from Google Calendar.

    Only returns events that match a customer's google_calendar_event_pattern.
    """
    from src.integrations.google.calendar import GoogleCalendarClient

    # Build customer patterns — skip customers without a pattern
    customer_patterns = []
    for c in customers:
        if c.google_calendar_event_pattern:
            customer_patterns.append((c.name, c.google_calendar_event_pattern.strip().lower()))

    if not customer_patterns:
        return []

    try:
        calendar = GoogleCalendarClient()
        all_events = await calendar.list_upcoming_events(days_ahead=days_ahead)
    except Exception as e:
        logger.warning("dashboard.calendar_fetch_failed", error=str(e))
        return []

    meetings = []
    for event in all_events:
        summary = event.get("summary", "")
        start = event.get("start", {})
        start_time = start.get("dateTime", start.get("date", ""))

        # Only include events that match a customer pattern
        for cname, pattern in customer_patterns:
            if pattern in summary.lower():
                meetings.append({
                    "id": event.get("id", ""),
                    "summary": summary,
                    "start": start_time,
                    "customer_name": cname,
                })
                break

    return meetings


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

    # Get customers for calendar matching
    cust_result = await db.execute(select(Customer))
    customers = cust_result.scalars().all()

    # Fetch upcoming meetings from Google Calendar
    upcoming_meetings = await _fetch_upcoming_meetings(customers)

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
        "upcoming_meetings": upcoming_meetings,
        "pending_approvals": pending_approvals,
        "recent_activity": recent_activity,
        "customer_health": health_counts,
    }
