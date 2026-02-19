import { useState } from 'react';
import {
  LightBulbIcon,
  ArrowTopRightOnSquareIcon,
  ArrowDownTrayIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  ChevronUpDownIcon,
} from '@heroicons/react/24/outline';
import api from '../services/api';
import { PageLoader } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { useApi } from '../hooks/useApi';
import { classNames, formatDate, formatTimeAgo } from '../utils';
import type { FeatureRequest, Customer } from '../types';

const PRIORITY_COLORS: Record<number, string> = {
  0: 'text-gray-400',
  1: 'text-red-600',
  2: 'text-orange-500',
  3: 'text-yellow-600',
  4: 'text-blue-500',
};

const STATUS_TYPE_COLORS: Record<string, string> = {
  backlog: 'bg-gray-100 text-gray-700',
  unstarted: 'bg-gray-100 text-gray-700',
  started: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  canceled: 'bg-red-100 text-red-700',
};

type SortKey = 'identifier' | 'title' | 'status' | 'priority' | 'assignee' | 'project' | 'team' | 'updated_at';
type SortDir = 'asc' | 'desc';

function compareFR(a: FeatureRequest, b: FeatureRequest, key: SortKey): number {
  switch (key) {
    case 'priority':
      return (a.priority || 0) - (b.priority || 0);
    case 'updated_at':
      return (a.updated_at || '').localeCompare(b.updated_at || '');
    case 'identifier':
      return a.identifier.localeCompare(b.identifier);
    case 'title':
      return a.title.localeCompare(b.title);
    case 'status':
      return (a.status || '').localeCompare(b.status || '');
    case 'assignee':
      return (a.assignee || '').localeCompare(b.assignee || '');
    case 'project':
      return (a.project || '').localeCompare(b.project || '');
    case 'team':
      return (a.team || '').localeCompare(b.team || '');
    default:
      return 0;
  }
}

