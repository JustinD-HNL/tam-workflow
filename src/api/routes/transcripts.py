"""Transcript upload and processing routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import TranscriptUpload
from src.models.customer import Customer
from src.models.database import get_db
from src.models.integration import MeetingDocument
from src.models.workflow import ApprovalItem, ApprovalItemType, ApprovalStatus, Workflow, WorkflowType, WorkflowStatus

router = APIRouter()


@router.post("/upload")
async def upload_transcript(
    customer_id: str = Form(...),
    meeting_date: str = Form(...),
    transcript_text: str = Form(None),
    calendar_event_id: str = Form(None),
    file: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a transcript file or paste transcript text."""
    if not transcript_text and not file:
        raise HTTPException(status_code=400, detail="Provide either transcript_text or a file")

    cust_id = uuid.UUID(customer_id)

    # Verify customer exists
    result = await db.execute(select(Customer).where(Customer.id == cust_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Parse text from file if provided
    content = transcript_text
    if file and not content:
        raw = await file.read()
        filename = file.filename or ""
        if filename.endswith(".txt"):
            content = raw.decode("utf-8")
        elif filename.endswith(".pdf"):
            from src.transcript.parser import parse_pdf
            content = parse_pdf(raw)
        elif filename.endswith(".docx"):
            from src.transcript.parser import parse_docx
            content = parse_docx(raw)
        else:
            content = raw.decode("utf-8", errors="replace")

    meeting_dt = datetime.fromisoformat(meeting_date).replace(tzinfo=timezone.utc)

    # Store the transcript (generate UUID explicitly so we can reference it before flush)
    doc_id = uuid.uuid4()
    doc = MeetingDocument(
        id=doc_id,
        customer_id=cust_id,
        document_type="transcript",
        title=f"Transcript — {customer.name} — {meeting_dt.strftime('%Y-%m-%d')}",
        content=content,
        meeting_date=meeting_dt,
        calendar_event_id=calendar_event_id,
    )
    db.add(doc)

    # Create a workflow for meeting notes generation
    workflow = Workflow(
        workflow_type=WorkflowType.MEETING_NOTES,
        status=WorkflowStatus.PENDING,
        customer_id=cust_id,
        context={"transcript_document_id": str(doc_id), "meeting_date": meeting_date},
    )
    db.add(workflow)

    await db.flush()

    return {
        "message": "Transcript uploaded successfully",
        "document_id": str(doc.id),
        "workflow_id": str(workflow.id),
        "customer": customer.name,
        "meeting_date": meeting_date,
    }


@router.post("/paste")
async def paste_transcript(
    data: TranscriptUpload,
    db: AsyncSession = Depends(get_db),
):
    """Submit pasted transcript text."""
    # Verify customer exists
    result = await db.execute(select(Customer).where(Customer.id == data.customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    meeting_dt = data.meeting_date.replace(tzinfo=timezone.utc) if data.meeting_date.tzinfo is None else data.meeting_date

    # Store the transcript (generate UUID explicitly so we can reference it before flush)
    doc_id = uuid.uuid4()
    doc = MeetingDocument(
        id=doc_id,
        customer_id=data.customer_id,
        document_type="transcript",
        title=f"Transcript — {customer.name} — {meeting_dt.strftime('%Y-%m-%d')}",
        content=data.transcript_text,
        meeting_date=meeting_dt,
        calendar_event_id=data.calendar_event_id,
    )
    db.add(doc)

    # Create a workflow
    workflow = Workflow(
        workflow_type=WorkflowType.MEETING_NOTES,
        status=WorkflowStatus.PENDING,
        customer_id=data.customer_id,
        context={"transcript_document_id": str(doc_id), "meeting_date": str(meeting_dt)},
    )
    db.add(workflow)

    await db.flush()

    return {
        "message": "Transcript submitted successfully",
        "document_id": str(doc.id),
        "workflow_id": str(workflow.id),
    }
