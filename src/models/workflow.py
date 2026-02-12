"""Workflow and approval models."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class WorkflowType(str, enum.Enum):
    AGENDA_GENERATION = "agenda_generation"
    MEETING_NOTES = "meeting_notes"
    HEALTH_UPDATE = "health_update"
    SLACK_MONITORING = "slack_monitoring"


class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class ApprovalItemType(str, enum.Enum):
    AGENDA = "agenda"
    MEETING_NOTES = "meeting_notes"
    HEALTH_UPDATE = "health_update"
    LINEAR_TICKET = "linear_ticket"


class Workflow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflows"

    workflow_type: Mapped[str] = mapped_column(
        Enum(WorkflowType, name="workflow_type_enum", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=WorkflowStatus.PENDING,
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )

    # Workflow context and step tracking
    context: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    steps_completed: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="workflows")
    approval_items: Mapped[list["ApprovalItem"]] = relationship(back_populates="workflow")


class ApprovalItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "approval_items"

    item_type: Mapped[str] = mapped_column(
        Enum(ApprovalItemType, name="approval_item_type_enum", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(ApprovalStatus, name="approval_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=ApprovalStatus.DRAFT,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Links
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    workflow_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id")
    )
    google_doc_id: Mapped[Optional[str]] = mapped_column(String(255))
    google_doc_url: Mapped[Optional[str]] = mapped_column(String(500))
    linear_issue_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Publishing tracking
    published_to_slack_internal: Mapped[bool] = mapped_column(default=False)
    published_to_slack_external: Mapped[bool] = mapped_column(default=False)
    published_to_notion: Mapped[bool] = mapped_column(default=False)
    published_to_linear: Mapped[bool] = mapped_column(default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Meeting reference
    meeting_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    calendar_event_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="approval_items")
    workflow: Mapped[Optional["Workflow"]] = relationship(back_populates="approval_items")
    action_items: Mapped[list["ActionItem"]] = relationship(back_populates="approval_item")


class ActionItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "action_items"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    assignee: Mapped[Optional[str]] = mapped_column(String(255))
    priority: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(
        Enum(ApprovalStatus, name="approval_status_enum", values_callable=lambda x: [e.value for e in x], create_type=False),
        default=ApprovalStatus.DRAFT,
        nullable=False,
    )
    linear_issue_id: Mapped[Optional[str]] = mapped_column(String(255))
    linear_issue_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Parent
    approval_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_items.id"), nullable=False
    )

    # Relationships
    approval_item: Mapped["ApprovalItem"] = relationship(back_populates="action_items")
