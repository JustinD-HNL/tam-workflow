import { useState } from 'react';
import {
  HeartIcon,
  CheckCircleIcon,
  XCircleIcon,
  PencilIcon,
} from '@heroicons/react/24/outline';
import { useApi } from '../hooks/useApi';
import api from '../services/api';
import { PageLoader } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import {
  formatDate,
  getHealthDot,
  getApprovalBadge,
  getApprovalLabel,
  classNames,
} from '../utils';
import type { Customer, HealthUpdate } from '../types';

const RAG_OPTIONS = [
  { value: 'green', label: 'Green', dot: 'bg-green-500' },
  { value: 'yellow', label: 'Yellow', dot: 'bg-yellow-500' },
  { value: 'red', label: 'Red', dot: 'bg-red-500' },
];

export function HealthDashboard() {
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const [selectedUpdate, setSelectedUpdate] = useState<HealthUpdate | null>(null);
  const [editing, setEditing] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Edit fields
  const [editStatus, setEditStatus] = useState('green');
  const [editSummary, setEditSummary] = useState('');
  const [editRisks, setEditRisks] = useState('');
  const [editOpportunities, setEditOpportunities] = useState('');

  const { data: customers, loading: loadingCustomers, error: customersError, refetch: refetchCustomers } =
    useApi<Customer[]>(() => api.getCustomers(), []);

  const { data: pendingUpdates, refetch: refetchPending } =
    useApi<HealthUpdate[]>(() => api.getHealthUpdates({ approval_status: 'draft' }), []);

  const { data: history, loading: loadingHistory } = useApi<HealthUpdate[]>(
    () => (selectedCustomerId ? api.getHealthHistory(selectedCustomerId) : Promise.resolve([])),
    [selectedCustomerId]
  );

  function startEditing(update: HealthUpdate) {
    setSelectedUpdate(update);
    setEditStatus(update.new_status || 'green');
    setEditSummary(update.summary || '');
    setEditRisks(Array.isArray(update.key_risks) ? update.key_risks.join(', ') : (update.key_risks || ''));
    setEditOpportunities(Array.isArray(update.opportunities) ? update.opportunities.join(', ') : (update.opportunities || ''));
    setEditing(true);
  }

  function cancelEditing() {
    setEditing(false);
  }

  async function saveEdit() {
    if (!selectedUpdate) return;
    setActionLoading(true);
    try {
      await api.updateApprovalItem(selectedUpdate.id, {
        content: editSummary,
        metadata_json: {
          health_status: editStatus,
          key_risks: editRisks,
          opportunities: editOpportunities,
        },
      } as Partial<any>);
      setEditing(false);
      refetchPending();
    } catch {
      // handled
    } finally {
      setActionLoading(false);
    }
  }

  async function handlePublish(update: HealthUpdate) {
    setActionLoading(true);
    try {
      await api.approveAndPublish(update.id);
      setSelectedUpdate(null);
      setEditing(false);
      refetchPending();
      refetchCustomers();
    } catch {
      // handled
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject(update: HealthUpdate) {
    setActionLoading(true);
    try {
      await api.rejectApproval(update.id);
      setSelectedUpdate(null);
      setEditing(false);
      refetchPending();
    } catch {
      // handled
    } finally {
      setActionLoading(false);
    }
  }

  if (loadingCustomers && !customers) return <PageLoader />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Health Dashboard</h1>

      {customersError && <ErrorAlert message={customersError} onRetry={refetchCustomers} />}

      {/* Customer Health Grid */}
      {customers && customers.length === 0 ? (
        <EmptyState
          icon={<HeartIcon className="h-12 w-12" />}
          title="No customers"
          description="Add customers to track their health status."
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {customers?.map((customer) => (
              <div
                key={customer.id}
                onClick={() => setSelectedCustomerId(
                  selectedCustomerId === customer.id ? null : customer.id
                )}
                className={classNames(
                  'card cursor-pointer hover:shadow-md transition-shadow',
                  selectedCustomerId === customer.id && 'ring-2 ring-indigo-500'
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={classNames('h-4 w-4 rounded-full', getHealthDot(customer.health_status))} />
                    <div>
                      <h3 className="text-sm font-semibold text-gray-900">{customer.name}</h3>
                      <p className="text-xs text-gray-500 capitalize">{customer.cadence}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-500">Last updated</p>
                    <p className="text-xs font-medium text-gray-700">{formatDate(customer.last_health_update)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pending Health Updates */}
          {pendingUpdates && pendingUpdates.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold text-gray-900">Pending Health Updates</h2>
              {pendingUpdates.map((update) => (
                <div key={update.id} className="card">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm font-semibold text-gray-900">{update.customer_name}</span>
                        <span className={getApprovalBadge(update.approval_status)}>
                          {getApprovalLabel(update.approval_status)}
                        </span>
                      </div>

                      {editing && selectedUpdate?.id === update.id ? (
                        /* Edit Mode */
                        <div className="space-y-3 mt-3">
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">Health Status</label>
                            <div className="flex gap-2">
                              {RAG_OPTIONS.map((opt) => (
                                <button
                                  key={opt.value}
                                  onClick={() => setEditStatus(opt.value)}
                                  className={classNames(
                                    'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium border transition-colors',
                                    editStatus === opt.value
                                      ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                                      : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                                  )}
                                >
                                  <span className={classNames('h-3 w-3 rounded-full', opt.dot)} />
                                  {opt.label}
                                </button>
                              ))}
                            </div>
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">Summary</label>
                            <textarea
                              value={editSummary}
                              onChange={(e) => setEditSummary(e.target.value)}
                              rows={3}
                              className="input-field text-sm"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                              Key Risks <span className="text-gray-400 font-normal">(comma-separated)</span>
                            </label>
                            <input
                              type="text"
                              value={editRisks}
                              onChange={(e) => setEditRisks(e.target.value)}
                              className="input-field text-sm"
                              placeholder="e.g. Delayed migration, Budget concerns"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                              Opportunities <span className="text-gray-400 font-normal">(comma-separated)</span>
                            </label>
                            <input
                              type="text"
                              value={editOpportunities}
                              onChange={(e) => setEditOpportunities(e.target.value)}
                              className="input-field text-sm"
                              placeholder="e.g. Expansion to new team, Upsell opportunity"
                            />
                          </div>
                          <div className="flex items-center gap-2 pt-2">
                            <button
                              onClick={saveEdit}
                              disabled={actionLoading}
                              className="btn-primary text-sm"
                            >
                              {actionLoading ? 'Saving...' : 'Save Changes'}
                            </button>
                            <button
                              onClick={cancelEditing}
                              disabled={actionLoading}
                              className="btn-secondary text-sm"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        /* View Mode */
                        <>
                          <div className="flex items-center gap-3 text-sm">
                            {update.previous_status && (
                              <>
                                <span className="flex items-center gap-1">
                                  <span className={classNames('h-3 w-3 rounded-full', getHealthDot(update.previous_status))} />
                                  <span className="capitalize">{update.previous_status}</span>
                                </span>
                                <span className="text-gray-400">&rarr;</span>
                              </>
                            )}
                            <span className="flex items-center gap-1">
                              <span className={classNames('h-3 w-3 rounded-full', getHealthDot(update.new_status))} />
                              <span className="capitalize font-medium">{update.new_status}</span>
                            </span>
                          </div>
                          <p className="mt-2 text-sm text-gray-600">{update.summary}</p>
                          {update.key_risks && update.key_risks.length > 0 && (
                            <div className="mt-2">
                              <p className="text-xs font-medium text-red-600">Risks:</p>
                              <ul className="text-xs text-gray-600 list-disc list-inside">
                                {(Array.isArray(update.key_risks) ? update.key_risks : [update.key_risks]).map((risk, i) => (
                                  <li key={i}>{risk}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {update.opportunities && update.opportunities.length > 0 && (
                            <div className="mt-2">
                              <p className="text-xs font-medium text-green-600">Opportunities:</p>
                              <ul className="text-xs text-gray-600 list-disc list-inside">
                                {(Array.isArray(update.opportunities) ? update.opportunities : [update.opportunities]).map((opp, i) => (
                                  <li key={i}>{opp}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* Action Buttons */}
                          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
                            <button
                              onClick={() => startEditing(update)}
                              disabled={actionLoading}
                              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                            >
                              <PencilIcon className="h-4 w-4" />
                              Edit
                            </button>
                            <button
                              onClick={() => handlePublish(update)}
                              disabled={actionLoading}
                              className="btn-success text-sm flex items-center gap-1"
                            >
                              <CheckCircleIcon className="h-4 w-4" />
                              Approve & Publish
                            </button>
                            <button
                              onClick={() => handleReject(update)}
                              disabled={actionLoading}
                              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-red-700 bg-red-50 hover:bg-red-100 rounded-md transition-colors"
                            >
                              <XCircleIcon className="h-4 w-4" />
                              Reject
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* History */}
          {selectedCustomerId && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold text-gray-900">
                Health History: {customers?.find((c) => c.id === selectedCustomerId)?.name}
              </h2>
              {loadingHistory ? (
                <p className="text-sm text-gray-500">Loading...</p>
              ) : history && history.length === 0 ? (
                <p className="text-sm text-gray-500">No health history for this customer.</p>
              ) : (
                <div className="space-y-2">
                  {history?.map((update) => (
                    <div key={update.id} className="card !p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className={classNames('h-3 w-3 rounded-full', getHealthDot(update.new_status))} />
                          <span className="text-sm capitalize font-medium">{update.new_status}</span>
                          <span className="text-xs text-gray-500">{update.summary}</span>
                        </div>
                        <span className="text-xs text-gray-400">{formatDate(update.created_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
