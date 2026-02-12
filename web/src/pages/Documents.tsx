import { useState } from 'react';
import { DocumentTextIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline';
import { useApi } from '../hooks/useApi';
import api from '../services/api';
import { PageLoader } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import {
  formatDateTime,
  getApprovalBadge,
  getApprovalLabel,
  getWorkflowTypeLabel,
  classNames,
} from '../utils';
import type { ApprovalItem, WorkflowType } from '../types';

export function Documents() {
  const [typeFilter, setTypeFilter] = useState<WorkflowType | ''>('');
  const [selectedDoc, setSelectedDoc] = useState<ApprovalItem | null>(null);

  const { data, loading, error, refetch } = useApi<ApprovalItem[]>(
    () =>
      api.getApprovalQueue({
        item_type: typeFilter || undefined,
      }),
    [typeFilter]
  );

  // Filter to only agenda and meeting_notes types
  const documents = data?.filter(
    (item) => item.item_type === 'agenda' || item.item_type === 'meeting_notes'
  ) || [];

  if (loading && !data) return <PageLoader />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Agendas & Notes</h1>
        <div className="flex gap-3">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as WorkflowType | '')}
            className="input-field"
          >
            <option value="">All Types</option>
            <option value="agenda">Agendas</option>
            <option value="meeting_notes">Meeting Notes</option>
          </select>
        </div>
      </div>

      {error && <ErrorAlert message={error} onRetry={refetch} />}

      {documents.length === 0 ? (
        <EmptyState
          icon={<DocumentTextIcon className="h-12 w-12" />}
          title="No documents yet"
          description="Documents will appear here when agendas are generated or transcripts are processed."
        />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-3">
            {documents.map((doc) => (
              <div
                key={doc.id}
                onClick={() => setSelectedDoc(doc)}
                className={classNames(
                  'card cursor-pointer hover:shadow-md transition-shadow',
                  selectedDoc?.id === doc.id && 'ring-2 ring-indigo-500'
                )}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={getApprovalBadge(doc.status)}>
                        {getApprovalLabel(doc.status)}
                      </span>
                      <span className="badge-blue">
                        {getWorkflowTypeLabel(doc.item_type)}
                      </span>
                    </div>
                    <h3 className="mt-2 text-sm font-semibold text-gray-900">{doc.title}</h3>
                    <p className="mt-1 text-xs text-gray-500">
                      {formatDateTime(doc.created_at)}
                    </p>
                  </div>
                  {doc.google_doc_url && (
                    <a
                      href={doc.google_doc_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-indigo-600 hover:text-indigo-500"
                      title="Open in Google Docs"
                    >
                      <ArrowTopRightOnSquareIcon className="h-5 w-5" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Preview Panel */}
          <div className="lg:col-span-1">
            {selectedDoc ? (
              <div className="card sticky top-6">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">{selectedDoc.title}</h3>
                <p className="text-xs text-gray-500 mb-4">
                  {formatDateTime(selectedDoc.created_at)}
                </p>
                <div className="prose prose-sm max-w-none max-h-[calc(100vh-300px)] overflow-y-auto">
                  <div className="whitespace-pre-wrap text-sm text-gray-700">
                    {selectedDoc.content}
                  </div>
                </div>
              </div>
            ) : (
              <div className="card text-center py-8 text-sm text-gray-500">
                <DocumentTextIcon className="h-8 w-8 mx-auto text-gray-300 mb-2" />
                Select a document to preview
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
