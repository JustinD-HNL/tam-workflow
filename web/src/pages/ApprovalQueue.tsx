import { useState } from 'react';
import { CheckCircleIcon, XCircleIcon, ClipboardIcon, EyeIcon } from '@heroicons/react/24/outline';
import { useApi } from '../hooks/useApi';
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

  const { data, loading, error, refetch } = useApi<ApprovalItem[]>(
    () =>
      api.getApprovalQueue({
        status: statusFilter || undefined,
        item_type: typeFilter || undefined,
      }),
    [statusFilter, typeFilter]
  );

  async function handlePublish(item: ApprovalItem) {
    setActionLoading(item.id);
    try {
      await api.approveAndPublish(item.id);
      refetch();
      if (selectedItem?.id === item.id) setSelectedItem(null);
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
    } catch {
      // handled
    } finally {
      setActionLoading(null);
    }
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
          <div className="lg:col-span-2 space-y-3">
            {data?.map((item) => (
              <div
                key={item.id}
                onClick={() => setSelectedItem(item)}
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
                  <div className="flex items-center gap-1 ml-4">
                    {(item.status === 'draft' || item.status === 'in_review') && (
                      <>
                        <button
                          onClick={(e) => { e.stopPropagation(); handlePublish(item); }}
                          disabled={actionLoading === item.id}
                          className="p-1.5 text-green-600 hover:bg-green-50 rounded-md"
                          title="Approve & Publish"
                        >
                          <CheckCircleIcon className="h-5 w-5" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleCopy(item); }}
                          disabled={actionLoading === item.id}
                          className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-md"
                          title="Approve & Copy"
                        >
                          <ClipboardIcon className="h-5 w-5" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleReject(item); }}
                          disabled={actionLoading === item.id}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded-md"
                          title="Reject"
                        >
                          <XCircleIcon className="h-5 w-5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Preview Panel */}
          <div className="lg:col-span-1">
            {selectedItem ? (
              <div className="card sticky top-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-900">Preview</h3>
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
                </div>
                <div className="prose prose-sm max-w-none max-h-96 overflow-y-auto">
                  <h4>{selectedItem.title}</h4>
                  <div className="whitespace-pre-wrap text-sm text-gray-700">
                    {selectedItem.content}
                  </div>
                </div>
                {(selectedItem.status === 'draft' || selectedItem.status === 'in_review') && (
                  <div className="mt-4 flex gap-2 border-t border-gray-200 pt-4">
                    <button
                      onClick={() => handlePublish(selectedItem)}
                      disabled={actionLoading === selectedItem.id}
                      className="btn-success flex-1 text-xs"
                    >
                      Approve & Publish
                    </button>
                    <button
                      onClick={() => handleCopy(selectedItem)}
                      disabled={actionLoading === selectedItem.id}
                      className="btn-secondary flex-1 text-xs"
                    >
                      Approve & Copy
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="card text-center py-8 text-sm text-gray-500">
                <EyeIcon className="h-8 w-8 mx-auto text-gray-300 mb-2" />
                Select an item to preview
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
