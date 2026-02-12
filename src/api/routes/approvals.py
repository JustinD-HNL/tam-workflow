"""Approval queue routes."""

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas import ApprovalActionRequest, ApprovalItemResponse, ApprovalItemUpdate
from src.models.customer import Customer
from src.models.database import get_db
from src.models.workflow import ApprovalItem, ApprovalStatus

logger = structlog.get_logger()

router = APIRouter()

# Valid state transitions
TRANSITIONS = {
    "approve": {
        ApprovalStatus.DRAFT: ApprovalStatus.APPROVED,
        ApprovalStatus.IN_REVIEW: ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED: ApprovalStatus.APPROVED,
    },
    "reject": {
        ApprovalStatus.DRAFT: ApprovalStatus.REJECTED,
        ApprovalStatus.IN_REVIEW: ApprovalStatus.REJECTED,
    },
    "publish": {
        ApprovalStatus.APPROVED: ApprovalStatus.PUBLISHED,
    },
    "archive": {
        ApprovalStatus.PUBLISHED: ApprovalStatus.ARCHIVED,
    },
}


@router.get("", response_model=list[ApprovalItemResponse])
async def list_approvals(
    status: Optional[str] = Query(None),
    item_type: Optional[str] = Query(None),
    customer_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List approval items with optional filters."""
    query = select(ApprovalItem).order_by(ApprovalItem.created_at.desc())
    if status:
        query = query.where(ApprovalItem.status == status)
    if item_type:
        query = query.where(ApprovalItem.item_type == item_type)
    if customer_id:
        query = query.where(ApprovalItem.customer_id == customer_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{item_id}", response_model=ApprovalItemResponse)
async def get_approval(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single approval item."""
    result = await db.execute(select(ApprovalItem).where(ApprovalItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Approval item not found")
    return item


@router.patch("/{item_id}", response_model=ApprovalItemResponse)
async def update_approval(
    item_id: uuid.UUID,
    data: ApprovalItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an approval item (edit content, title, etc.)."""
    result = await db.execute(select(ApprovalItem).where(ApprovalItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Approval item not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    await db.flush()
    await db.refresh(item)
    return item


@router.post("/{item_id}/action", response_model=ApprovalItemResponse)
async def perform_action(
    item_id: uuid.UUID,
    action_req: ApprovalActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Perform an action (approve, reject, publish, archive) on an approval item."""
    result = await db.execute(select(ApprovalItem).where(ApprovalItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Approval item not found")

    action = action_req.action
    current_status = ApprovalStatus(item.status)
    transitions = TRANSITIONS.get(action, {})
    new_status = transitions.get(current_status)

    if new_status is None:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot {action} item with status '{item.status}'",
        )

    item.status = new_status

    if new_status == ApprovalStatus.PUBLISHED:
        item.published_at = datetime.now(timezone.utc)

    await db.flush()

    # Trigger publish side effects when transitioning to PUBLISHED
    if new_status == ApprovalStatus.PUBLISHED:
        await _run_publish(item, db)

    await db.refresh(item)
    return item


@router.post("/{item_id}/approve", response_model=ApprovalItemResponse)
async def approve_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Approve an item."""
    item = await db.get(ApprovalItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    from src.orchestrator.state_machine import can_transition, get_next_status
    if not can_transition(item.status, "approve"):
        raise HTTPException(status_code=400, detail=f"Cannot approve item in {item.status} status")
    item.status = get_next_status(item.status, "approve")
    await db.flush()
    await db.refresh(item)
    return item


@router.post("/{item_id}/publish", response_model=ApprovalItemResponse)
async def publish_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Approve and publish an item."""
    item = await db.get(ApprovalItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    from src.orchestrator.state_machine import can_transition, get_next_status
    # First approve if needed
    if can_transition(item.status, "approve"):
        item.status = get_next_status(item.status, "approve")
    # Then publish
    if can_transition(item.status, "publish"):
        item.status = get_next_status(item.status, "publish")
        item.published_at = datetime.now(timezone.utc)
    else:
        raise HTTPException(status_code=400, detail=f"Cannot publish item in {item.status} status")
    await db.flush()

    # Trigger publish side effects
    await _run_publish(item, db)

    await db.refresh(item)
    return item


@router.post("/{item_id}/reject", response_model=ApprovalItemResponse)
async def reject_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Reject an item."""
    item = await db.get(ApprovalItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    from src.orchestrator.state_machine import can_transition, get_next_status
    if not can_transition(item.status, "reject"):
        raise HTTPException(status_code=400, detail=f"Cannot reject item in {item.status} status")
    item.status = get_next_status(item.status, "reject")
    await db.flush()
    await db.refresh(item)
    return item


@router.post("/{item_id}/copy")
async def copy_item_content(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get item content for clipboard copy."""
    item = await db.get(ApprovalItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"content": item.content or ""}


async def _run_publish(item: ApprovalItem, db: AsyncSession):
    """Run publish side effects (Slack, Linear, Notion) for an approval item."""
    from src.orchestrator.workflows import publish_approval_item

    # Load customer
    cust_result = await db.execute(select(Customer).where(Customer.id == item.customer_id))
    customer = cust_result.scalar_one_or_none()
    if not customer:
        logger.error("publish.customer_not_found", item_id=str(item.id))
        return

    # Load action items relationship for meeting notes
    item_result = await db.execute(
        select(ApprovalItem)
        .options(selectinload(ApprovalItem.action_items))
        .where(ApprovalItem.id == item.id)
    )
    item_with_actions = item_result.scalar_one()

    try:
        steps = await publish_approval_item(item_with_actions, customer, db)
        logger.info("publish.side_effects_complete", item_id=str(item.id), steps=steps)
    except Exception as e:
        logger.error("publish.side_effects_failed", item_id=str(item.id), error=str(e))