export function FeatureRequests() {
  const [searchInput, setSearchInput] = useState('');
  const [activeQuery, setActiveQuery] = useState('');
  const [includeCompleted, setIncludeCompleted] = useState(false);
  const [selectedItem, setSelectedItem] = useState<FeatureRequest | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('updated_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const { data: customers } = useApi<Customer[]>(() => api.getCustomers(), []);

  const { data, loading, error, execute } = useApi<FeatureRequest[]>(
    () => api.searchFeatureRequests(activeQuery, includeCompleted),
    [activeQuery, includeCompleted],
    { immediate: false }
  );

  function handleSearch(e?: React.FormEvent) {
    e?.preventDefault();
    const q = searchInput.trim();
    if (!q) return;
    setActiveQuery(q);
    setSelectedItem(null);
    // If the query changed, useApi deps will trigger. But if same query re-submitted, force execute.
    if (q === activeQuery) {
      execute();
    }
  }

  function handleCustomerSelect(name: string) {
    setSearchInput(name);
    setActiveQuery(name);
    setSelectedItem(null);
  }

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'updated_at' || key === 'priority' ? 'desc' : 'asc');
    }
  }

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) return <ChevronUpDownIcon className="h-3.5 w-3.5 text-gray-300" />;
    return sortDir === 'asc'
      ? <ChevronUpIcon className="h-3.5 w-3.5 text-indigo-600" />
      : <ChevronDownIcon className="h-3.5 w-3.5 text-indigo-600" />;
  }

  const sortedData = data
    ? [...data].sort((a, b) => {
        const cmp = compareFR(a, b, sortKey);
        return sortDir === 'asc' ? cmp : -cmp;
      })
    : null;

  function handleDownloadCsv() {
    if (!activeQuery) return;
    const url = api.getFeatureRequestsCsvUrl(activeQuery, includeCompleted);
    window.open(url, '_blank');
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Feature Requests</h1>
        {data && data.length > 0 && (
          <button onClick={handleDownloadCsv} className="btn-secondary">
            <ArrowDownTrayIcon className="h-4 w-4 mr-1" />
            Export CSV
          </button>
        )}
      </div>

      {/* Search Controls */}
      <div className="card">
        <form onSubmit={handleSearch} className="flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search Linear Issues
            </label>
            <div className="relative">
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search by customer name, keyword, or issue title..."
                className="input-field pr-10"
              />
              <MagnifyingGlassIcon className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Customer
            </label>
            <select
              onChange={(e) => {
                if (e.target.value) handleCustomerSelect(e.target.value);
              }}
              className="input-field"
              value=""
            >
              <option value="">Select customer...</option>
              {customers?.map((c) => (
                <option key={c.id} value={c.name}>{c.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2 pb-2">
            <input
              type="checkbox"
              id="includeCompleted"
              checked={includeCompleted}
              onChange={(e) => setIncludeCompleted(e.target.checked)}
              className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-600"
            />
            <label htmlFor="includeCompleted" className="text-sm text-gray-600 whitespace-nowrap">
              Include completed
            </label>
          </div>
          <button type="submit" disabled={!searchInput.trim() || loading} className="btn-primary">
            <MagnifyingGlassIcon className="h-4 w-4 mr-1" />
            Search
          </button>
        </form>
      </div>

      {error && <ErrorAlert message={error} onRetry={() => execute()} />}

      {loading && !data && <PageLoader />}

      {/* No search yet */}
      {!activeQuery && !data && !loading && (
        <EmptyState
          icon={<LightBulbIcon className="h-12 w-12" />}
          title="Search for feature requests"
          description="Search across all Linear projects by customer name or keyword to find feature requests and open issues."
        />
      )}

      {/* No results */}
      {activeQuery && data && data.length === 0 && !loading && (
        <EmptyState
          icon={<LightBulbIcon className="h-12 w-12" />}
          title="No issues found"
          description={`No Linear issues matched "${activeQuery}". Try a different search term.`}
        />
      )}

      {/* Results */}
      {data && data.length > 0 && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              {data.length} issue{data.length !== 1 ? 's' : ''} found
              {loading && ' (refreshing...)'}
            </p>
          </div>

          <div className="flex gap-6">
            {/* Results Table */}
            <div className={classNames('flex-shrink-0 overflow-auto', selectedItem ? 'w-1/2' : 'w-full')}>
              <div className="card overflow-hidden !p-0">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      {([
                        ['identifier', 'ID'],
                        ['title', 'Title'],
                        ['status', 'Status'],
                        ['priority', 'Priority'],
                      ] as [SortKey, string][]).map(([key, label]) => (
                        <th
                          key={key}
                          onClick={() => toggleSort(key)}
                          className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none hover:text-gray-700"
                        >
                          <span className="inline-flex items-center gap-1">
                            {label} <SortIcon col={key} />
                          </span>
                        </th>
                      ))}
                      {!selectedItem && (
                        <>
                          {([
                            ['assignee', 'Assignee'],
                            ['project', 'Project'],
                            ['team', 'Team'],
                          ] as [SortKey, string][]).map(([key, label]) => (
                            <th
                              key={key}
                              onClick={() => toggleSort(key)}
                              className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none hover:text-gray-700"
                            >
                              <span className="inline-flex items-center gap-1">
                                {label} <SortIcon col={key} />
                              </span>
                            </th>
                          ))}
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Labels</th>
                        </>
                      )}
                      <th
                        onClick={() => toggleSort('updated_at')}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none hover:text-gray-700 whitespace-nowrap"
                      >
                        <span className="inline-flex items-center gap-1">
                          Updated <SortIcon col="updated_at" />
                        </span>
                      </th>
                      <th className="relative px-4 py-3"><span className="sr-only">Link</span></th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {sortedData?.map((item) => (
                      <tr
                        key={item.id}
                        onClick={() => setSelectedItem(item)}
                        className={classNames(
                          'cursor-pointer',
                          selectedItem?.id === item.id ? 'bg-indigo-50' : 'hover:bg-gray-50'
                        )}
                      >
                        <td className="px-4 py-3 whitespace-nowrap text-sm font-mono text-gray-500">
                          {item.identifier}
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-sm font-medium text-gray-900 max-w-xs truncate">
                            {item.title}
                          </div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={classNames(
                            'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                            STATUS_TYPE_COLORS[item.status_type] || 'bg-gray-100 text-gray-700'
                          )}>
                            {item.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={classNames('text-sm font-medium', PRIORITY_COLORS[item.priority] || 'text-gray-400')}>
                            {item.priority_label}
                          </span>
                        </td>
                        {!selectedItem && (
                          <>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                              {item.assignee || '—'}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                              {item.project || '—'}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                              {item.team || '—'}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-500">
                              <div className="flex flex-wrap gap-1 max-w-[200px]">
                                {item.labels.length > 0
                                  ? item.labels.map((label) => (
                                      <span key={label} className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                                        {label}
                                      </span>
                                    ))
                                  : '—'}
                              </div>
                            </td>
                          </>
                        )}
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500" title={formatDate(item.updated_at)}>
                          {formatTimeAgo(item.updated_at)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-right text-sm" onClick={(e) => e.stopPropagation()}>
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-indigo-600 hover:text-indigo-800"
                            title="View in Linear"
                          >
                            <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Detail Panel */}
            {selectedItem && (
              <div className="flex-1 min-w-0">
                <div className="card sticky top-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <span className="text-sm font-mono text-gray-500">{selectedItem.identifier}</span>
                      <h2 className="text-lg font-semibold text-gray-900">{selectedItem.title}</h2>
                    </div>
                    <button
                      onClick={() => setSelectedItem(null)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <XMarkIcon className="h-5 w-5" />
                    </button>
                  </div>

                  <div className="space-y-4">
                    <div className="flex flex-wrap gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">Status:</span>{' '}
                        <span className={classNames(
                          'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                          STATUS_TYPE_COLORS[selectedItem.status_type] || 'bg-gray-100 text-gray-700'
                        )}>
                          {selectedItem.status}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500">Priority:</span>{' '}
                        <span className={classNames('font-medium', PRIORITY_COLORS[selectedItem.priority] || 'text-gray-400')}>
                          {selectedItem.priority_label}
                        </span>
                      </div>
                      {selectedItem.assignee && (
                        <div>
                          <span className="text-gray-500">Assignee:</span>{' '}
                          <span className="text-gray-900">{selectedItem.assignee}</span>
                        </div>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-4 text-sm">
                      {selectedItem.project && (
                        <div>
                          <span className="text-gray-500">Project:</span>{' '}
                          <span className="text-gray-900">{selectedItem.project}</span>
                        </div>
                      )}
                      {selectedItem.team && (
                        <div>
                          <span className="text-gray-500">Team:</span>{' '}
                          <span className="text-gray-900">{selectedItem.team} ({selectedItem.team_key})</span>
                        </div>
                      )}
                    </div>

                    {selectedItem.labels.length > 0 && (
                      <div>
                        <span className="text-xs font-medium text-gray-500 uppercase">Labels</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {selectedItem.labels.map((label) => (
                            <span key={label} className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                              {label}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    <div>
                      <span className="text-xs font-medium text-gray-500 uppercase">Description</span>
                      <div className="mt-1 prose prose-sm max-w-none text-gray-700 bg-gray-50 rounded-md p-3 whitespace-pre-wrap max-h-96 overflow-y-auto">
                        {selectedItem.full_description || selectedItem.description || 'No description'}
                      </div>
                    </div>

                    <div className="text-xs text-gray-400 space-y-1">
                      <div>Created: {formatDate(selectedItem.created_at)}</div>
                      <div>Updated: {formatDate(selectedItem.updated_at)}</div>
                    </div>

                    <div className="pt-2 border-t">
                      <a
                        href={selectedItem.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-indigo-600 hover:text-indigo-500 flex items-center gap-1"
                      >
                        <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                        View in Linear
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
