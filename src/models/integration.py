"""Integration credential and Slack mention models."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class IntegrationType(str, enum.Enum):
    GOOGLE = "google"
    SLACK_INTERNAL = "slack_internal"
    SLACK_EXTERNAL = "slack_external"
    LINEAR = "linear"
    NOTION = "notion"
    AVOMA = "avoma"


class IntegrationStatus(str, enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    EXPIRED = "expired"


class IntegrationCredential(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_credentials"

    integration_type: Mapped[str] = mapped_column(
        Enum(IntegrationType, name="integration_type_enum", values_callable=lambda x: [e.value for e in x]),
        unique=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(IntegrationStatus, name="integration_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=IntegrationStatus.DISCONNECTED,
        nullable=False,
    )

    # Encrypted tokens
    access_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)

    # Token metadata
    token_type: Mapped[Optional[str]] = mapped_column(String(50))
    scopes: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Extra data (e.g., workspace info for Slack)
    extra_data: Mapped[Optional[str]] = mapped_column(Text)


class MeetingDocument(Base, UUIDMixin, TimestampMixin):
    """Stores uploaded transcripts and generated documents."""

    __tablename__ = "meeting_documents"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)  # transcript, agenda, notes
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    meeting_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    calendar_event_id: Mapped[Optional[str]] = mapped_column(String(255))
    google_doc_id: Mapped[Optional[str]] = mapped_column(String(255))
    google_doc_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Source tracking (for Avoma auto-pull and future integrations)
    source: Mapped[Optional[str]] = mapped_column(String(50))  # "manual", "avoma"
    external_meeting_id: Mapped[Optional[str]] = mapped_column(String(255))  # Avoma meeting UUID for dedup

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="meeting_documents")


class SlackMention(Base, UUIDMixin, TimestampMixin):
    """Tracks @mentions of the TAM in external Slack channels."""

    __tablename__ = "slack_mentions"

    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id")
    )
    workspace: Mapped[str] = mapped_column(String(50), nullable=False)  # internal, external
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_name: Mapped[Optional[str]] = mapped_column(String(255))
    message_ts: Mapped[str] = mapped_column(String(50), nullable=False)
    thread_ts: Mapped[Optional[str]] = mapped_column(String(50))
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_name: Mapped[Optional[str]] = mapped_column(String(255))
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    permalink: Mapped[Optional[str]] = mapped_column(String(500))

    # Status
    handled: Mapped[bool] = mapped_column(default=False)
    linear_issue_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship(back_populates="slack_mentions")
