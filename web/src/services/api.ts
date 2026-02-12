import axios, { type AxiosInstance, type AxiosError } from 'axios';
import type {
  Customer,
  ApprovalItem,
  CalendarEvent,
  IntegrationStatus,
  SlackMention,
  LinearTicket,
  HealthUpdate,
  DashboardStats,
  TemplateConfig,
  ApprovalStatus,
  ResolveResult,
} from '../types';

const BASE_URL = '/api';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: BASE_URL,
      headers: { 'Content-Type': 'application/json' },
    });

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        const status = error.response?.status;
        const detail = (error.response?.data as { detail?: string })?.detail;
        const url = `${error.config?.method?.toUpperCase()} ${error.config?.url}`;

        if (error.code === 'ERR_NETWORK') {
          console.error(`API Network Error: ${url} - Backend unreachable`);
        } else {
          console.error(`API Error ${status}: ${url} - ${detail || error.message}`);
        }
        return Promise.reject(error);
      }
    );
  }

  // ---- Dashboard ----

  async getDashboard(): Promise<DashboardStats> {
    const { data } = await this.client.get('/dashboard');
    return data;
  }

  // ---- Customers ----

  async getCustomers(): Promise<Customer[]> {
    const { data } = await this.client.get('/customers');
    return data;
  }

  async getCustomer(id: string): Promise<Customer> {
    const { data } = await this.client.get(`/customers/${id}`);
    return data;
  }

  async createCustomer(customer: Partial<Customer>): Promise<Customer> {
    const { data } = await this.client.post('/customers', customer);
    return data;
  }

  async updateCustomer(id: string, customer: Partial<Customer>): Promise<Customer> {
    const { data } = await this.client.put(`/customers/${id}`, customer);
    return data;
  }

  async deleteCustomer(id: string): Promise<void> {
    await this.client.delete(`/customers/${id}`);
  }

  // ---- Approval Queue ----

  async getApprovalQueue(params?: {
    status?: ApprovalStatus;
    item_type?: string;
    customer_id?: string;
  }): Promise<ApprovalItem[]> {
    const { data } = await this.client.get('/approvals', { params });
    return data;
  }

  async getApprovalItem(id: string): Promise<ApprovalItem> {
    const { data } = await this.client.get(`/approvals/${id}`);
    return data;
  }

  async updateApprovalItem(id: string, updates: Partial<ApprovalItem>): Promise<ApprovalItem> {
    const { data } = await this.client.patch(`/approvals/${id}`, updates);
    return data;
  }

  async approveAndPublish(id: string): Promise<ApprovalItem> {
    // First approve, then publish via the action endpoint
    await this.client.post(`/approvals/${id}/action`, { action: 'approve' });
    const { data } = await this.client.post(`/approvals/${id}/action`, { action: 'publish' });
    return data;
  }

  async approveAndCopy(id: string): Promise<{ content: string }> {
    // Approve the item, then return its content for clipboard
    const { data } = await this.client.post(`/approvals/${id}/action`, { action: 'approve' });
    return { content: data.content || '' };
  }

  async rejectApproval(id: string): Promise<ApprovalItem> {
    const { data } = await this.client.post(`/approvals/${id}/action`, { action: 'reject' });
    return data;
  }

  // ---- Transcripts ----

  async uploadTranscript(
    customerId: string,
    meetingDate: string,
    file?: File,
    text?: string,
    calendarEventId?: string,
  ): Promise<ApprovalItem> {
    const formData = new FormData();
    formData.append('customer_id', customerId);
    formData.append('meeting_date', meetingDate);
    if (calendarEventId) formData.append('calendar_event_id', calendarEventId);
    if (file) {
      formData.append('file', file);
    } else if (text) {
      formData.append('transcript_text', text);
    }
    const { data } = await this.client.post('/transcripts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  }

  // ---- Calendar ----

  async getUpcomingEvents(days?: number): Promise<CalendarEvent[]> {
    const { data } = await this.client.get('/calendar/events', { params: { days } });
    return data;
  }

  async getRecentEvents(customerId?: string): Promise<CalendarEvent[]> {
    const { data } = await this.client.get('/calendar/recent', { params: { customer_id: customerId } });
    return data;
  }

  // ---- Linear Tickets ----

  async getLinearTickets(params?: {
    customer_id?: string;
    status?: string;
    approval_status?: ApprovalStatus;
  }): Promise<LinearTicket[]> {
    const { data } = await this.client.get('/linear/tickets', { params });
    return data;
  }

  async createLinearTicket(ticket: Partial<LinearTicket>): Promise<LinearTicket> {
    const { data } = await this.client.post('/linear/tickets', ticket);
    return data;
  }

  async updateLinearTicket(id: string, updates: Partial<LinearTicket>): Promise<LinearTicket> {
    const { data } = await this.client.put(`/linear/tickets/${id}`, updates);
    return data;
  }

  async approveLinearTicket(id: string): Promise<LinearTicket> {
    const { data } = await this.client.post(`/linear/tickets/${id}/approve`);
    return data;
  }

  async bulkApproveLinearTickets(ids: string[]): Promise<LinearTicket[]> {
    const { data } = await this.client.post('/linear/tickets/bulk-approve', { ids });
    return data;
  }

  // ---- Slack Mentions ----

  async getSlackMentions(params?: {
    customer_id?: string;
    handled?: boolean;
  }): Promise<SlackMention[]> {
    const { data } = await this.client.get('/slack/mentions', { params });
    return data;
  }

  async createTicketFromMention(mentionId: string): Promise<LinearTicket> {
    const { data } = await this.client.post(`/slack/mentions/${mentionId}/create-ticket`);
    return data;
  }

  async markMentionHandled(mentionId: string): Promise<SlackMention> {
    const { data } = await this.client.post(`/slack/mentions/${mentionId}/handled`);
    return data;
  }

  // ---- Health ----

  async getHealthUpdates(params?: {
    customer_id?: string;
    approval_status?: ApprovalStatus;
  }): Promise<HealthUpdate[]> {
    const { data } = await this.client.get('/health', { params });
    return data;
  }

  async getHealthHistory(customerId: string): Promise<HealthUpdate[]> {
    const { data } = await this.client.get(`/health/history/${customerId}`);
    return data;
  }

  // ---- Integrations / Settings ----

  async getIntegrationStatuses(): Promise<IntegrationStatus[]> {
    const { data } = await this.client.get('/integrations/status');
    return data;
  }

  async getOAuthConfig(): Promise<Record<string, boolean>> {
    const { data } = await this.client.get('/integrations/oauth-config');
    return data;
  }

  async saveOAuthAppConfig(config: {
    integration_type: string;
    client_id: string;
    client_secret: string;
    extra_config?: Record<string, string>;
  }): Promise<{ message: string; configured: boolean }> {
    const { data } = await this.client.post('/integrations/oauth-app-config', config);
    return data;
  }

  async getSlackManifest(workspace: 'internal' | 'external'): Promise<Record<string, unknown>> {
    const { data } = await this.client.get(`/integrations/slack-manifest/${workspace}`);
    return data;
  }

  /**
   * Get the OAuth connect URL for a given integration.
   * Backend auth routes use GET /auth/{service}/connect which returns a redirect.
   * The frontend should open this URL directly in a popup/new tab.
   */
  getOAuthConnectUrl(integration: string): string {
    // Map frontend integration keys to backend auth route paths
    const pathMap: Record<string, string> = {
      google: '/auth/google/connect',
      slack_internal: '/auth/slack/internal/connect',
      slack_external: '/auth/slack/external/connect',
      linear: '/auth/linear/connect',
      notion: '/auth/notion/connect',
    };
    const path = pathMap[integration];
    if (!path) throw new Error(`Unknown integration: ${integration}`);
    // Auth routes are NOT under /api prefix — use absolute path
    return path;
  }

  async initiateOAuth(integration: string): Promise<{ auth_url: string }> {
    const auth_url = this.getOAuthConnectUrl(integration);
    return { auth_url };
  }

  async saveManualToken(integration: string, token: string): Promise<{ message: string; status: string; details?: Record<string, string> }> {
    const { data } = await this.client.post('/integrations/manual-token', {
      integration_type: integration,
      token,
    });
    return data;
  }

  async verifyIntegration(integration: string): Promise<{ valid: boolean; details: Record<string, string>; status: string }> {
    const { data } = await this.client.post(`/integrations/verify/${integration}`);
    return data;
  }

  async importGcloudCredentials(): Promise<{ message: string; user?: string; email?: string }> {
    const { data } = await this.client.post('/integrations/import-gcloud');
    return data;
  }

  async checkGcloudStatus(): Promise<{ available: boolean }> {
    const { data } = await this.client.get('/integrations/gcloud-status');
    return data;
  }

  async disconnectIntegration(integration: string): Promise<void> {
    // Note: backend does not currently have a disconnect endpoint.
    // This is a placeholder for future implementation.
    await this.client.delete(`/integrations/${integration}`);
  }

  async getTemplateConfig(): Promise<TemplateConfig> {
    const { data } = await this.client.get('/integrations/settings/templates');
    return data;
  }

  async updateTemplateConfig(config: Partial<TemplateConfig>): Promise<TemplateConfig> {
    const { data } = await this.client.put('/integrations/settings/templates', config);
    return data;
  }

  async triggerSchedulerJob(job: string): Promise<{ message: string }> {
    const { data } = await this.client.post(`/scheduler/trigger/${job}`);
    return data;
  }

  // ---- Resolution ----

  async resolveSlackChannel(workspace: 'internal' | 'external', channelName: string): Promise<ResolveResult> {
    const { data } = await this.client.post('/integrations/resolve/slack-channel', {
      workspace,
      channel_name: channelName,
    });
    return data;
  }

  async resolveSlackUser(workspace: 'internal' | 'external', query: string): Promise<ResolveResult> {
    const { data } = await this.client.post('/integrations/resolve/slack-user', {
      workspace,
      query,
    });
    return data;
  }

  async resolveLinearProject(url: string): Promise<ResolveResult> {
    const { data } = await this.client.post('/integrations/resolve/linear-project', { url });
    return data;
  }

  async resolveLinearTeam(name: string): Promise<ResolveResult> {
    const { data } = await this.client.post('/integrations/resolve/linear-team', { name });
    return data;
  }

  async resolveLinearAssignee(query: string): Promise<ResolveResult> {
    const { data } = await this.client.post('/integrations/resolve/linear-assignee', { query });
    return data;
  }

  async resolveNotionPage(url: string): Promise<ResolveResult> {
    const { data } = await this.client.post('/integrations/resolve/notion-page', { url });
    return data;
  }

  async resolveGoogleDoc(url: string): Promise<ResolveResult> {
    const { data } = await this.client.post('/integrations/resolve/google-doc', { url });
    return data;
  }

  // ---- Workflows ----

  async triggerAgendaGeneration(customerId: string, eventId: string): Promise<ApprovalItem> {
    const { data } = await this.client.post('/workflows/agenda', { customer_id: customerId, event_id: eventId });
    return data;
  }
}

export const api = new ApiClient();
export default api;
