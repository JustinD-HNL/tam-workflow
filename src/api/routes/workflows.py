"""Workflow management routes."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import WorkflowResponse
from src.models.database import get_db
from src.models.workflow import Workflow

router = APIRouter()


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    status: Optional[str] = Query(None),
    workflow_type: Optional[str] = Query(None),
    customer_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List workflows with optional filters."""
    query = select(Workflow).order_by(Workflow.created_at.desc())
    if status:
        query = query.where(Workflow.status == status)
    if workflow_type:
        query = query.where(Workflow.workflow_type == workflow_type)
    if customer_id:
        query = query.where(Workflow.customer_id == customer_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single workflow."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.post("/{workflow_id}/retry", response_model=WorkflowResponse)
async def retry_workflow(workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Retry a failed workflow."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed workflows can be retried")

    workflow.status = "pending"
    workflow.error_message = None
    await db.flush()
    await db.refresh(workflow)

    # TODO: trigger workflow execution
    return workflow
