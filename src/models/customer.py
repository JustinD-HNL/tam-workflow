"""Customer model."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Enum, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class HealthStatus(str, enum.Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class Cadence(str, enum.Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class Customer(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Linear
    linear_project_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Slack
    slack_internal_channel_id: Mapped[Optional[str]] = mapped_column(String(255))
    slack_external_channel_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Notion
    notion_page_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Google
    google_calendar_event_pattern: Mapped[Optional[str]] = mapped_column(String(500))
    google_docs_folder_id: Mapped[Optional[str]] = mapped_column(String(255))

    # TAM
    tam_slack_user_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Contacts
    primary_contacts: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)

    # Meeting
    cadence: Mapped[Optional[str]] = mapped_column(
        Enum(Cadence, name="cadence_enum", values_callable=lambda x: [e.value for e in x]), default=Cadence.WEEKLY
    )

    # Health
    health_status: Mapped[Optional[str]] = mapped_column(
        Enum(HealthStatus, name="health_status_enum", values_callable=lambda x: [e.value for e in x]), default=HealthStatus.GREEN
    )
    last_health_update: Mapped[Optional[datetime]] = mapped_column()

    # Linear defaults
    linear_task_defaults: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    workflows: Mapped[list["Workflow"]] = relationship(back_populates="customer")
    approval_items: Mapped[list["ApprovalItem"]] = relationship(back_populates="customer")
    meeting_documents: Mapped[list["MeetingDocument"]] = relationship(back_populates="customer")
    slack_mentions: Mapped[list["SlackMention"]] = relationship(back_populates="customer")
