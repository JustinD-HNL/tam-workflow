import { useState } from 'react';
import { CheckCircleIcon, XCircleIcon, ClipboardIcon, EyeIcon, PencilSquareIcon } from '@heroicons/react/24/outline';
import { usePolling } from '../hooks/useApi';
import api from '../services/api';
import { PageLoader } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import {
  formatTimeAgo,
  getApprovalBadge,
  getApprovalLabel,
  getWorkflowTypeLabel,
  copyToClipboard,
  classNames,
} from '../utils';
import type { ApprovalItem, ApprovalStatus, WorkflowType } from '../types';

export function ApprovalQueue() {
  const [statusFilter, setStatusFilter] = useState<ApprovalStatus | ''>('');
  const [typeFilter, setTypeFilter] = useState<WorkflowType | ''>('');
  const [selectedItem, setSelectedItem] = useState<ApprovalItem | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState(false);

  // Edit state
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [publishExternal, setPublishExternal] = useState(false);

  // Auto-refresh every 10 seconds
  const { data, loading, error, refetch } = usePolling<ApprovalItem[]>(
    () =>
      api.getApprovalQueue({
        status: statusFilter || undefined,
        item_type: typeFilter || undefined,
      }),
    10000,
    [statusFilter, typeFilter]
  );

  function startEditing(item: ApprovalItem) {
    setEditing(true);
    setEditTitle(item.title);
    setEditContent(item.content || '');
  }

  function cancelEditing() {
    setEditing(false);
    setEditTitle('');
    setEditContent('');
  }

  async function saveEdit() {
    if (!selectedItem) return;
    setSaving(true);
    try {
      const updated = await api.updateApprovalItem(selectedItem.id, {
        title: editTitle,
        content: editContent,
      });
      setSelectedItem(updated);
      setEditing(false);
      refetch();
    } catch {
      // handled by API client
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish(item: ApprovalItem) {
    setActionLoading(item.id);
    try {
      await api.approveAndPublish(item.id, { publish_external: publishExternal });
      refetch();
      if (selectedItem?.id === item.id) setSelectedItem(null);
      setEditing(false);
      setPublishExternal(false);
    } catch {
      // handled by API client
    } finally {
      setActionLoading(null);
    }
  }

  async function handleCopy(item: ApprovalItem) {
    setActionLoading(item.id);
    try {
      const { content } = await api.approveAndCopy(item.id);
      await copyToClipboard(content);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
      refetch();
    } catch {
      // handled
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReject(item: ApprovalItem) {
    setActionLoading(item.id);
    try {
      await api.rejectApproval(item.id);
      refetch();
      if (selectedItem?.id === item.id) setSelectedItem(null);
      setEditing(false);
    } catch {
      // handled
    } finally {
      setActionLoading(null);
    }
  }

  function handleSelectItem(item: ApprovalItem) {
    setSelectedItem(item);
    setEditing(false);
    setPublishExternal(false);
  }

  if (loading && !data) return <PageLoader />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Approval Queue</h1>
        <div className="flex gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ApprovalStatus | '')}
            className="input-field"
          >
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="in_review">In Review</option>
            <option value="approved">Approved</option>
            <option value="published">Published</option>
            <option value="rejected">Rejected</option>
          </select>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as WorkflowType | '')}
            className="input-field"
          >
            <option value="">All Types</option>
            <option value="agenda">Agenda</option>
            <option value="meeting_notes">Meeting Notes</option>
            <option value="health_update">Health Update</option>
          </select>
        </div>
      </div>

      {error && <ErrorAlert message={error} onRetry={refetch} />}
      {copySuccess && (
        <div className="rounded-md bg-green-50 p-3 text-sm text-green-700">
          Content copied to clipboard.
        </div>
      )}

      {data && data.length === 0 ? (
        <EmptyState
          title="No items in the queue"
          description="Upload a transcript or wait for scheduled agenda generation."
        />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* List */}
          <div className="lg:col-span-1 space-y-3 max-h-[calc(100vh-12rem)] overflow-y-auto">
            {data?.map((item) => (
              <div
                key={item.id}
                onClick={() => handleSelectItem(item)}
                className={classNames(
                  'card cursor-pointer hover:shadow-md transition-shadow',
                  selectedItem?.id === item.id && 'ring-2 ring-indigo-500'
                )}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={getApprovalBadge(item.status)}>
                        {getApprovalLabel(item.status)}
                      </span>
                      <span className="badge-blue">
                        {getWorkflowTypeLabel(item.item_type)}
                      </span>
                    </div>
                    <h3 className="mt-2 text-sm font-semibold text-gray-900 truncate">{item.title}</h3>
                    <p className="mt-1 text-xs text-gray-500">
                      {formatTimeAgo(item.created_at)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Preview / Edit Panel */}
          <div className="lg:col-span-2">
            {selectedItem ? (
              <div className="card sticky top-6">
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <span className={getApprovalBadge(selectedItem.status)}>
                      {getApprovalLabel(selectedItem.status)}
                    </span>
                    <span className="badge-blue">
                      {getWorkflowTypeLabel(selectedItem.item_type)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedItem.google_doc_url && (
                      <a
                        href={selectedItem.google_doc_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-indigo-600 hover:text-indigo-500"
                      >
                        Open in Google Docs
                      </a>
                    )}
                    {!editing && (selectedItem.status === 'draft' || selectedItem.status === 'in_review' || selectedItem.status === 'rejected') && (
                      <button
                        onClick={() => startEditing(selectedItem)}
                        className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                      >
                        <PencilSquareIcon className="h-4 w-4" />
                        Edit
                      </button>
                    )}
                  </div>
                </div>

                {editing ? (
                  /* Edit Mode */
                  <div className="space-y-4">
                    <div>
                      <label className="label">Title</label>
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        className="input-field mt-1"
                      />
                    </div>
                    <div>
                      <label className="label">Content</label>
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        className="input-field mt-1 font-mono text-sm min-h-[400px]"
                        rows={20}
                      />
                    </div>
                    <div className="flex gap-2 border-t border-gray-200 pt-4">
                      <button
                        onClick={saveEdit}
                        disabled={saving}
                        className="btn-primary text-sm"
                      >
                        {saving ? 'Saving...' : 'Save Changes'}
                      </button>
                      <button
                        onClick={cancelEditing}
                        disabled={saving}
                        className="btn-secondary text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Preview Mode */
                  <>
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">{selectedItem.title}</h3>
                    <div className="prose prose-sm max-w-none max-h-[500px] overflow-y-auto border border-gray-100 rounded-md p-4 bg-gray-50">
                      <div className="whitespace-pre-wrap text-sm text-gray-700">
                        {selectedItem.content}
                      </div>
                    </div>

                    {/* Action Buttons */}
                    {(selectedItem.status === 'draft' || selectedItem.status === 'in_review' || selectedItem.status === 'rejected') && (
                      <div className="mt-4 border-t border-gray-200 pt-4 space-y-3">
                        {selectedItem.item_type === 'agenda' && (
                          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={publishExternal}
                              onChange={(e) => setPublishExternal(e.target.checked)}
                              className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-600"
                            />
                            Also post to external Slack channel
                          </label>
                        )}
                      <div className="flex gap-2">
                        <button
                          onClick={() => startEditing(selectedItem)}
                          disabled={actionLoading === selectedItem.id}
                          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                        >
                          <PencilSquareIcon className="h-4 w-4" />
                          Edit
                        </button>
                        <button
                          onClick={() => handlePublish(selectedItem)}
                          disabled={actionLoading === selectedItem.id}
                          className="btn-success flex items-center gap-1.5 text-sm"
                        >
                          <CheckCircleIcon className="h-4 w-4" />
                          Approve & Publish
                        </button>
                        <button
                          onClick={() => handleCopy(selectedItem)}
                          disabled={actionLoading === selectedItem.id}
                          className="btn-secondary flex items-center gap-1.5 text-sm"
                        >
                          <ClipboardIcon className="h-4 w-4" />
                          Approve & Copy
                        </button>
                        <button
                          onClick={() => handleReject(selectedItem)}
                          disabled={actionLoading === selectedItem.id}
                          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-red-700 bg-red-50 hover:bg-red-100 rounded-md transition-colors"
                        >
                          <XCircleIcon className="h-4 w-4" />
                          Reject
                        </button>
                      </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            ) : (
              <div className="card text-center py-16 text-sm text-gray-500">
                <EyeIcon className="h-10 w-10 mx-auto text-gray-300 mb-3" />
                <p className="font-medium">Select an item to preview</p>
                <p className="mt-1 text-xs">Click on an item from the list to view, edit, or approve it.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
