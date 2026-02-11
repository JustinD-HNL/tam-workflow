"""Initial schema — all core tables.

Revision ID: 001
Revises:
Create Date: 2025-02-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enums
    cadence_enum = postgresql.ENUM("weekly", "biweekly", "monthly", name="cadence_enum", create_type=False)
    health_status_enum = postgresql.ENUM("green", "yellow", "red", name="health_status_enum", create_type=False)
    workflow_type_enum = postgresql.ENUM(
        "agenda_generation", "meeting_notes", "health_update", "slack_monitoring",
        name="workflow_type_enum", create_type=False,
    )
    workflow_status_enum = postgresql.ENUM(
        "pending", "running", "completed", "failed",
        name="workflow_status_enum", create_type=False,
    )
    approval_status_enum = postgresql.ENUM(
        "draft", "in_review", "approved", "published", "archived", "rejected",
        name="approval_status_enum", create_type=False,
    )
    approval_item_type_enum = postgresql.ENUM(
        "agenda", "meeting_notes", "health_update", "linear_ticket",
        name="approval_item_type_enum", create_type=False,
    )
    integration_type_enum = postgresql.ENUM(
        "google", "slack_internal", "slack_external", "linear", "notion",
        name="integration_type_enum", create_type=False,
    )
    integration_status_enum = postgresql.ENUM(
        "connected", "disconnected", "expired",
        name="integration_status_enum", create_type=False,
    )

    # Create all enums
    cadence_enum.create(op.get_bind(), checkfirst=True)
    health_status_enum.create(op.get_bind(), checkfirst=True)
    workflow_type_enum.create(op.get_bind(), checkfirst=True)
    workflow_status_enum.create(op.get_bind(), checkfirst=True)
    approval_status_enum.create(op.get_bind(), checkfirst=True)
    approval_item_type_enum.create(op.get_bind(), checkfirst=True)
    integration_type_enum.create(op.get_bind(), checkfirst=True)
    integration_status_enum.create(op.get_bind(), checkfirst=True)

    # Customers
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("linear_project_id", sa.String(255)),
        sa.Column("slack_internal_channel_id", sa.String(255)),
        sa.Column("slack_external_channel_id", sa.String(255)),
        sa.Column("notion_page_id", sa.String(255)),
        sa.Column("google_calendar_event_pattern", sa.String(500)),
        sa.Column("google_docs_folder_id", sa.String(255)),
        sa.Column("tam_slack_user_id", sa.String(255)),
        sa.Column("primary_contacts", postgresql.JSONB, server_default="[]"),
        sa.Column("cadence", cadence_enum, server_default="weekly"),
        sa.Column("health_status", health_status_enum, server_default="green"),
        sa.Column("last_health_update", sa.DateTime(timezone=True)),
        sa.Column("linear_task_defaults", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customers_slug", "customers", ["slug"])

    # Workflows
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workflow_type", workflow_type_enum, nullable=False),
        sa.Column("status", workflow_status_enum, nullable=False, server_default="pending"),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("context", postgresql.JSONB, server_default="{}"),
        sa.Column("steps_completed", postgresql.JSONB, server_default="[]"),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Approval Items
    op.create_table(
        "approval_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("item_type", approval_item_type_enum, nullable=False),
        sa.Column("status", approval_status_enum, nullable=False, server_default="draft"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("metadata_json", postgresql.JSONB, server_default="{}"),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id")),
        sa.Column("google_doc_id", sa.String(255)),
        sa.Column("google_doc_url", sa.String(500)),
        sa.Column("linear_issue_id", sa.String(255)),
        sa.Column("published_to_slack_internal", sa.Boolean, server_default="false"),
        sa.Column("published_to_slack_external", sa.Boolean, server_default="false"),
        sa.Column("published_to_notion", sa.Boolean, server_default="false"),
        sa.Column("published_to_linear", sa.Boolean, server_default="false"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("meeting_date", sa.DateTime(timezone=True)),
        sa.Column("calendar_event_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_approval_items_status", "approval_items", ["status"])

    # Action Items
    op.create_table(
        "action_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("assignee", sa.String(255)),
        sa.Column("priority", sa.String(50)),
        sa.Column("status", approval_status_enum, nullable=False, server_default="draft"),
        sa.Column("linear_issue_id", sa.String(255)),
        sa.Column("linear_issue_url", sa.String(500)),
        sa.Column("approval_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approval_items.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Integration Credentials
    op.create_table(
        "integration_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("integration_type", integration_type_enum, unique=True, nullable=False),
        sa.Column("status", integration_status_enum, nullable=False, server_default="disconnected"),
        sa.Column("access_token_encrypted", sa.Text),
        sa.Column("refresh_token_encrypted", sa.Text),
        sa.Column("token_type", sa.String(50)),
        sa.Column("scopes", sa.Text),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_verified", sa.DateTime(timezone=True)),
        sa.Column("extra_data", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Meeting Documents
    op.create_table(
        "meeting_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("file_path", sa.String(500)),
        sa.Column("meeting_date", sa.DateTime(timezone=True)),
        sa.Column("calendar_event_id", sa.String(255)),
        sa.Column("google_doc_id", sa.String(255)),
        sa.Column("google_doc_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Slack Mentions
    op.create_table(
        "slack_mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("workspace", sa.String(50), nullable=False),
        sa.Column("channel_id", sa.String(255), nullable=False),
        sa.Column("channel_name", sa.String(255)),
        sa.Column("message_ts", sa.String(50), nullable=False),
        sa.Column("thread_ts", sa.String(50)),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("user_name", sa.String(255)),
        sa.Column("message_text", sa.Text, nullable=False),
        sa.Column("permalink", sa.String(500)),
        sa.Column("handled", sa.Boolean, server_default="false"),
        sa.Column("linear_issue_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("slack_mentions")
    op.drop_table("meeting_documents")
    op.drop_table("integration_credentials")
    op.drop_table("action_items")
    op.drop_table("approval_items")
    op.drop_table("workflows")
    op.drop_table("customers")

    # Drop enums
    for name in [
        "integration_status_enum", "integration_type_enum",
        "approval_item_type_enum", "approval_status_enum",
        "workflow_status_enum", "workflow_type_enum",
        "health_status_enum", "cadence_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {name}")
