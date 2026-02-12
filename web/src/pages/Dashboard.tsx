import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  CalendarDaysIcon,
  ClipboardDocumentCheckIcon,
  ArrowUpTrayIcon,
  DocumentPlusIcon,
} from '@heroicons/react/24/outline';
import { useApi } from '../hooks/useApi';
import api from '../services/api';
import { PageLoader } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { formatDateTime, formatTimeAgo, classNames } from '../utils';
import type { DashboardStats, Customer } from '../types';

export function Dashboard() {
  const navigate = useNavigate();
  const [showAgendaForm, setShowAgendaForm] = useState(false);
  const [agendaCustomerId, setAgendaCustomerId] = useState('');
  const [agendaMeetingDate, setAgendaMeetingDate] = useState('');
  const [agendaGenerating, setAgendaGenerating] = useState(false);
  const [agendaError, setAgendaError] = useState('');

  const { data: customers } = useApi<Customer[]>(() => api.getCustomers(), []);
  const { data: stats, loading, error, refetch } = useApi<DashboardStats>(
    () => api.getDashboard(),
    []
  );

  async function handleGenerateAgenda() {
    if (!agendaCustomerId) return;
    setAgendaGenerating(true);
    setAgendaError('');
    try {
      const result = await api.triggerAgendaGeneration(agendaCustomerId, agendaMeetingDate || undefined);
      if (result.status === 'failed') {
        setAgendaError(result.error_message || 'Agenda generation failed');
      } else {
        setShowAgendaForm(false);
        setAgendaCustomerId('');
        setAgendaMeetingDate('');
        navigate('/approvals');
      }
    } catch {
      setAgendaError('Failed to generate agenda. Check the backend logs.');
    } finally {
      setAgendaGenerating(false);
    }
  }

  if (loading && !stats) return <PageLoader />;

  // If backend is not connected yet, show a helpful placeholder
  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <ErrorAlert message={error} onRetry={refetch} />
        <DashboardPlaceholder />
      </div>
    );
  }

  if (!stats) return <DashboardPlaceholder />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex gap-3">
          <button
            onClick={() => setShowAgendaForm(!showAgendaForm)}
            className="btn-secondary"
          >
            <DocumentPlusIcon className="h-4 w-4 mr-2" />
            Generate Agenda
          </button>
          <Link to="/transcripts" className="btn-primary">
            <ArrowUpTrayIcon className="h-4 w-4 mr-2" />
            Upload Transcript
          </Link>
        </div>
      </div>

      {/* Agenda Generation Form */}
      {showAgendaForm && (
        <div className="card border border-indigo-200 bg-indigo-50/30">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Generate Meeting Agenda</h3>
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-700 mb-1">Customer</label>
              <select
                value={agendaCustomerId}
                onChange={(e) => setAgendaCustomerId(e.target.value)}
                className="input-field"
              >
                <option value="">Select customer...</option>
                {customers?.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div className="w-48">
              <label className="block text-xs font-medium text-gray-700 mb-1">Meeting Date</label>
              <input
                type="date"
                value={agendaMeetingDate}
                onChange={(e) => setAgendaMeetingDate(e.target.value)}
                className="input-field"
              />
            </div>
            <button
              onClick={handleGenerateAgenda}
              disabled={!agendaCustomerId || agendaGenerating}
              className="btn-primary whitespace-nowrap"
            >
              {agendaGenerating ? 'Generating...' : 'Generate'}
            </button>
          </div>
          {agendaError && (
            <p className="mt-2 text-sm text-red-600">{agendaError}</p>
          )}
          <p className="mt-2 text-xs text-gray-500">
            Uses last call notes, open Linear issues, and Slack mentions as context. Gracefully skips unavailable sources.
          </p>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Upcoming Meetings"
          value={stats.upcoming_meetings.length}
          icon={CalendarDaysIcon}
          href="/documents"
          color="bg-blue-500"
        />
        <StatCard
          title="Pending Approvals"
          value={stats.pending_approvals}
          icon={ClipboardDocumentCheckIcon}
          href="/approvals"
          color="bg-yellow-500"
        />
        <div className="card">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-gray-500">Customer Health</p>
            <Link to="/health" className="text-sm text-indigo-600 hover:text-indigo-500">View all</Link>
          </div>
          <div className="mt-3 flex items-center gap-4">
            <HealthCount color="bg-green-500" count={stats.customer_health.green} label="Green" />
            <HealthCount color="bg-yellow-500" count={stats.customer_health.yellow} label="Yellow" />
            <HealthCount color="bg-red-500" count={stats.customer_health.red} label="Red" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Upcoming Meetings */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">Upcoming Meetings</h2>
            <Link to="/documents" className="text-sm text-indigo-600 hover:text-indigo-500">View all</Link>
          </div>
          {stats.upcoming_meetings.length === 0 ? (
            <p className="text-sm text-gray-500 py-4 text-center">No upcoming meetings</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {stats.upcoming_meetings.slice(0, 5).map((event) => (
                <li key={event.id} className="py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{event.summary}</p>
                      {event.customer_name && (
                        <p className="text-xs text-gray-500">{event.customer_name}</p>
                      )}
                    </div>
                    <p className="text-xs text-gray-500">{formatDateTime(event.start)}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Recent Activity */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">Recent Activity</h2>
          </div>
          {stats.recent_activity.length === 0 ? (
            <p className="text-sm text-gray-500 py-4 text-center">No recent activity</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {stats.recent_activity.slice(0, 8).map((item) => (
                <li key={item.id} className="py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-700">{item.title}</p>
                      <p className="text-xs text-gray-500">{item.type} - {item.status}</p>
                    </div>
                    <p className="text-xs text-gray-400 whitespace-nowrap ml-4">{formatTimeAgo(item.created_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon: Icon,
  href,
  color,
}: {
  title: string;
  value: number;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  href: string;
  color: string;
}) {
  return (
    <Link to={href} className="card hover:shadow-md transition-shadow">
      <div className="flex items-center">
        <div className={classNames('flex-shrink-0 rounded-md p-3', color)}>
          <Icon className="h-6 w-6 text-white" />
        </div>
        <div className="ml-5">
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
        </div>
      </div>
    </Link>
  );
}

function HealthCount({ color, count, label }: { color: string; count: number; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={classNames('h-3 w-3 rounded-full', color)} />
      <span className="text-lg font-semibold text-gray-900">{count}</span>
      <span className="text-xs text-gray-500">{label}</span>
    </div>
  );
}

function DashboardPlaceholder() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      <div className="card text-center py-12">
        <h2 className="text-lg font-semibold text-gray-900">Welcome to TAM Workflow</h2>
        <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
          Get started by connecting your integrations in Settings, then add your first customer.
        </p>
        <div className="mt-6 flex items-center justify-center gap-4">
          <Link to="/settings" className="btn-primary">
            Go to Settings
          </Link>
          <Link to="/customers" className="btn-secondary">
            Add Customer
          </Link>
        </div>
      </div>
    </div>
  );
}
