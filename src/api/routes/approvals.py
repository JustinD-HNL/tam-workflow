"""Approval queue routes."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import ApprovalActionRequest, ApprovalItemResponse, ApprovalItemUpdate
from src.models.database import get_db
from src.models.workflow import ApprovalItem, ApprovalStatus

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


@router.get("/", response_model=list[ApprovalItemResponse])
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

    # If approving and publishing, trigger the publish workflow
    if action == "publish":
        # TODO: trigger publish side effects (Slack, Linear, etc.)
        pass

    await db.flush()
    await db.refresh(item)
    return item
