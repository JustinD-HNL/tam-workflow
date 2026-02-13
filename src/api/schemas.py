"""Pydantic schemas for API request/response validation."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- Customer ---
class CustomerCreate(BaseModel):
    name: str
    slug: str
    linear_project_id: Optional[str] = None
    slack_internal_channel_id: Optional[str] = None
    slack_external_channel_id: Optional[str] = None
    notion_page_id: Optional[str] = None
    google_calendar_event_pattern: Optional[str] = None
    google_docs_folder_id: Optional[str] = None
    tam_slack_user_id: Optional[str] = None
    primary_contacts: Optional[list] = []
    cadence: str = "weekly"
    linear_task_defaults: Optional[dict] = {}


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    linear_project_id: Optional[str] = None
    slack_internal_channel_id: Optional[str] = None
    slack_external_channel_id: Optional[str] = None
    notion_page_id: Optional[str] = None
    google_calendar_event_pattern: Optional[str] = None
    google_docs_folder_id: Optional[str] = None
    tam_slack_user_id: Optional[str] = None
    primary_contacts: Optional[list] = None
    cadence: Optional[str] = None
    health_status: Optional[str] = None
    linear_task_defaults: Optional[dict] = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    linear_project_id: Optional[str]
    slack_internal_channel_id: Optional[str]
    slack_external_channel_id: Optional[str]
    notion_page_id: Optional[str]
    google_calendar_event_pattern: Optional[str]
    google_docs_folder_id: Optional[str]
    tam_slack_user_id: Optional[str]
    primary_contacts: Optional[list]
    cadence: Optional[str]
    health_status: Optional[str]
    last_health_update: Optional[datetime]
    linear_task_defaults: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Approval Item ---
class ApprovalItemResponse(BaseModel):
    id: uuid.UUID
    item_type: str
    status: str
    title: str
    content: Optional[str]
    metadata_json: Optional[dict]
    customer_id: uuid.UUID
    workflow_id: Optional[uuid.UUID]
    google_doc_id: Optional[str]
    google_doc_url: Optional[str]
    linear_issue_id: Optional[str]
    published_to_slack_internal: bool
    published_to_slack_external: bool
    published_to_notion: bool
    published_to_linear: bool
    published_at: Optional[datetime]
    meeting_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalItemUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    meeting_date: Optional[datetime] = None
    metadata_json: Optional[dict] = None


class ApprovalActionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|publish|archive)$")


# --- Transcript ---
class TranscriptUpload(BaseModel):
    customer_id: uuid.UUID
    meeting_date: datetime
    transcript_text: str
    calendar_event_id: Optional[str] = None


# --- Workflow ---
class WorkflowResponse(BaseModel):
    id: uuid.UUID
    workflow_type: str
    status: str
    customer_id: uuid.UUID
    context: Optional[dict]
    steps_completed: Optional[list | dict]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Integration ---
class IntegrationStatusResponse(BaseModel):
    integration_type: str
    status: str
    last_verified: Optional[datetime]
    scopes: Optional[str]

    model_config = {"from_attributes": True}


class ManualTokenRequest(BaseModel):
    integration_type: str
    token: str


# --- Action Item ---
class ActionItemResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str]
    assignee: Optional[str]
    priority: Optional[str]
    status: str
    linear_issue_id: Optional[str]
    linear_issue_url: Optional[str]
    approval_item_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ActionItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None


# --- Slack Mention ---
class SlackMentionResponse(BaseModel):
    id: uuid.UUID
    customer_id: Optional[uuid.UUID]
    workspace: str
    channel_id: str
    channel_name: Optional[str]
    message_ts: str
    user_id: str
    user_name: Optional[str]
    message_text: str
    permalink: Optional[str]
    handled: bool
    linear_issue_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Health ---
class HealthUpdateRequest(BaseModel):
    customer_id: uuid.UUID
    health_status: str = Field(..., pattern="^(green|yellow|red)$")
    summary: Optional[str] = None


# --- Dashboard ---
class DashboardResponse(BaseModel):
    upcoming_meetings: list = []
    pending_approvals: int = 0
    recent_activity: list = []
    customer_health: list = []
