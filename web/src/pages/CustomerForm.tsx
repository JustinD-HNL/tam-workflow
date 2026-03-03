import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeftIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import api from '../services/api';
import { PageLoader } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { ResolvableField } from '../components/ResolvableField';
import type { Customer, HealthStatus, Priority, Contact } from '../types';

const cadenceOptions = ['weekly', 'biweekly', 'monthly', 'quarterly'];
const healthOptions: HealthStatus[] = ['green', 'yellow', 'red'];
const priorityOptions: Priority[] = ['none', 'low', 'medium', 'high', 'urgent'];

export function CustomerForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEditing = id && id !== 'new';

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verifyTrigger, setVerifyTrigger] = useState(0);

  // Basic form fields
  const [form, setForm] = useState({
    name: '',
    slug: '',
    cadence: 'biweekly',
    health_status: 'green' as HealthStatus,
    primary_contacts: [] as Contact[],
    google_calendar_event_pattern: '',
    google_docs_folder_id: '',
    linear_priority: 'medium' as Priority,
  });

  // Resolvable fields: display value, resolved ID, and resolved display name
  const [linear_project_display, setLinearProjectDisplay] = useState('');
  const [linear_project_id, setLinearProjectId] = useState('');
  const [linear_project_name, setLinearProjectName] = useState('');

  const [slack_internal_display, setSlackInternalDisplay] = useState('');
  const [slack_internal_id, setSlackInternalId] = useState('');
  const [slack_internal_name, setSlackInternalName] = useState('');

  const [slack_external_display, setSlackExternalDisplay] = useState('');
  const [slack_external_id, setSlackExternalId] = useState('');
  const [slack_external_name, setSlackExternalName] = useState('');

  const [notion_page_display, setNotionPageDisplay] = useState('');
  const [notion_page_id, setNotionPageId] = useState('');
  const [notion_page_name, setNotionPageName] = useState('');

  const [tam_slack_display, setTamSlackDisplay] = useState('');
  const [tam_slack_id, setTamSlackId] = useState('');
  const [tam_slack_name, setTamSlackName] = useState('');

  const [linear_team_display, setLinearTeamDisplay] = useState('');
  const [linear_team_id, setLinearTeamId] = useState('');
  const [linear_team_name, setLinearTeamName] = useState('');

  const [linear_assignee_display, setLinearAssigneeDisplay] = useState('');
  const [linear_assignee_id, setLinearAssigneeId] = useState('');
  const [linear_assignee_name, setLinearAssigneeName] = useState('');

  useEffect(() => {
    if (isEditing) {
      setLoading(true);
      api.getCustomer(id)
        .then((customer) => {
          setForm({
            name: customer.name,
            slug: customer.slug,
            cadence: customer.cadence,
            health_status: customer.health_status,
            primary_contacts: customer.primary_contacts || [],
            google_calendar_event_pattern: customer.google_calendar_event_pattern || '',
            google_docs_folder_id: customer.google_docs_folder_id || '',
            linear_priority: customer.linear_task_defaults?.priority || 'medium',
          });

          // Set resolvable fields — display the stored ID as the value
          // The user can re-resolve or leave as-is
          if (customer.linear_project_id) {
            setLinearProjectDisplay(customer.linear_project_id);
            setLinearProjectId(customer.linear_project_id);
            setLinearProjectName(customer.linear_project_id);
          }
          if (customer.slack_internal_channel_id) {
            setSlackInternalDisplay(customer.slack_internal_channel_id);
            setSlackInternalId(customer.slack_internal_channel_id);
            setSlackInternalName(customer.slack_internal_channel_id);
          }
          if (customer.slack_external_channel_id) {
            setSlackExternalDisplay(customer.slack_external_channel_id);
            setSlackExternalId(customer.slack_external_channel_id);
            setSlackExternalName(customer.slack_external_channel_id);
          }
          if (customer.notion_page_id) {
            setNotionPageDisplay(customer.notion_page_id);
            setNotionPageId(customer.notion_page_id);
            setNotionPageName(customer.notion_page_id);
          }
          if (customer.tam_slack_user_id) {
            setTamSlackDisplay(customer.tam_slack_user_id);
            setTamSlackId(customer.tam_slack_user_id);
            setTamSlackName(customer.tam_slack_user_id);
          }
          if (customer.linear_task_defaults?.team_id) {
            setLinearTeamDisplay(customer.linear_task_defaults.team_id);
            setLinearTeamId(customer.linear_task_defaults.team_id);
            setLinearTeamName(customer.linear_task_defaults.team_id);
          }
          if (customer.linear_task_defaults?.assignee_id) {
            setLinearAssigneeDisplay(customer.linear_task_defaults.assignee_id);
            setLinearAssigneeId(customer.linear_task_defaults.assignee_id);
            setLinearAssigneeName(customer.linear_task_defaults.assignee_id);
          }
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [id, isEditing]);

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));

    if (name === 'name' && !isEditing) {
      setForm((prev) => ({
        ...prev,
        [name]: value,
        slug: value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
      }));
    }
  }

  function addContact() {
    setForm((prev) => ({
      ...prev,
      primary_contacts: [...prev.primary_contacts, { name: '', email: '', role: '' }],
    }));
  }

  function updateContact(index: number, field: keyof Contact, value: string) {
    setForm((prev) => {
      const contacts = [...prev.primary_contacts];
      contacts[index] = { ...contacts[index], [field]: value };
      return { ...prev, primary_contacts: contacts };
    });
  }

  function removeContact(index: number) {
    setForm((prev) => ({
      ...prev,
      primary_contacts: prev.primary_contacts.filter((_, i) => i !== index),
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const payload: Partial<Customer> = {
      name: form.name,
      slug: form.slug,
      linear_project_id: linear_project_id || null,
      slack_internal_channel_id: slack_internal_id || null,
      slack_external_channel_id: slack_external_id || null,
      notion_page_id: notion_page_id || null,
      google_calendar_event_pattern: form.google_calendar_event_pattern || null,
      google_docs_folder_id: form.google_docs_folder_id || null,
      tam_slack_user_id: tam_slack_id || null,
      cadence: form.cadence,
      health_status: form.health_status,
      primary_contacts: form.primary_contacts,
      linear_task_defaults: linear_team_id
        ? {
            team_id: linear_team_id,
            assignee_id: linear_assignee_id,
            priority: form.linear_priority,
          }
        : null,
    };

    try {
      if (isEditing) {
        await api.updateCustomer(id, payload);
      } else {
        await api.createCustomer(payload);
      }
      navigate('/customers');
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(errorObj.response?.data?.detail || errorObj.message || 'Failed to save customer');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <PageLoader />;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/customers')} className="text-gray-400 hover:text-gray-600">
          <ArrowLeftIcon className="h-5 w-5" />
        </button>
        <h1 className="text-2xl font-bold text-gray-900">
          {isEditing ? 'Edit Customer' : 'Add Customer'}
        </h1>
      </div>

      {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Basic Info */}
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Basic Information</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Customer Name</label>
              <input type="text" name="name" value={form.name} onChange={handleChange} className="input-field mt-1" required />
            </div>
            <div>
              <label className="label">Slug</label>
              <input type="text" name="slug" value={form.slug} onChange={handleChange} className="input-field mt-1" required
                pattern="[a-z0-9-]+" title="Lowercase letters, numbers, and hyphens only" />
              <p className="mt-1 text-xs text-gray-500">Short identifier (auto-generated from name). Used for file paths and internal references.</p>
            </div>
            <div>
              <label className="label">Cadence</label>
              <select name="cadence" value={form.cadence} onChange={handleChange} className="input-field mt-1">
                {cadenceOptions.map((opt) => (
                  <option key={opt} value={opt}>{opt.charAt(0).toUpperCase() + opt.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Health Status</label>
              <select name="health_status" value={form.health_status} onChange={handleChange} className="input-field mt-1">
                {healthOptions.map((opt) => (
                  <option key={opt} value={opt}>{opt.charAt(0).toUpperCase() + opt.slice(1)}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Integration Configuration */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Integration Configuration</h2>
              <p className="text-sm text-gray-500 mt-0.5">Enter channel names, URLs, or @mentions — they'll be validated against each service.</p>
            </div>
            <button
              type="button"
              onClick={() => setVerifyTrigger((n) => n + 1)}
              className="btn-secondary text-sm flex items-center gap-1.5 whitespace-nowrap"
              title="Re-verify all integration fields"
            >
              <ArrowPathIcon className="h-4 w-4" />
              Verify All
            </button>
          </div>
          <div className="grid grid-cols-1 gap-4">
            <ResolvableField
              label="Linear Project"
              placeholder="Paste Linear project URL"
              helpText="e.g., https://linear.app/buildkite/project/aurora-6937c2a6e36e/"
              value={linear_project_display}
              resolvedId={linear_project_id}
              resolvedName={linear_project_name}
              onValueChange={setLinearProjectDisplay}
              onResolved={(id, name) => { setLinearProjectId(id); setLinearProjectName(name); }}
              onClear={() => { setLinearProjectId(''); setLinearProjectName(''); }}
              resolveFn={(url) => api.resolveLinearProject(url)}
              verifyTrigger={verifyTrigger}
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <ResolvableField
                label="Internal Slack Channel"
                placeholder="#channel-name"
                helpText="e.g., #aurora or #tam-aurora"
                value={slack_internal_display}
                resolvedId={slack_internal_id}
                resolvedName={slack_internal_name}
                onValueChange={setSlackInternalDisplay}
                onResolved={(id, name) => { setSlackInternalId(id); setSlackInternalName(name); }}
                onClear={() => { setSlackInternalId(''); setSlackInternalName(''); }}
                resolveFn={(name) => api.resolveSlackChannel('internal', name)}
                verifyTrigger={verifyTrigger}
              />
              <ResolvableField
                label="External Slack Channel"
                placeholder="#channel-name"
                helpText="e.g., #aurora-external"
                value={slack_external_display}
                resolvedId={slack_external_id}
                resolvedName={slack_external_name}
                onValueChange={setSlackExternalDisplay}
                onResolved={(id, name) => { setSlackExternalId(id); setSlackExternalName(name); }}
                onClear={() => { setSlackExternalId(''); setSlackExternalName(''); }}
                resolveFn={(name) => api.resolveSlackChannel('external', name)}
                verifyTrigger={verifyTrigger}
              />
            </div>

            <ResolvableField
              label="Notion Health Page"
              placeholder="Paste Notion page URL"
              helpText="e.g., https://www.notion.so/buildkite/Aurora-Health-21bb8dbc2c8981e7a908fd0d2b98f307"
              value={notion_page_display}
              resolvedId={notion_page_id}
              resolvedName={notion_page_name}
              onValueChange={setNotionPageDisplay}
              onResolved={(id, name) => { setNotionPageId(id); setNotionPageName(name); }}
              onClear={() => { setNotionPageId(''); setNotionPageName(''); }}
              resolveFn={(url) => api.resolveNotionPage(url)}
              verifyTrigger={verifyTrigger}
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="label">Google Calendar Event Pattern</label>
                <input type="text" name="google_calendar_event_pattern" value={form.google_calendar_event_pattern} onChange={handleChange} className="input-field mt-1" placeholder='e.g., "Aurora" or "TAM Sync"' />
                <p className="mt-1 text-xs text-gray-500">Text to match in calendar event titles.</p>
              </div>
              <div>
                <label className="label">Google Docs Folder ID</label>
                <input type="text" name="google_docs_folder_id" value={form.google_docs_folder_id} onChange={handleChange} className="input-field mt-1" placeholder="e.g., 1A2B3C4D..." />
                <p className="mt-1 text-xs text-gray-500">Google Drive folder ID for this customer's docs.</p>
              </div>
            </div>

            <ResolvableField
              label="TAM Slack User"
              placeholder="@your.name or display name"
              helpText="e.g., @justin.downer — your Slack username for @mention detection"
              value={tam_slack_display}
              resolvedId={tam_slack_id}
              resolvedName={tam_slack_name}
              onValueChange={setTamSlackDisplay}
              onResolved={(id, name) => { setTamSlackId(id); setTamSlackName(name); }}
              onClear={() => { setTamSlackId(''); setTamSlackName(''); }}
              resolveFn={(query) => api.resolveSlackUser('internal', query)}
              verifyTrigger={verifyTrigger}
            />
          </div>
        </div>

        {/* Linear Task Defaults */}
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Linear Task Defaults</h2>
          <p className="text-sm text-gray-500">Default settings for Linear issues created for this customer.</p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <ResolvableField
              label="Team"
              placeholder="Team name (e.g., Engineering)"
              value={linear_team_display}
              resolvedId={linear_team_id}
              resolvedName={linear_team_name}
              onValueChange={setLinearTeamDisplay}
              onResolved={(id, name) => { setLinearTeamId(id); setLinearTeamName(name); }}
              onClear={() => { setLinearTeamId(''); setLinearTeamName(''); }}
              resolveFn={(name) => api.resolveLinearTeam(name)}
              verifyTrigger={verifyTrigger}
            />
            <ResolvableField
              label="Assignee"
              placeholder="Name or email"
              value={linear_assignee_display}
              resolvedId={linear_assignee_id}
              resolvedName={linear_assignee_name}
              onValueChange={setLinearAssigneeDisplay}
              onResolved={(id, name) => { setLinearAssigneeId(id); setLinearAssigneeName(name); }}
              onClear={() => { setLinearAssigneeId(''); setLinearAssigneeName(''); }}
              resolveFn={(query) => api.resolveLinearAssignee(query)}
              verifyTrigger={verifyTrigger}
            />
            {/* Labels are now selected per-issue in the Linear Issues edit form */}
            <div>
              <label className="label">Default Priority</label>
              <select name="linear_priority" value={form.linear_priority} onChange={handleChange} className="input-field mt-1">
                {priorityOptions.map((opt) => (
                  <option key={opt} value={opt}>{opt.charAt(0).toUpperCase() + opt.slice(1)}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Primary Contacts */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Primary Contacts</h2>
            <button type="button" onClick={addContact} className="btn-secondary text-sm">
              Add Contact
            </button>
          </div>
          {form.primary_contacts.length === 0 ? (
            <p className="text-sm text-gray-500">No contacts added yet.</p>
          ) : (
            <div className="space-y-3">
              {form.primary_contacts.map((contact, i) => (
                <div key={i} className="flex gap-3 items-start">
                  <input type="text" value={contact.name} onChange={(e) => updateContact(i, 'name', e.target.value)} className="input-field flex-1" placeholder="Name" />
                  <input type="email" value={contact.email} onChange={(e) => updateContact(i, 'email', e.target.value)} className="input-field flex-1" placeholder="Email" />
                  <input type="text" value={contact.role} onChange={(e) => updateContact(i, 'role', e.target.value)} className="input-field flex-1" placeholder="Role" />
                  <button type="button" onClick={() => removeContact(i)} className="text-red-500 hover:text-red-700 mt-2 text-sm">Remove</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-3">
          <button type="button" onClick={() => navigate('/customers')} className="btn-secondary">Cancel</button>
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? 'Saving...' : isEditing ? 'Update Customer' : 'Create Customer'}
          </button>
        </div>
      </form>
    </div>
  );
}
