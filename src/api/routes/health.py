"""Customer health dashboard routes."""

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas import HealthUpdateRequest
from src.models.customer import Customer, HealthStatus
from src.models.database import get_db
from src.models.workflow import (
    ApprovalItem,
    ApprovalItemType,
    ApprovalStatus,
    Workflow,
    WorkflowStatus,
    WorkflowType,
)

logger = structlog.get_logger()
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


@router.get("/notion/{customer_id}")
async def get_notion_health_page(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetch the current content of a customer's Notion health page."""
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not customer.notion_page_id:
        return {"content": None, "message": "No Notion page configured for this customer."}

    try:
        from src.integrations.notion.client import NotionClient

        notion = NotionClient()
        page = await notion.get_page(customer.notion_page_id)
        title = NotionClient.extract_page_title(page)
        text = await notion.get_page_text(customer.notion_page_id)
        return {
            "content": text,
            "title": title,
            "page_id": customer.notion_page_id,
            "url": f"https://www.notion.so/{customer.notion_page_id.replace('-', '')}",
        }
    except Exception as e:
        logger.error("health.notion_fetch_failed", customer=customer.name, error=str(e))
        raise HTTPException(status_code=502, detail=f"Failed to fetch Notion page: {str(e)}")


@router.post("/generate/{customer_id}")
async def generate_health_update(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generate an AI health update for a customer based on recent context.

    Pulls context from recent meeting notes, Linear issues, and Slack mentions,
    then generates a health assessment for review.
    """
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Gather context: most recent published meeting notes
    notes_result = await db.execute(
        select(ApprovalItem)
        .where(
            ApprovalItem.customer_id == customer_id,
            ApprovalItem.item_type == ApprovalItemType.MEETING_NOTES,
            ApprovalItem.status == ApprovalStatus.PUBLISHED,
        )
        .order_by(ApprovalItem.created_at.desc())
        .limit(1)
    )
    recent_notes = notes_result.scalar_one_or_none()
    meeting_notes = recent_notes.content if recent_notes else ""
    meeting_date = recent_notes.meeting_date.isoformat() if recent_notes and recent_notes.meeting_date else None

    try:
        # Create and execute health update workflow
        workflow = Workflow(
            workflow_type=WorkflowType.HEALTH_UPDATE,
            status=WorkflowStatus.PENDING,
            customer_id=customer.id,
            context={
                "meeting_notes": meeting_notes,
                "meeting_date": meeting_date,
                "triggered_by": "manual_generate",
            },
        )
        db.add(workflow)
        await db.flush()

        from src.orchestrator.workflows import _execute_health_update

        await _execute_health_update(workflow, customer, db)
        workflow.status = WorkflowStatus.COMPLETED
        await db.flush()

        return {
            "message": f"Health update generated for {customer.name}",
            "status": "success",
        }
    except Exception as e:
        logger.error("health.generate_failed", customer=customer.name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Health update generation failed: {str(e)}")
