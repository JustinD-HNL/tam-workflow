"""Workflow management routes."""

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import WorkflowResponse
from src.models.customer import Customer
from src.models.database import get_db
from src.models.workflow import Workflow, WorkflowType, WorkflowStatus

logger = structlog.get_logger()

router = APIRouter()


class AgendaTriggerRequest(BaseModel):
    customer_id: uuid.UUID
    meeting_date: Optional[str] = None
    event_id: Optional[str] = None


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


@router.post("/agenda")
async def trigger_agenda_generation(
    data: AgendaTriggerRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger agenda generation for a customer. Gathers all available context resiliently."""
    # Verify customer exists
    cust_result = await db.execute(select(Customer).where(Customer.id == data.customer_id))
    customer = cust_result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    meeting_date = data.meeting_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    context = {"meeting_date": meeting_date}
    if data.event_id:
        context["event_id"] = data.event_id

    workflow = Workflow(
        workflow_type=WorkflowType.AGENDA_GENERATION,
        status=WorkflowStatus.PENDING,
        customer_id=data.customer_id,
        context=context,
    )
    db.add(workflow)
    await db.flush()

    # Execute immediately
    from src.orchestrator.workflows import execute_workflow
    await execute_workflow(workflow.id, db)

    await db.refresh(workflow)
    return {
        "id": str(workflow.id),
        "status": workflow.status.value if hasattr(workflow.status, "value") else str(workflow.status),
        "error_message": workflow.error_message,
        "workflow_type": workflow.workflow_type.value if hasattr(workflow.workflow_type, "value") else str(workflow.workflow_type),
        "steps_completed": workflow.steps_completed,
    }


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
