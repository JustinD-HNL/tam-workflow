import { useState, useEffect, useCallback } from 'react';
import {
  LinkIcon,
  ArrowPathIcon,
  TrashIcon,
  PlayIcon,
  KeyIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClipboardDocumentIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline';
import { useApi } from '../hooks/useApi';
import api from '../services/api';
import { PageLoader } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { ResolvableField } from '../components/ResolvableField';
import { formatDateTime } from '../utils';
import type { IntegrationStatus, ConnectionStatus, TemplateConfig } from '../types';

// ---- Integration metadata ----

interface IntegrationMeta {
  display: string;
  description: string;
  scopes: string;
  setupType: 'oauth_app' | 'personal_token';
  steps: SetupStep[];
  tokenHint: string;
  adminRequest?: string;
}

interface SetupStep {
  title: string;
  detail: string;
  link?: string;
  linkText?: string;
}

const integrationMeta: Record<string, IntegrationMeta> = {
  google: {
    display: 'Google (Calendar, Docs, Drive)',
    description: 'Read calendar events, create/edit documents, manage files in Drive.',
    scopes: 'calendar.readonly, docs, drive.file',
    setupType: 'oauth_app',
    tokenHint: 'Paste a Google access token or service account JSON key.',
    adminRequest: `Hi,

I'm building a local automation tool (TAM Workflow) to manage customer meetings. It needs Google API access for:

- Reading my Google Calendar events (to detect upcoming customer calls)
- Creating/editing Google Docs (for meeting agendas and notes)
- Managing files in a Google Drive folder (storing generated docs)

**What I need:**
1. Access to a GCP project (or permission to create one) with these APIs enabled:
   - Google Calendar API
   - Google Docs API
   - Google Drive API
2. An OAuth 2.0 Client ID (type: Web application) created in that project with:
   - Authorized redirect URI: http://localhost:3001/auth/google/callback
3. The OAuth consent screen configured (can be "Internal" for our org)

If it's easier, I just need the **Client ID** and **Client Secret** from the OAuth client. I can handle the rest.

This runs entirely locally on my laptop — no external servers or data leaving our network.`,
    steps: [
      {
        title: 'Request GCP project access',
        detail: 'You need a GCP project with Calendar, Docs, and Drive APIs enabled. Use the admin request template below if you need help from IT.',
      },
      {
        title: 'Create an OAuth 2.0 Client ID',
        detail: 'In the GCP Console, go to APIs & Services > Credentials > Create Credentials > OAuth Client ID. Select "Web application" and add http://localhost:3001/auth/google/callback as an authorized redirect URI.',
        link: 'https://console.cloud.google.com/apis/credentials',
        linkText: 'GCP Credentials',
      },
      {
        title: 'Enter Client ID and Secret below',
        detail: 'Copy the Client ID and Client Secret from the OAuth client you created and paste them into the form below.',
      },
      {
        title: 'Click "Connect" to authenticate',
        detail: 'After saving credentials, click Connect to sign in with your Google account and grant access.',
      },
    ],
  },
  slack_internal: {
    display: 'Slack (Internal Workspace)',
    description: 'Monitor internal customer channels, post agendas and notes.',
    scopes: 'channels:read, channels:history, chat:write, users:read, app_mentions:read',
    setupType: 'oauth_app',
    tokenHint: 'Paste the Bot User OAuth Token (xoxb-...) from your Slack App > OAuth & Permissions.',
    adminRequest: `Hi,

I'm building a local automation tool (TAM Workflow) to help manage customer meetings, agendas, and notes. It needs a Slack App installed in our internal workspace to:

- Read customer channel messages (to track new threads)
- Post agendas and meeting notes to customer channels
- Detect @mentions

**What I need:**
1. Permission to create and install a Slack App in our internal workspace, OR
2. Someone to create the app and share the Bot User OAuth Token (xoxb-...) with me

The app needs these bot scopes: channels:read, channels:history, chat:write, users:read, app_mentions:read

I have a pre-built app manifest that auto-configures everything — it takes about 2 minutes. Happy to walk through it together.

This runs entirely locally on my laptop (localhost) — no external servers or data leaving our network.`,
    steps: [
      {
        title: 'Request admin access (or get the bot token)',
        detail: 'Use the admin request template below to ask your workspace admin for help. They can either give you permission to create the app, or create it and share the bot token with you.',
      },
      {
        title: 'Create a Slack App from manifest (if you have permission)',
        detail: 'Click "Create Slack App" below, select "From a manifest", and paste the manifest.',
        link: 'https://api.slack.com/apps?new_app=1',
        linkText: 'Create Slack App',
      },
      {
        title: 'Get the Bot Token',
        detail: 'After the app is created and installed, go to OAuth & Permissions to find the Bot User OAuth Token (xoxb-...). Paste it below.',
      },
    ],
  },
  slack_external: {
    display: 'Slack (External / Slack Connect)',
    description: 'Monitor customer-facing channels, detect @mentions.',
    scopes: 'channels:read, channels:history, chat:write, users:read, app_mentions:read',
    setupType: 'oauth_app',
    tokenHint: 'Paste the Bot User OAuth Token (xoxb-...) from your external Slack App > OAuth & Permissions.',
    adminRequest: `Hi,

I'm building a local automation tool (TAM Workflow) to manage customer interactions. It needs a Slack App installed in our external/customer-facing workspace to:

- Detect @mentions of me in customer Slack Connect channels
- Read channel messages for context
- Post approved agendas to customer channels

**What I need:**
1. Permission to create and install a Slack App in the external workspace, OR
2. Someone to create the app and share the Bot User OAuth Token (xoxb-...) with me

Required bot scopes: channels:read, channels:history, chat:write, users:read, app_mentions:read

I have a pre-built app manifest that auto-configures everything. This runs entirely locally on my laptop.`,
    steps: [
      {
        title: 'Request admin access (or get the bot token)',
        detail: 'Use the admin request template below. Same process as internal, but for the external workspace.',
      },
      {
        title: 'Create a Slack App from manifest (if you have permission)',
        detail: 'Same as internal but select the external workspace.',
        link: 'https://api.slack.com/apps?new_app=1',
        linkText: 'Create Slack App',
      },
      {
        title: 'Get the Bot Token',
        detail: 'After install, copy the Bot User OAuth Token (xoxb-...) and paste below.',
      },
    ],
  },
  linear: {
    display: 'Linear',
    description: 'Create and manage issues, track customer projects.',
    scopes: 'read, write',
    setupType: 'personal_token',
    tokenHint: 'Paste your Personal API Key from Linear > Settings > API > Personal API Keys.',
    steps: [
      {
        title: 'Open Linear API Settings',
        detail: 'Go to your Linear workspace settings, then API section.',
        link: 'https://linear.app/settings/api',
        linkText: 'Linear API Settings',
      },
      {
        title: 'Create a Personal API Key',
        detail: 'Click "Create key", give it a name like "TAM Workflow", and copy the key.',
      },
      {
        title: 'Paste the token below',
        detail: 'Use the "Paste Token" button to save it. No OAuth app needed.',
      },
    ],
  },
  notion: {
    display: 'Notion',
    description: 'Update customer health database, manage pages.',
    scopes: 'read_content, update_content, insert_content',
    setupType: 'personal_token',
    tokenHint: 'Paste the Internal Integration Token from Notion > Settings > Integrations.',
    adminRequest: `Hi,

I'm building a local automation tool (TAM Workflow) to track customer health status. It needs a Notion integration to:

- Read customer health pages
- Update health status (RAG), summary, and notes after customer calls
- Add new entries

**What I need:**
1. Permission to create an internal integration at notion.so/my-integrations (it may be restricted by workspace settings), OR
2. Someone to create an integration named "TAM Workflow" with Read/Update/Insert capabilities and share the Internal Integration Token with me

The integration also needs to be connected to our customer health database in Notion (via the database's Connections menu).

This runs entirely locally on my laptop — no external servers involved.`,
    steps: [
      {
        title: 'Request access (if integration creation is restricted)',
        detail: 'If you cannot create integrations at notion.so/my-integrations, use the admin request template below to ask a workspace admin for help.',
      },
      {
        title: 'Create a Notion Integration (if you have access)',
        detail: 'Go to Notion integrations page, click "New integration", name it "TAM Workflow".',
        link: 'https://www.notion.so/my-integrations',
        linkText: 'Notion Integrations',
      },
      {
        title: 'Copy the Internal Integration Token',
        detail: 'On the integration page, click "Show" next to the token and copy it.',
      },
      {
        title: 'Share your database with the integration',
        detail: 'Open your customer health database in Notion, click ... > Connections > Add connection > "TAM Workflow".',
      },
      {
        title: 'Paste the token below',
        detail: 'Use the token input to save it.',
      },
    ],
  },
};

// ---- Component ----

export function Settings() {
  const { data: integrations, loading, error, refetch } = useApi<IntegrationStatus[]>(
    () => api.getIntegrationStatuses(),
    []
  );

  const { data: templates, refetch: refetchTemplates } = useApi<TemplateConfig>(
    () => api.getTemplateConfig(),
    []
  );

  const [oauthConfig, setOauthConfig] = useState<Record<string, boolean> | null>(null);
  const [expandedSetup, setExpandedSetup] = useState<string | null>(null);
  const [manualTokenTarget, setManualTokenTarget] = useState<string | null>(null);
  const [manualToken, setManualToken] = useState('');
  const [savingToken, setSavingToken] = useState(false);
  const [savingTemplates, setSavingTemplates] = useState(false);
  const [templateForm, setTemplateForm] = useState({
    agenda_template_url: '',
    notes_template_url: '',
  });
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [schedulerMessage, setSchedulerMessage] = useState<string | null>(null);

  // OAuth app config form
  const [oauthForm, setOauthForm] = useState<Record<string, { client_id: string; client_secret: string }>>({});
  const [savingOAuthConfig, setSavingOAuthConfig] = useState<string | null>(null);
  const [copiedManifest, setCopiedManifest] = useState<string | null>(null);
  const [copiedAdminRequest, setCopiedAdminRequest] = useState<string | null>(null);
  const [agendaDocId, setAgendaDocId] = useState('');
  const [agendaDocName, setAgendaDocName] = useState('');
  const [notesDocId, setNotesDocId] = useState('');
  const [notesDocName, setNotesDocName] = useState('');

  const fetchOAuthConfig = useCallback(() => {
    api.getOAuthConfig().then(setOauthConfig).catch(() => setOauthConfig(null));
  }, []);

  // Fetch OAuth config status and gcloud status on mount
  useEffect(() => {
    fetchOAuthConfig();
  }, [fetchOAuthConfig]);

  // Check URL params for OAuth results
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const errorIntegration = params.get('error');
    const reason = params.get('reason');
    if (errorIntegration && reason === 'not_configured') {
      const meta = integrationMeta[errorIntegration];
      const name = meta?.display || errorIntegration;
      setConfigError(`${name} OAuth app is not set up yet. Follow the setup steps below.`);
      setExpandedSetup(errorIntegration);
      window.history.replaceState({}, '', '/settings');
    }
    const connected = params.get('connected');
    if (connected) {
      const meta = integrationMeta[connected];
      setSuccessMessage(`${meta?.display || connected} connected successfully!`);
      refetch();
      fetchOAuthConfig();
      setTimeout(() => setSuccessMessage(null), 5000);
      window.history.replaceState({}, '', '/settings');
    }
  }, [refetch, fetchOAuthConfig]);

  // Update template form when data loads
  useEffect(() => {
    if (templates) {
      setTemplateForm({
        agenda_template_url: templates.agenda_template_url || '',
        notes_template_url: templates.notes_template_url || '',
      });
    }
  }, [templates]);

  async function handleOAuthConnect(integration: string) {
    if (oauthConfig && !oauthConfig[integration]) {
      setConfigError(`Set up ${integrationMeta[integration].display} first using the setup guide below.`);
      setExpandedSetup(integration);
      return;
    }
    try {
      const { auth_url } = await api.initiateOAuth(integration);
      window.open(auth_url, '_blank', 'width=600,height=700');
      setTimeout(() => { refetch(); fetchOAuthConfig(); }, 5000);
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } }; message?: string };
      setTokenError(errorObj.response?.data?.detail || 'Failed to initiate OAuth flow');
    }
  }

  async function handleSaveOAuthAppConfig(integration: string) {
    const form = oauthForm[integration];
    if (!form?.client_id?.trim()) {
      setTokenError('Client ID is required');
      return;
    }
    setSavingOAuthConfig(integration);
    setTokenError(null);
    try {
      await api.saveOAuthAppConfig({
        integration_type: integration,
        client_id: form.client_id.trim(),
        client_secret: form.client_secret?.trim() || '',
      });
      fetchOAuthConfig();
      setSuccessMessage(`${integrationMeta[integration].display} credentials saved! You can now click "Connect".`);
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } }; message?: string };
      setTokenError(errorObj.response?.data?.detail || 'Failed to save OAuth app config');
    } finally {
      setSavingOAuthConfig(null);
    }
  }

  async function handleSaveManualToken() {
    if (!manualTokenTarget || !manualToken.trim()) return;
    setSavingToken(true);
    setTokenError(null);
    try {
      const result = await api.saveManualToken(manualTokenTarget, manualToken.trim());
      const details = result.details;
      const detailStr = details
        ? Object.entries(details).map(([k, v]) => `${k}: ${v}`).join(', ')
        : '';
      setManualTokenTarget(null);
      setManualToken('');
      refetch();
      setSuccessMessage(
        `${integrationMeta[manualTokenTarget].display} connected and verified!` +
        (detailStr ? ` (${detailStr})` : '')
      );
      setTimeout(() => setSuccessMessage(null), 8000);
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } }; message?: string };
      setTokenError(errorObj.response?.data?.detail || 'Failed to save token');
    } finally {
      setSavingToken(false);
    }
  }

  const [verifying, setVerifying] = useState<string | null>(null);

  async function handleVerify(integration: string) {
    setVerifying(integration);
    setTokenError(null);
    try {
      const result = await api.verifyIntegration(integration);
      if (result.valid) {
        const details = result.details;
        const detailStr = Object.entries(details).map(([k, v]) => `${k}: ${v}`).join(', ');
        setSuccessMessage(`${integrationMeta[integration].display} verified! (${detailStr})`);
        setTimeout(() => setSuccessMessage(null), 8000);
      } else {
        setTokenError(`${integrationMeta[integration].display} verification failed: ${result.details?.error || 'Unknown error'}`);
      }
      refetch();
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } }; message?: string };
      setTokenError(errorObj.response?.data?.detail || 'Verification failed');
    } finally {
      setVerifying(null);
    }
  }

  async function handleCopyAdminRequest(integration: string) {
    const meta = integrationMeta[integration];
    if (meta?.adminRequest) {
      await navigator.clipboard.writeText(meta.adminRequest);
      setCopiedAdminRequest(integration);
      setTimeout(() => setCopiedAdminRequest(null), 3000);
    }
  }

  async function handleDisconnect(integration: string) {
    try {
      await api.disconnectIntegration(integration);
      refetch();
    } catch { /* handled */ }
  }

  async function handleCopyManifest(workspace: 'internal' | 'external') {
    try {
      const manifest = await api.getSlackManifest(workspace);
      await navigator.clipboard.writeText(JSON.stringify(manifest, null, 2));
      setCopiedManifest(workspace);
      setTimeout(() => setCopiedManifest(null), 3000);
    } catch {
      setTokenError('Failed to copy manifest to clipboard');
    }
  }

  async function handleSaveTemplates() {
    setSavingTemplates(true);
    try {
      await api.updateTemplateConfig(templateForm);
      refetchTemplates();
    } catch { /* handled */ }
    finally { setSavingTemplates(false); }
  }

  async function handleTriggerJob(job: string) {
    try {
      const result = await api.triggerSchedulerJob(job);
      setSchedulerMessage(result.message);
      setTimeout(() => setSchedulerMessage(null), 3000);
    } catch { /* handled */ }
  }

  function getStatusIndicator(status: ConnectionStatus, isConfigured: boolean) {
    if (status === 'connected') {
      return <span className="flex h-3 w-3 rounded-full bg-green-500" title="Connected" />;
    }
    if (!isConfigured) {
      return <span className="flex h-3 w-3 rounded-full bg-gray-400" title="Not Configured" />;
    }
    if (status === 'expired') {
      return <span className="flex h-3 w-3 rounded-full bg-yellow-500" title="Token Expired" />;
    }
    return <span className="flex h-3 w-3 rounded-full bg-red-500" title="Not Connected" />;
  }

  function getStatusLabel(status: ConnectionStatus, isConfigured: boolean): string {
    if (status === 'connected') return 'Connected';
    if (!isConfigured) return 'Setup Required';
    if (status === 'expired') return 'Token Expired';
    return 'Ready to Connect';
  }

  if (loading && !integrations) return <PageLoader />;

  const connectedCount = integrations?.filter(i => i.status === 'connected').length || 0;
  const totalIntegrations = Object.keys(integrationMeta).length;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <span className="text-sm text-gray-500">{connectedCount}/{totalIntegrations} integrations connected</span>
      </div>

      {error && <ErrorAlert message={error} onRetry={refetch} />}
      {tokenError && <ErrorAlert message={tokenError} onDismiss={() => setTokenError(null)} />}

      {successMessage && (
        <div className="rounded-md bg-green-50 border border-green-200 p-4 flex items-center gap-3">
          <CheckCircleIcon className="h-5 w-5 text-green-600 flex-shrink-0" />
          <p className="text-sm text-green-700">{successMessage}</p>
        </div>
      )}

      {configError && (
        <div className="rounded-md bg-amber-50 border border-amber-200 p-4">
          <div className="flex items-start gap-3">
            <ExclamationTriangleIcon className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-amber-700">{configError}</p>
              <button onClick={() => setConfigError(null)} className="mt-1 text-xs text-amber-800 underline">Dismiss</button>
            </div>
          </div>
        </div>
      )}

      {/* Integration Setup Wizard */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Integrations</h2>
            <p className="mt-1 text-sm text-gray-500">
              Connect services to enable automated workflows. Click each integration to see setup instructions.
            </p>
          </div>
          <button onClick={() => { refetch(); fetchOAuthConfig(); }} className="btn-secondary text-sm">
            <ArrowPathIcon className="h-4 w-4 mr-1" />
            Refresh
          </button>
        </div>

        {Object.entries(integrationMeta).map(([key, meta]) => {
          const status = integrations?.find((i) => i.integration_type === key);
          const connectionStatus: ConnectionStatus = status?.status || 'disconnected';
          const isConfigured = oauthConfig ? oauthConfig[key] === true : false;
          const isExpanded = expandedSetup === key;
          const isSlack = key.startsWith('slack_');
          const slackWorkspace = key === 'slack_internal' ? 'internal' : 'external';

          return (
            <div key={key} className="card">
              {/* Header row */}
              <div className="flex items-center justify-between">
                <button
                  onClick={() => setExpandedSetup(isExpanded ? null : key)}
                  className="flex items-center gap-3 flex-1 text-left"
                >
                  {getStatusIndicator(connectionStatus, isConfigured || meta.setupType === 'personal_token')}
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-gray-900">{meta.display}</h3>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        connectionStatus === 'connected'
                          ? 'bg-green-100 text-green-700'
                          : !isConfigured && meta.setupType === 'oauth_app'
                          ? 'bg-gray-100 text-gray-600'
                          : connectionStatus === 'expired'
                          ? 'bg-yellow-100 text-yellow-700'
                          : 'bg-blue-100 text-blue-700'
                      }`}>
                        {getStatusLabel(connectionStatus, isConfigured || meta.setupType === 'personal_token')}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{meta.description}</p>
                  </div>
                  {isExpanded
                    ? <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                    : <ChevronRightIcon className="h-5 w-5 text-gray-400" />
                  }
                </button>

                {/* Action buttons */}
                <div className="flex items-center gap-2 ml-4">
                  {connectionStatus === 'connected' ? (
                    <>
                      {status?.last_verified && (
                        <span className="text-xs text-gray-400 mr-2">
                          Verified: {formatDateTime(status.last_verified)}
                        </span>
                      )}
                      <button
                        onClick={() => handleVerify(key)}
                        disabled={verifying === key}
                        className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                      >
                        <ArrowPathIcon className={`h-3.5 w-3.5 ${verifying === key ? 'animate-spin' : ''}`} />
                        {verifying === key ? 'Verifying...' : 'Verify'}
                      </button>
                      <button
                        onClick={() => handleDisconnect(key)}
                        className="text-xs text-red-600 hover:text-red-800 flex items-center gap-1"
                      >
                        <TrashIcon className="h-3.5 w-3.5" />
                        Disconnect
                      </button>
                    </>
                  ) : meta.setupType === 'oauth_app' && isConfigured ? (
                    <button
                      onClick={() => handleOAuthConnect(key)}
                      className="btn-primary text-sm"
                    >
                      <LinkIcon className="h-4 w-4 mr-1" />
                      Connect
                    </button>
                  ) : meta.setupType === 'personal_token' ? (
                    <button
                      onClick={() => {
                        setManualTokenTarget(key);
                        setManualToken('');
                        if (!isExpanded) setExpandedSetup(key);
                      }}
                      className="btn-primary text-sm"
                    >
                      <KeyIcon className="h-4 w-4 mr-1" />
                      Paste Token
                    </button>
                  ) : (
                    <button
                      onClick={() => setExpandedSetup(isExpanded ? null : key)}
                      className="btn-secondary text-sm"
                    >
                      <Cog6ToothIcon className="h-4 w-4 mr-1" />
                      Set Up
                    </button>
                  )}
                </div>
              </div>

              {/* Expanded setup guide */}
              {isExpanded && (
                <div className="mt-4 pt-4 border-t border-gray-100">
                  {/* Setup Steps */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Setup Steps</h4>
                    <ol className="space-y-3">
                      {meta.steps.map((step, i) => (
                        <li key={i} className="flex gap-3">
                          <span className="flex-shrink-0 flex items-center justify-center h-6 w-6 rounded-full bg-gray-100 text-xs font-medium text-gray-600">
                            {i + 1}
                          </span>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-gray-800">{step.title}</p>
                            <p className="text-xs text-gray-500 mt-0.5">{step.detail}</p>
                            {step.link && (
                              <a
                                href={step.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center text-xs text-blue-600 hover:text-blue-800 mt-1"
                              >
                                {step.linkText || 'Open'} &rarr;
                              </a>
                            )}
                          </div>
                        </li>
                      ))}
                    </ol>
                  </div>

                  {/* Slack manifest copy button */}
                  {isSlack && (
                    <div className="mt-4 p-3 bg-gray-50 rounded-md">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-gray-700">Slack App Manifest (auto-configures all scopes and events)</span>
                        <button
                          onClick={() => handleCopyManifest(slackWorkspace as 'internal' | 'external')}
                          className="btn-secondary text-xs"
                        >
                          <ClipboardDocumentIcon className="h-3.5 w-3.5 mr-1" />
                          {copiedManifest === slackWorkspace ? 'Copied!' : 'Copy Manifest'}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Admin request template */}
                  {meta.adminRequest && connectionStatus !== 'connected' && (
                    <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-md">
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="text-xs font-semibold text-amber-800 uppercase tracking-wide">Admin Request Template</h4>
                          <p className="text-xs text-amber-700 mt-1">Need admin help? Copy this message and send it to your IT/workspace admin:</p>
                        </div>
                        <button
                          onClick={() => handleCopyAdminRequest(key)}
                          className="btn-secondary text-xs flex-shrink-0"
                        >
                          <ClipboardDocumentIcon className="h-3.5 w-3.5 mr-1" />
                          {copiedAdminRequest === key ? 'Copied!' : 'Copy Request'}
                        </button>
                      </div>
                      <pre className="mt-2 text-xs text-amber-900 whitespace-pre-wrap bg-amber-100 p-3 rounded max-h-40 overflow-y-auto">{meta.adminRequest}</pre>
                    </div>
                  )}

                  {/* OAuth App Config Form (for Google, Slack) */}
                  {meta.setupType === 'oauth_app' && connectionStatus !== 'connected' && (
                    <div className="mt-4 p-4 bg-blue-50 rounded-md space-y-3">
                      <h4 className="text-xs font-semibold text-blue-800 uppercase tracking-wide">
                        {isConfigured ? 'Update Credentials' : 'Enter OAuth App Credentials'}
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs font-medium text-gray-700">Client ID</label>
                          <input
                            type="text"
                            value={oauthForm[key]?.client_id || ''}
                            onChange={(e) => setOauthForm(prev => ({
                              ...prev,
                              [key]: { ...prev[key], client_id: e.target.value, client_secret: prev[key]?.client_secret || '' }
                            }))}
                            className="input-field mt-1 text-sm"
                            placeholder="Client ID"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-medium text-gray-700">Client Secret</label>
                          <input
                            type="password"
                            value={oauthForm[key]?.client_secret || ''}
                            onChange={(e) => setOauthForm(prev => ({
                              ...prev,
                              [key]: { client_id: prev[key]?.client_id || '', client_secret: e.target.value }
                            }))}
                            className="input-field mt-1 text-sm"
                            placeholder="Client Secret"
                          />
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => handleSaveOAuthAppConfig(key)}
                          disabled={savingOAuthConfig === key || !oauthForm[key]?.client_id?.trim()}
                          className="btn-primary text-sm"
                        >
                          {savingOAuthConfig === key ? 'Saving...' : isConfigured ? 'Update & Connect' : 'Save & Connect'}
                        </button>
                        {isConfigured && (
                          <span className="text-xs text-green-600 flex items-center gap-1">
                            <CheckCircleIcon className="h-4 w-4" />
                            Credentials saved
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Manual Token Input (always available as fallback, primary for Linear/Notion) */}
                  {(meta.setupType === 'personal_token' || manualTokenTarget === key) && connectionStatus !== 'connected' && (
                    <div className="mt-4 p-4 bg-gray-50 rounded-md space-y-3">
                      <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
                        {meta.setupType === 'personal_token' ? 'Paste Token' : 'Alternative: Paste Token Directly'}
                      </h4>
                      <p className="text-xs text-gray-500">{meta.tokenHint}</p>
                      <div className="flex items-center gap-2">
                        <input
                          type="password"
                          value={manualTokenTarget === key ? manualToken : ''}
                          onChange={(e) => {
                            setManualTokenTarget(key);
                            setManualToken(e.target.value);
                          }}
                          className="input-field flex-1 text-sm"
                          placeholder={`Paste ${meta.display} token...`}
                        />
                        <button
                          onClick={handleSaveManualToken}
                          disabled={savingToken || !(manualTokenTarget === key && manualToken.trim())}
                          className="btn-primary text-sm"
                        >
                          {savingToken ? 'Saving...' : 'Save Token'}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Fallback: manual token for OAuth-type integrations */}
                  {meta.setupType === 'oauth_app' && manualTokenTarget !== key && connectionStatus !== 'connected' && (
                    <div className="mt-3">
                      <button
                        onClick={() => {
                          setManualTokenTarget(key);
                          setManualToken('');
                        }}
                        className="text-xs text-gray-500 hover:text-gray-700 underline"
                      >
                        Or paste a token directly (skip OAuth)
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Template Links */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Document Templates</h2>
        <p className="text-sm text-gray-500">
          Link Google Docs templates used as structural guides for generated content.
        </p>
        <div className="space-y-4">
          <div>
            <ResolvableField
              label="Agenda Template (Google Doc URL)"
              placeholder="https://docs.google.com/document/d/..."
              helpText="Paste the URL of the Google Doc to use as the agenda template."
              value={templateForm.agenda_template_url}
              resolvedId={agendaDocId}
              resolvedName={agendaDocName}
              onValueChange={(v) => setTemplateForm((prev) => ({ ...prev, agenda_template_url: v }))}
              onResolved={(id, name) => { setAgendaDocId(id); setAgendaDocName(name); }}
              onClear={() => { setAgendaDocId(''); setAgendaDocName(''); }}
              resolveFn={(url) => api.resolveGoogleDoc(url)}
            />
            {templates?.agenda_template_last_fetched && (
              <p className="text-xs text-gray-400 mt-1">
                Last fetched: {formatDateTime(templates.agenda_template_last_fetched)}
              </p>
            )}
          </div>
          <div>
            <ResolvableField
              label="Meeting Notes Template (Google Doc URL)"
              placeholder="https://docs.google.com/document/d/..."
              helpText="Paste the URL of the Google Doc to use as the meeting notes template."
              value={templateForm.notes_template_url}
              resolvedId={notesDocId}
              resolvedName={notesDocName}
              onValueChange={(v) => setTemplateForm((prev) => ({ ...prev, notes_template_url: v }))}
              onResolved={(id, name) => { setNotesDocId(id); setNotesDocName(name); }}
              onClear={() => { setNotesDocId(''); setNotesDocName(''); }}
              resolveFn={(url) => api.resolveGoogleDoc(url)}
            />
            {templates?.notes_template_last_fetched && (
              <p className="text-xs text-gray-400 mt-1">
                Last fetched: {formatDateTime(templates.notes_template_last_fetched)}
              </p>
            )}
          </div>
          <button onClick={handleSaveTemplates} disabled={savingTemplates} className="btn-primary">
            {savingTemplates ? 'Saving...' : 'Save Templates'}
          </button>
        </div>
      </div>

      {/* Scheduler Controls */}
      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Scheduler</h2>
        <p className="text-sm text-gray-500">Manually trigger scheduled jobs for testing or catch-up.</p>
        {schedulerMessage && (
          <div className="rounded-md bg-green-50 p-3 text-sm text-green-700">{schedulerMessage}</div>
        )}
        <div className="flex flex-wrap gap-3">
          <button onClick={() => handleTriggerJob('scan_calendar')} className="btn-secondary text-sm">
            <PlayIcon className="h-4 w-4 mr-1" /> Scan Calendar
          </button>
          <button onClick={() => handleTriggerJob('refresh_templates')} className="btn-secondary text-sm">
            <PlayIcon className="h-4 w-4 mr-1" /> Refresh Templates
          </button>
          <button onClick={() => handleTriggerJob('health_check')} className="btn-secondary text-sm">
            <PlayIcon className="h-4 w-4 mr-1" /> Check Integrations
          </button>
        </div>
      </div>
    </div>
  );
}
