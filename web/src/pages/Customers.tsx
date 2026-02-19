import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PlusIcon, PencilSquareIcon, TrashIcon } from '@heroicons/react/24/outline';
import { useApi } from '../hooks/useApi';
import api from '../services/api';
import { PageLoader } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { formatDate, getHealthDot, classNames } from '../utils';
import type { Customer } from '../types';

export function Customers() {
  const { data: customers, loading, error, refetch } = useApi<Customer[]>(
    () => api.getCustomers(),
    []
  );
  const [deleteTarget, setDeleteTarget] = useState<Customer | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteCustomer(deleteTarget.id);
      setDeleteTarget(null);
      refetch();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setDeleteError(detail || 'Failed to delete customer. It may have related records.');
    } finally {
      setDeleting(false);
    }
  }

  if (loading && !customers) return <PageLoader />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Customers</h1>
        <Link to="/customers/new" className="btn-primary">
          <PlusIcon className="h-4 w-4 mr-2" />
          Add Customer
        </Link>
      </div>

      {error && <ErrorAlert message={error} onRetry={refetch} />}

      {customers && customers.length === 0 ? (
        <EmptyState
          title="No customers yet"
          description="Add your first customer to get started with workflows."
          action={
            <Link to="/customers/new" className="btn-primary">
              <PlusIcon className="h-4 w-4 mr-2" />
              Add Customer
            </Link>
          }
        />
      ) : (
        <div className="card overflow-hidden !p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Customer</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Health</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cadence</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Update</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Integrations</th>
                <th className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {customers?.map((customer) => (
                <tr key={customer.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div>
                      <div className="text-sm font-medium text-gray-900">{customer.name}</div>
                      <div className="text-xs text-gray-500">{customer.slug}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className={classNames('h-3 w-3 rounded-full', getHealthDot(customer.health_status))} />
                      <span className="text-sm capitalize">{customer.health_status}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 capitalize">
                    {customer.cadence}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(customer.last_health_update)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex gap-1">
                      <IntegrationDot label="Linear" connected={!!customer.linear_project_id} />
                      <IntegrationDot label="Slack Int" connected={!!customer.slack_internal_channel_id} />
                      <IntegrationDot label="Slack Ext" connected={!!customer.slack_external_channel_id} />
                      <IntegrationDot label="Notion" connected={!!customer.notion_page_id} />
                      <IntegrationDot label="GCal" connected={!!customer.google_calendar_event_pattern} />
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        to={`/customers/${customer.id}`}
                        className="text-indigo-600 hover:text-indigo-900"
                        title="Edit"
                      >
                        <PencilSquareIcon className="h-5 w-5" />
                      </Link>
                      <button
                        onClick={() => setDeleteTarget(customer)}
                        className="text-red-600 hover:text-red-900"
                        title="Delete"
                      >
                        <TrashIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {deleteError && (
        <ErrorAlert message={deleteError} onDismiss={() => setDeleteError(null)} />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => { setDeleteTarget(null); setDeleteError(null); }}
        onConfirm={handleDelete}
        title="Delete Customer"
        message={`Are you sure you want to delete "${deleteTarget?.name}"? This will also remove all related workflows, approvals, and documents. This action cannot be undone.`}
        confirmLabel="Delete"
        loading={deleting}
      />
    </div>
  );
}

function IntegrationDot({ label, connected }: { label: string; connected: boolean }) {
  return (
    <span
      title={`${label}: ${connected ? 'Configured' : 'Not configured'}`}
      className={classNames(
        'h-2 w-2 rounded-full',
        connected ? 'bg-green-500' : 'bg-gray-300'
      )}
    />
  );
}
