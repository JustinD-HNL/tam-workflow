import { useState, useEffect, useRef } from 'react';
import {
  TicketIcon,
  CheckIcon,
  TrashIcon,
  PencilIcon,
  ArrowTopRightOnSquareIcon,
  XMarkIcon,
  ChevronDownIcon,
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
import type { LinearIssue, Customer } from '../types';

const PRIORITY_OPTIONS = [
  { value: '', label: 'No Priority' },
  { value: 'urgent', label: 'Urgent' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

interface LinearState {
  id: string;
  name: string;
  type: string;
}

interface LinearLabel {
  id: string;
  name: string;
  isGroup?: boolean;
  parentName?: string | null;
}

export function LinearIssues() {
  const [customerFilter, setCustomerFilter] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [actionLoading, setActionLoading] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<LinearIssue | null>(null);
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editAssignee, setEditAssignee] = useState('');
  const [editPriority, setEditPriority] = useState('');
  const [editStateId, setEditStateId] = useState('');
  const [editLabelIds, setEditLabelIds] = useState<string[]>([]);
  const [availableStates, setAvailableStates] = useState<LinearState[]>([]);
  const [availableLabels, setAvailableLabels] = useState<LinearLabel[]>([]);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [labelsOpen, setLabelsOpen] = useState(false);
  const [labelSearch, setLabelSearch] = useState('');
  const labelsRef = useRef<HTMLDivElement>(null);
  const labelSearchRef = useRef<HTMLInputElement>(null);

  // Close labels dropdown when clicking outside
  useEffect(() => {
    if (!labelsOpen) {
      setLabelSearch('');
      return;
    }
    // Auto-focus search input when dropdown opens
    setTimeout(() => labelSearchRef.current?.focus(), 0);
    function handleClick(e: MouseEvent) {
      if (labelsRef.current && !labelsRef.current.contains(e.target as Node)) {
        setLabelsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [labelsOpen]);

  const { data: customers } = useApi<Customer[]>(() => api.getCustomers(), []);

  const { data, loading, error, refetch } = useApi<LinearIssue[]>(
    () => api.getLinearIssues({ customer_id: customerFilter || undefined }),
    [customerFilter]
  );

  function selectIssue(issue: LinearIssue) {
    setSelectedIssue(issue);
    setEditing(false);
    setLabelsOpen(false);

    // Pre-fetch labels for the detail view if this issue has label_ids
    if (issue.label_ids?.length > 0 && availableLabels.length === 0) {
      const customer = customers?.find((c) => c.id === issue.customer_id);
      const teamId = customer?.linear_task_defaults?.team_id;
      api.getLinearLabels(teamId).then((labels) => {
        setAvailableLabels(labels.filter((l: LinearLabel) => !l.isGroup));
      }).catch(() => {});
    }
  }

  function startEditing() {
    if (!selectedIssue) return;
    setEditTitle(selectedIssue.title);
    setEditDescription(selectedIssue.description || '');
    setEditAssignee(selectedIssue.assignee || '');
    setEditPriority(selectedIssue.priority || '');
    setEditStateId(selectedIssue.linear_state_id || '');
    setEditLabelIds(selectedIssue.label_ids || []);
    setEditing(true);
    setLabelsOpen(false);

    // Fetch Linear metadata (states + labels filtered to customer's team)
    const customer = customers?.find((c) => c.id === selectedIssue.customer_id);
    const teamId = customer?.linear_task_defaults?.team_id;
    setMetadataLoading(true);
    Promise.all([
      teamId ? api.getLinearTeamStates(teamId).catch(() => []) : Promise.resolve([]),
      api.getLinearLabels(teamId).catch(() => []),
    ]).then(([states, labels]) => {
      setAvailableStates(states);
      // Filter out group/parent labels — they can't be assigned to issues in Linear
      const assignableLabels = labels.filter((l: LinearLabel) => !l.isGroup);
      setAvailableLabels(assignableLabels);
      // Filter editLabelIds to only include valid UUIDs that exist in available labels
      const validLabelIds = new Set(assignableLabels.map((l: LinearLabel) => l.id));
      setEditLabelIds((prev) => prev.filter((id) => validLabelIds.has(id)));
      setMetadataLoading(false);
    });
  }

  async function handleSaveEdit() {
    if (!selectedIssue) return;
    setActionLoading(true);
    try {
      const updates: Record<string, unknown> = {
        title: editTitle,
        description: editDescription,
        assignee: editAssignee,
        priority: editPriority || null,
      };
      if (editStateId) updates.linear_state_id = editStateId;
      if (editLabelIds.length > 0) updates.label_ids = editLabelIds;
      const updated = await api.updateLinearIssue(selectedIssue.id, updates as Partial<LinearIssue>);
      setSelectedIssue({ ...selectedIssue, ...updated });
      setEditing(false);
      refetch();
    } catch {
      // handled
    } finally {
      setActionLoading(false);
    }
  }

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
      await api.bulkApproveLinearIssues(Array.from(selectedIds));
      setSelectedIds(new Set());
      setSelectedIssue(null);
      refetch();
    } catch {
      // handled
    } finally {
      setActionLoading(false);
    }
  }

  async function handleBulkDelete() {
    if (selectedIds.size === 0) return;
    if (!confirm(`Delete ${selectedIds.size} selected issue(s)? They will not be created in Linear.`)) return;
    setActionLoading(true);
    try {
      await api.bulkDeleteLinearIssues(Array.from(selectedIds));
      setSelectedIds(new Set());
      setSelectedIssue(null);
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
      await api.approveLinearIssue(id);
      if (selectedIssue?.id === id) setSelectedIssue(null);
      refetch();
    } catch {
      // handled
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this issue? It will not be created in Linear.')) return;
    setActionLoading(true);
    try {
      await api.deleteLinearIssue(id);
      if (selectedIssue?.id === id) setSelectedIssue(null);
      setSelectedIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
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
        <h1 className="text-2xl font-bold text-gray-900">Linear Issues</h1>
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
            <>
              <button
                onClick={handleBulkApprove}
                disabled={actionLoading}
                className="btn-success"
              >
                <CheckIcon className="h-4 w-4 mr-1" />
                Approve {selectedIds.size} Selected
              </button>
              <button
                onClick={handleBulkDelete}
                disabled={actionLoading}
                className="btn-danger"
              >
                <TrashIcon className="h-4 w-4 mr-1" />
                Delete {selectedIds.size} Selected
              </button>
            </>
          )}
        </div>
      </div>

      {error && <ErrorAlert message={error} onRetry={refetch} />}

      {data && data.length === 0 ? (
        <EmptyState
          icon={<TicketIcon className="h-12 w-12" />}
          title="No issues"
          description="Issues will appear here when extracted from meeting notes, Slack threads, or created manually."
        />
      ) : (
        <div className="flex gap-6">
          {/* Issue List */}
          <div className={classNames('flex-shrink-0 overflow-auto', selectedIssue ? 'w-1/3' : 'w-full')}>
            <div className="card overflow-hidden !p-0">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {pendingCount > 0 && (
                      <th className="px-3 py-3 w-8">
                        <input
                          type="checkbox"
                          checked={selectedIds.size === pendingCount && pendingCount > 0}
                          onChange={toggleSelectAll}
                          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-600"
                        />
                      </th>
                    )}
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Issue</th>
                    {!selectedIssue && (
                      <>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Customer</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Priority</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                      </>
                    )}
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="relative px-4 py-3"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {data?.map((issue) => (
                    <tr
                      key={issue.id}
                      onClick={() => selectIssue(issue)}
                      className={classNames(
                        'cursor-pointer',
                        selectedIssue?.id === issue.id ? 'bg-indigo-50' : 'hover:bg-gray-50'
                      )}
                    >
                      {pendingCount > 0 && (
                        <td className="px-3 py-3 w-8" onClick={(e) => e.stopPropagation()}>
                          {issue.approval_status === 'draft' && (
                            <input
                              type="checkbox"
                              checked={selectedIds.has(issue.id)}
                              onChange={() => toggleSelect(issue.id)}
                              className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-600"
                            />
                          )}
                        </td>
                      )}
                      <td className="px-4 py-3">
                        <div className="text-sm font-medium text-gray-900 max-w-xs truncate">{issue.title}</div>
                        {!selectedIssue && issue.description && (
                          <div className="text-xs text-gray-500 max-w-xs truncate">{issue.description}</div>
                        )}
                      </td>
                      {!selectedIssue && (
                        <>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                            {issue.customer_name || '—'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className={classNames('text-sm font-medium', getPriorityColor(issue.priority))}>
                              {getPriorityLabel(issue.priority)}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 capitalize">
                            {issue.source?.replace('_', ' ') || '—'}
                          </td>
                        </>
                      )}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={getApprovalBadge(issue.approval_status)}>
                          {getApprovalLabel(issue.approval_status)}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-right text-sm" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1">
                          {issue.approval_status === 'draft' && (
                            <>
                              <button
                                onClick={() => handleApprove(issue.id)}
                                disabled={actionLoading}
                                className="text-green-600 hover:text-green-800"
                                title="Approve & Create in Linear"
                              >
                                <CheckIcon className="h-4 w-4" />
                              </button>
                              <button
                                onClick={() => handleDelete(issue.id)}
                                disabled={actionLoading}
                                className="text-red-500 hover:text-red-700"
                                title="Delete Issue"
                              >
                                <TrashIcon className="h-4 w-4" />
                              </button>
                            </>
                          )}
                          {issue.linear_issue_url && (
                            <a
                              href={issue.linear_issue_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-indigo-600 hover:text-indigo-800"
                              title="View in Linear"
                            >
                              <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                            </a>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Detail / Edit Panel */}
          {selectedIssue && (
            <div className="flex-1 min-w-0">
              <div className="card sticky top-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-gray-900">
                    {editing ? 'Edit Issue' : 'Issue Details'}
                  </h2>
                  <div className="flex items-center gap-2">
                    {selectedIssue.approval_status === 'draft' && !editing && (
                      <button onClick={startEditing} className="btn-secondary text-sm py-1 px-3">
                        <PencilIcon className="h-4 w-4 mr-1" />
                        Edit
                      </button>
                    )}
                    <button
                      onClick={() => { setSelectedIssue(null); setEditing(false); }}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <XMarkIcon className="h-5 w-5" />
                    </button>
                  </div>
                </div>

                {editing ? (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        className="input-field"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Description
                        <span className="text-xs text-gray-400 ml-1">(sent as Linear issue description — supports markdown)</span>
                      </label>
                      <textarea
                        value={editDescription}
                        onChange={(e) => setEditDescription(e.target.value)}
                        rows={10}
                        className="input-field font-mono text-sm"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Assignee</label>
                        <input
                          type="text"
                          value={editAssignee}
                          onChange={(e) => setEditAssignee(e.target.value)}
                          className="input-field"
                          placeholder="Name or email"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                        <select
                          value={editPriority}
                          onChange={(e) => setEditPriority(e.target.value)}
                          className="input-field"
                        >
                          {PRIORITY_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Linear Status & Labels */}
                    {metadataLoading ? (
                      <div className="text-sm text-gray-400">Loading Linear metadata...</div>
                    ) : (
                      <div className="grid grid-cols-2 gap-4">
                        {availableStates.length > 0 && (
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                            <select
                              value={editStateId}
                              onChange={(e) => setEditStateId(e.target.value)}
                              className="input-field"
                            >
                              <option value="">Use default</option>
                              {availableStates.map((s) => (
                                <option key={s.id} value={s.id}>
                                  {s.name}
                                </option>
                              ))}
                            </select>
                          </div>
                        )}
                        {availableLabels.length > 0 && (
                          <div className="relative col-span-2" ref={labelsRef}>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              Labels
                              {editLabelIds.length > 0 && (
                                <span className="ml-1 text-xs text-indigo-600">({editLabelIds.length} selected)</span>
                              )}
                            </label>
                            <button
                              type="button"
                              onClick={() => setLabelsOpen(!labelsOpen)}
                              className="input-field text-left flex items-center justify-between"
                            >
                              <span className="truncate text-sm">
                                {editLabelIds.length === 0
                                  ? 'Select labels...'
                                  : availableLabels
                                      .filter((l) => editLabelIds.includes(l.id))
                                      .map((l) => l.name)
                                      .join(', ')}
                              </span>
                              <ChevronDownIcon className={classNames('h-4 w-4 text-gray-400 transition-transform', labelsOpen ? 'rotate-180' : '')} />
                            </button>
                            {labelsOpen && (
                              <div className="absolute z-10 mt-1 w-full max-h-80 bg-white border border-gray-200 rounded-md shadow-lg flex flex-col">
                                <div className="p-2 border-b border-gray-100">
                                  <input
                                    ref={labelSearchRef}
                                    type="text"
                                    value={labelSearch}
                                    onChange={(e) => setLabelSearch(e.target.value)}
                                    placeholder="Search labels..."
                                    className="w-full px-2 py-1 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-500"
                                  />
                                </div>
                                <div className="overflow-auto flex-1">
                                  {(() => {
                                    const q = labelSearch.toLowerCase();

                                    // Build grouped structure: { parentName: label[] }
                                    // Groups with parentName get radio-style (one per group)
                                    // Labels without parentName go in "Other" with checkboxes
                                    const groups: Record<string, LinearLabel[]> = {};
                                    const ungrouped: LinearLabel[] = [];

                                    for (const label of availableLabels) {
                                      // Filter by search query
                                      if (q && !label.name.toLowerCase().includes(q) &&
                                          !(label.parentName && label.parentName.toLowerCase().includes(q))) {
                                        continue;
                                      }
                                      if (label.parentName) {
                                        if (!groups[label.parentName]) groups[label.parentName] = [];
                                        groups[label.parentName].push(label);
                                      } else {
                                        ungrouped.push(label);
                                      }
                                    }

                                    // Sort groups: show Customer Task and Internal Task first
                                    const priorityGroups = ['Customer Task', 'Internal Task'];
                                    const sortedGroupNames = [
                                      ...priorityGroups.filter((g) => groups[g]),
                                      ...Object.keys(groups)
                                        .filter((g) => !priorityGroups.includes(g))
                                        .sort(),
                                    ];

                                    const hasResults = sortedGroupNames.length > 0 || ungrouped.length > 0;
                                    if (!hasResults) {
                                      return <div className="px-3 py-2 text-sm text-gray-400">No labels found</div>;
                                    }

                                    return (
                                      <>
                                        {sortedGroupNames.map((groupName) => {
                                          const labels = groups[groupName].sort((a, b) => a.name.localeCompare(b.name));
                                          const selectedInGroup = labels.find((l) => editLabelIds.includes(l.id));
                                          return (
                                            <div key={groupName}>
                                              <div className="px-3 py-1.5 bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-gray-100 sticky top-0">
                                                {groupName}
                                                <span className="ml-1 font-normal normal-case">(select one)</span>
                                              </div>
                                              {labels.map((label) => (
                                                <label
                                                  key={label.id}
                                                  className="flex items-center px-3 pl-5 py-1.5 hover:bg-gray-50 cursor-pointer text-sm"
                                                >
                                                  <input
                                                    type="radio"
                                                    name={`label-group-${groupName}`}
                                                    checked={editLabelIds.includes(label.id)}
                                                    onChange={() => {
                                                      setEditLabelIds((prev) => {
                                                        // Remove any sibling from this group, then add this one
                                                        const siblingIds = labels.map((l) => l.id);
                                                        const without = prev.filter((id) => !siblingIds.includes(id));
                                                        return [...without, label.id];
                                                      });
                                                    }}
                                                    className="border-gray-300 text-indigo-600 focus:ring-indigo-600 mr-2 flex-shrink-0"
                                                  />
                                                  <span className="truncate">{label.name}</span>
                                                </label>
                                              ))}
                                              {selectedInGroup && (
                                                <button
                                                  type="button"
                                                  onClick={() => {
                                                    const siblingIds = labels.map((l) => l.id);
                                                    setEditLabelIds((prev) => prev.filter((id) => !siblingIds.includes(id)));
                                                  }}
                                                  className="px-3 pl-5 py-1 text-xs text-gray-400 hover:text-red-500 cursor-pointer"
                                                >
                                                  Clear {groupName} selection
                                                </button>
                                              )}
                                            </div>
                                          );
                                        })}
                                        {ungrouped.length > 0 && (
                                          <div>
                                            {sortedGroupNames.length > 0 && (
                                              <div className="px-3 py-1.5 bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-gray-100 sticky top-0">
                                                Other Labels
                                              </div>
                                            )}
                                            {ungrouped.sort((a, b) => a.name.localeCompare(b.name)).map((label) => (
                                              <label
                                                key={label.id}
                                                className="flex items-center px-3 pl-5 py-1.5 hover:bg-gray-50 cursor-pointer text-sm"
                                              >
                                                <input
                                                  type="checkbox"
                                                  checked={editLabelIds.includes(label.id)}
                                                  onChange={() => {
                                                    setEditLabelIds((prev) =>
                                                      prev.includes(label.id)
                                                        ? prev.filter((id) => id !== label.id)
                                                        : [...prev, label.id]
                                                    );
                                                  }}
                                                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-600 mr-2 flex-shrink-0"
                                                />
                                                <span className="truncate">{label.name}</span>
                                              </label>
                                            ))}
                                          </div>
                                        )}
                                      </>
                                    );
                                  })()}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    <div className="flex items-center gap-3 pt-2">
                      <button onClick={handleSaveEdit} disabled={actionLoading} className="btn-primary">
                        Save Changes
                      </button>
                      <button onClick={() => { setEditing(false); setLabelsOpen(false); }} className="btn-secondary">
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-base font-medium text-gray-900">{selectedIssue.title}</h3>
                      <div className="mt-1 flex items-center gap-3 text-sm text-gray-500">
                        <span>{selectedIssue.customer_name || 'No customer'}</span>
                        <span>·</span>
                        <span className={classNames('font-medium', getPriorityColor(selectedIssue.priority))}>
                          {getPriorityLabel(selectedIssue.priority)}
                        </span>
                        <span>·</span>
                        <span className="capitalize">{selectedIssue.source?.replace('_', ' ') || '—'}</span>
                      </div>
                    </div>

                    {selectedIssue.assignee && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 uppercase">Assignee</p>
                        <p className="text-sm text-gray-900">{selectedIssue.assignee}</p>
                      </div>
                    )}

                    {selectedIssue.label_ids?.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 uppercase">Labels</p>
                        <div className="flex flex-wrap gap-1 mt-0.5">
                          {selectedIssue.label_ids.map((labelId) => {
                            const label = availableLabels.find((l) => l.id === labelId);
                            return (
                              <span key={labelId} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700">
                                {label ? label.name : labelId.slice(0, 8) + '...'}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase mb-1">Description</p>
                      <div className="prose prose-sm max-w-none text-gray-700 bg-gray-50 rounded-md p-3 whitespace-pre-wrap">
                        {selectedIssue.description || 'No description'}
                      </div>
                    </div>

                    <div className="text-xs text-gray-400">
                      Created {formatTimeAgo(selectedIssue.created_at)}
                    </div>

                    {selectedIssue.approval_status === 'draft' && (
                      <div className="flex items-center gap-3 pt-2 border-t">
                        <button
                          onClick={() => handleApprove(selectedIssue.id)}
                          disabled={actionLoading}
                          className="btn-success"
                        >
                          <CheckIcon className="h-4 w-4 mr-1" />
                          Approve & Create in Linear
                        </button>
                        <button
                          onClick={() => handleDelete(selectedIssue.id)}
                          disabled={actionLoading}
                          className="btn-danger"
                        >
                          <TrashIcon className="h-4 w-4 mr-1" />
                          Delete
                        </button>
                      </div>
                    )}

                    {selectedIssue.linear_issue_url && (
                      <div className="pt-2 border-t">
                        <a
                          href={selectedIssue.linear_issue_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-indigo-600 hover:text-indigo-500 flex items-center gap-1"
                        >
                          <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                          View in Linear
                        </a>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
