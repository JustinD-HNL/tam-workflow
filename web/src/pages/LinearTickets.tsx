import { useState } from 'react';
import {
  TicketIcon,
  CheckIcon,
  ArrowTopRightOnSquareIcon,

} from '@heroicons/react/24/outline';
import { useApi } from '../hooks/useApi';
import api from '../services/api';
import { PageLoader } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import {
  formatTimeAgo,
  getApprovalBadge,
  getApprovalLabel,
  getPriorityColor,
  getPriorityLabel,
  classNames,
} from '../utils';
import type { LinearTicket, Customer } from '../types';

export function LinearTickets() {
  const [customerFilter, setCustomerFilter] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [actionLoading, setActionLoading] = useState(false);

  const { data: customers } = useApi<Customer[]>(() => api.getCustomers(), []);

  const { data, loading, error, refetch } = useApi<LinearTicket[]>(
    () => api.getLinearTickets({ customer_id: customerFilter || undefined }),
    [customerFilter]
  );

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (!data) return;
    const pendingIds = data.filter((t) => t.approval_status === 'draft').map((t) => t.id);
    if (selectedIds.size === pendingIds.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(pendingIds));
    }
  }

  async function handleBulkApprove() {
    if (selectedIds.size === 0) return;
    setActionLoading(true);
    try {
      await api.bulkApproveLinearTickets(Array.from(selectedIds));
      setSelectedIds(new Set());
      refetch();
    } catch {
      // handled
    } finally {
      setActionLoading(false);
    }
  }

  async function handleApprove(id: string) {
    setActionLoading(true);
    try {
      await api.approveLinearTicket(id);
      refetch();
    } catch {
      // handled
    } finally {
      setActionLoading(false);
    }
  }

  if (loading && !data) return <PageLoader />;

  const pendingCount = data?.filter((t) => t.approval_status === 'draft').length || 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Linear Tickets</h1>
        <div className="flex items-center gap-3">
          <select
            value={customerFilter}
            onChange={(e) => setCustomerFilter(e.target.value)}
            className="input-field"
          >
            <option value="">All Customers</option>
            {customers?.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {selectedIds.size > 0 && (
            <button
              onClick={handleBulkApprove}
              disabled={actionLoading}
              className="btn-success"
            >
              <CheckIcon className="h-4 w-4 mr-1" />
              Approve {selectedIds.size} Selected
            </button>
          )}
        </div>
      </div>

      {error && <ErrorAlert message={error} onRetry={refetch} />}

      {data && data.length === 0 ? (
        <EmptyState
          icon={<TicketIcon className="h-12 w-12" />}
          title="No tickets"
          description="Tickets will appear here when extracted from meeting notes, Slack threads, or created manually."
        />
      ) : (
        <div className="card overflow-hidden !p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {pendingCount > 0 && (
                  <th className="px-4 py-3 w-10">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === pendingCount && pendingCount > 0}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-600"
                    />
                  </th>
                )}
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Customer</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Priority</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                <th className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data?.map((ticket) => (
                <tr key={ticket.id} className="hover:bg-gray-50">
                  {pendingCount > 0 && (
                    <td className="px-4 py-4 w-10">
                      {ticket.approval_status === 'draft' && (
                        <input
                          type="checkbox"
                          checked={selectedIds.has(ticket.id)}
                          onChange={() => toggleSelect(ticket.id)}
                          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-600"
                        />
                      )}
                    </td>
                  )}
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-gray-900 max-w-xs truncate">{ticket.title}</div>
                    {ticket.description && (
                      <div className="text-xs text-gray-500 max-w-xs truncate">{ticket.description}</div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {ticket.customer_name || '—'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={classNames('text-sm font-medium', getPriorityColor(ticket.priority))}>
                      {getPriorityLabel(ticket.priority)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 capitalize">
                    {ticket.source.replace('_', ' ')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={getApprovalBadge(ticket.approval_status)}>
                      {getApprovalLabel(ticket.approval_status)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-xs text-gray-500">
                    {formatTimeAgo(ticket.created_at)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                    <div className="flex items-center justify-end gap-2">
                      {ticket.approval_status === 'draft' && (
                        <button
                          onClick={() => handleApprove(ticket.id)}
                          disabled={actionLoading}
                          className="text-green-600 hover:text-green-800"
                          title="Approve & Create in Linear"
                        >
                          <CheckIcon className="h-5 w-5" />
                        </button>
                      )}
                      {ticket.linear_issue_url && (
                        <a
                          href={ticket.linear_issue_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-indigo-600 hover:text-indigo-800"
                          title="View in Linear"
                        >
                          <ArrowTopRightOnSquareIcon className="h-5 w-5" />
                        </a>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
