// ---- Enums ----

export type HealthStatus = 'green' | 'yellow' | 'red';

export type ApprovalStatus = 'draft' | 'in_review' | 'approved' | 'published' | 'rejected' | 'archived';

export type WorkflowType = 'agenda' | 'meeting_notes' | 'health_update';

export type IntegrationName = 'google' | 'slack_internal' | 'slack_external' | 'linear' | 'notion';

export type ConnectionStatus = 'connected' | 'disconnected' | 'expired';

export type Priority = 'none' | 'low' | 'medium' | 'high' | 'urgent';

// ---- Models ----

export interface Customer {
  id: string;
  name: string;
  slug: string;
  linear_project_id: string | null;
  slack_internal_channel_id: string | null;
  slack_external_channel_id: string | null;
  notion_page_id: string | null;
  google_calendar_event_pattern: string | null;
  google_docs_folder_id: string | null;
  tam_slack_user_id: string | null;
  primary_contacts: Contact[];
  cadence: string;
  health_status: HealthStatus;
  last_health_update: string | null;
  linear_task_defaults: LinearTaskDefaults | null;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  name: string;
  email: string;
  role: string;
}

export interface LinearTaskDefaults {
  team_id: string;
  assignee_id: string;
  labels: string[];
  priority: Priority;
}

export interface ApprovalItem {
  id: string;
  item_type: string;
  status: ApprovalStatus;
  customer_id: string;
  customer_name?: string;
  title: string;
  content: string | null;
  metadata_json: Record<string, unknown> | null;
  workflow_id: string | null;
  google_doc_id: string | null;
  google_doc_url: string | null;
  linear_issue_id: string | null;
  published_to_slack_internal: boolean;
  published_to_slack_external: boolean;
  published_to_notion: boolean;
  published_to_linear: boolean;
  meeting_date: string | null;
  created_at: string;
  updated_at: string;
  published_at: string | null;
}

export interface ActionItem {
  id: string;
  approval_item_id: string;
  title: string;
  description: string;
  assignee: string | null;
  priority: Priority;
  linear_issue_id: string | null;
  linear_issue_url: string | null;
  completed: boolean;
  created_at: string;
}

export interface CalendarEvent {
  id: string;
  summary: string;
  start: string;
  end: string;
  customer_id: string | null;
  customer_name: string | null;
  zoom_link: string | null;
}

export interface IntegrationStatus {
  integration_type: string;
  status: ConnectionStatus;
  last_verified: string | null;
  scopes: string | null;
}

export interface SlackMention {
  id: string;
  workspace: string;
  channel_id: string;
  channel_name: string | null;
  customer_id: string | null;
  user_id: string;
  user_name: string | null;
  message_text: string;
  message_ts: string;
  permalink: string | null;
  linear_issue_id: string | null;
  handled: boolean;
  created_at: string;
}

export interface LinearIssue {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: Priority;
  assignee: string | null;
  customer_id: string | null;
  customer_name: string | null;
  labels: string[];
  linear_issue_id: string | null;
  linear_issue_url: string | null;
  source: 'meeting_notes' | 'slack_thread' | 'slack_mention' | 'manual' | 'agenda';
  approval_status: ApprovalStatus;
  created_at: string;
  updated_at: string;
}

export interface HealthUpdate {
  id: string;
  customer_id: string;
  customer_name: string;
  previous_status: HealthStatus;
  new_status: HealthStatus;
  summary: string;
  key_risks: string[];
  opportunities: string[];
  last_meeting_date: string | null;
  approval_status: ApprovalStatus;
  created_at: string;
  published_at: string | null;
}

export interface WorkflowRun {
  id: string;
  workflow_type: WorkflowType;
  customer_id: string;
  customer_name: string;
  status: 'running' | 'completed' | 'failed';
  current_step: string;
  steps_completed: number;
  total_steps: number;
  error: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface DashboardStats {
  upcoming_meetings: CalendarEvent[];
  pending_approvals: number;
  recent_activity: ActivityItem[];
  customer_health: {
    green: number;
    yellow: number;
    red: number;
  };
}

export interface ActivityItem {
  id: string;
  title: string;
  type: string;
  status: string;
  created_at: string | null;
}

export interface TemplateConfig {
  agenda_template_url: string | null;
  notes_template_url: string | null;
  agenda_template_last_fetched: string | null;
  notes_template_last_fetched: string | null;
}

// ---- API Responses ----

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface ResolveResult {
  valid: boolean;
  id: string | null;
  name: string | null;
  error: string | null;
  extra: Record<string, unknown> | null;
}

export interface ApiError {
  detail: string;
  status_code: number;
}
