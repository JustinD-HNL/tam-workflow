import { useState } from 'react';
import { HeartIcon, CheckCircleIcon } from '@heroicons/react/24/outline';
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

export function HealthDashboard() {
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);

  const { data: customers, loading: loadingCustomers, error: customersError, refetch: refetchCustomers } =
    useApi<Customer[]>(() => api.getCustomers(), []);

  const { data: pendingUpdates } =
    useApi<HealthUpdate[]>(() => api.getHealthUpdates({ approval_status: 'draft' }), []);

  const { data: history, loading: loadingHistory } = useApi<HealthUpdate[]>(
    () => (selectedCustomerId ? api.getHealthHistory(selectedCustomerId) : Promise.resolve([])),
    [selectedCustomerId]
  );

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
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm font-semibold text-gray-900">{update.customer_name}</span>
                        <span className={getApprovalBadge(update.approval_status)}>
                          {getApprovalLabel(update.approval_status)}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-sm">
                        <span className="flex items-center gap-1">
                          <span className={classNames('h-3 w-3 rounded-full', getHealthDot(update.previous_status))} />
                          <span className="capitalize">{update.previous_status}</span>
                        </span>
                        <span className="text-gray-400">&rarr;</span>
                        <span className="flex items-center gap-1">
                          <span className={classNames('h-3 w-3 rounded-full', getHealthDot(update.new_status))} />
                          <span className="capitalize font-medium">{update.new_status}</span>
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-gray-600">{update.summary}</p>
                      {update.key_risks.length > 0 && (
                        <div className="mt-2">
                          <p className="text-xs font-medium text-red-600">Risks:</p>
                          <ul className="text-xs text-gray-600 list-disc list-inside">
                            {update.key_risks.map((risk, i) => <li key={i}>{risk}</li>)}
                          </ul>
                        </div>
                      )}
                      {update.opportunities.length > 0 && (
                        <div className="mt-2">
                          <p className="text-xs font-medium text-green-600">Opportunities:</p>
                          <ul className="text-xs text-gray-600 list-disc list-inside">
                            {update.opportunities.map((opp, i) => <li key={i}>{opp}</li>)}
                          </ul>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <button className="p-1.5 text-green-600 hover:bg-green-50 rounded-md" title="Approve">
                        <CheckCircleIcon className="h-5 w-5" />
                      </button>
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
