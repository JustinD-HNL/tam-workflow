"""Add Avoma integration support

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"


def upgrade() -> None:
    # Add 'avoma' to the integration_type_enum
    op.execute("ALTER TYPE integration_type_enum ADD VALUE IF NOT EXISTS 'avoma'")

    # Add source and external_meeting_id columns to meeting_documents
    op.add_column("meeting_documents", sa.Column("source", sa.String(50), nullable=True))
    op.add_column("meeting_documents", sa.Column("external_meeting_id", sa.String(255), nullable=True))

    # Index for dedup lookups
    op.create_index("ix_meeting_documents_external_meeting_id", "meeting_documents", ["external_meeting_id"])


def downgrade() -> None:
    op.drop_index("ix_meeting_documents_external_meeting_id", table_name="meeting_documents")
    op.drop_column("meeting_documents", "external_meeting_id")
    op.drop_column("meeting_documents", "source")
    # Note: PostgreSQL does not support removing values from an enum type
