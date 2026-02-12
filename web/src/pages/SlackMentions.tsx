import { useState } from 'react';
import {
  ChatBubbleLeftRightIcon,
  TicketIcon,
  CheckIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline';
import { useApi } from '../hooks/useApi';
import api from '../services/api';
import { PageLoader } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { formatTimeAgo, classNames } from '../utils';
import type { SlackMention, Customer } from '../types';

export function SlackMentions() {
  const [customerFilter, setCustomerFilter] = useState('');
  const [showHandled, setShowHandled] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const { data: customers } = useApi<Customer[]>(() => api.getCustomers(), []);

  const { data, loading, error, refetch } = useApi<SlackMention[]>(
    () =>
      api.getSlackMentions({
        customer_id: customerFilter || undefined,
        handled: showHandled ? undefined : false,
      }),
    [customerFilter, showHandled]
  );

  async function handleCreateIssue(mention: SlackMention) {
    setActionLoading(mention.id);
    try {
      await api.createIssueFromMention(mention.id);
      refetch();
    } catch {
      // handled
    } finally {
      setActionLoading(null);
    }
  }

  async function handleMarkHandled(mention: SlackMention) {
    setActionLoading(mention.id);
    try {
      await api.markMentionHandled(mention.id);
      refetch();
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
        <h1 className="text-2xl font-bold text-gray-900">Slack Mentions</h1>
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
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={showHandled}
              onChange={(e) => setShowHandled(e.target.checked)}
              className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-600"
            />
            Show handled
          </label>
        </div>
      </div>

      {error && <ErrorAlert message={error} onRetry={refetch} />}

      {data && data.length === 0 ? (
        <EmptyState
          icon={<ChatBubbleLeftRightIcon className="h-12 w-12" />}
          title={showHandled ? 'No mentions found' : 'No unhandled mentions'}
          description="Mentions of you in external Slack channels will appear here."
        />
      ) : (
        <div className="space-y-3">
          {data?.map((mention) => (
            <div
              key={mention.id}
              className={classNames(
                'card',
                mention.handled && 'opacity-60'
              )}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-gray-900">{mention.user_name}</span>
                    <span className="text-xs text-gray-400">in #{mention.channel_name}</span>
                    {mention.customer_id && (
                      <span className="badge-blue">Customer</span>
                    )}
                    {mention.handled && (
                      <span className="badge-green">Handled</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">{mention.message_text}</p>
                  <p className="mt-1 text-xs text-gray-400">{formatTimeAgo(mention.created_at)}</p>
                </div>
                <div className="flex items-center gap-1 ml-4">
                  {!mention.handled && (
                    <>
                      <button
                        onClick={() => handleCreateIssue(mention)}
                        disabled={actionLoading === mention.id}
                        className="p-1.5 text-indigo-600 hover:bg-indigo-50 rounded-md"
                        title="Create Linear Issue"
                      >
                        <TicketIcon className="h-5 w-5" />
                      </button>
                      <button
                        onClick={() => handleMarkHandled(mention)}
                        disabled={actionLoading === mention.id}
                        className="p-1.5 text-green-600 hover:bg-green-50 rounded-md"
                        title="Mark as Handled"
                      >
                        <CheckIcon className="h-5 w-5" />
                      </button>
                    </>
                  )}
                  {mention.permalink && (
                    <a
                      href={mention.permalink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 text-gray-400 hover:bg-gray-50 rounded-md"
                      title="View in Slack"
                    >
                      <ArrowTopRightOnSquareIcon className="h-5 w-5" />
                    </a>
                  )}
                  {mention.linear_issue_id && (
                    <span className="text-xs text-green-600 font-medium">Issue created</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
