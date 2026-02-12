import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns';
import type { HealthStatus, ApprovalStatus, Priority, ConnectionStatus } from '../types';

// ---- Date Formatting ----

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const date = parseISO(dateStr);
  if (!isValid(date)) return '—';
  return format(date, 'MMM d, yyyy');
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const date = parseISO(dateStr);
  if (!isValid(date)) return '—';
  return format(date, 'MMM d, yyyy h:mm a');
}

export function formatTimeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const date = parseISO(dateStr);
  if (!isValid(date)) return '—';
  return formatDistanceToNow(date, { addSuffix: true });
}

export function formatTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const date = parseISO(dateStr);
  if (!isValid(date)) return '—';
  return format(date, 'h:mm a');
}

// ---- Status Displays ----

export function getHealthColor(status: HealthStatus): string {
  switch (status) {
    case 'green': return 'badge-green';
    case 'yellow': return 'badge-yellow';
    case 'red': return 'badge-red';
  }
}

export function getHealthDot(status: HealthStatus): string {
  switch (status) {
    case 'green': return 'bg-green-500';
    case 'yellow': return 'bg-yellow-500';
    case 'red': return 'bg-red-500';
  }
}

export function getApprovalBadge(status: ApprovalStatus): string {
  switch (status) {
    case 'draft': return 'badge-gray';
    case 'in_review': return 'badge-blue';
    case 'approved': return 'badge-green';
    case 'published': return 'badge-green';
    case 'rejected': return 'badge-red';
    case 'archived': return 'badge-gray';
  }
}

export function getApprovalLabel(status: ApprovalStatus): string {
  switch (status) {
    case 'draft': return 'Draft';
    case 'in_review': return 'In Review';
    case 'approved': return 'Approved';
    case 'published': return 'Published';
    case 'rejected': return 'Rejected';
    case 'archived': return 'Archived';
  }
}

export function getPriorityColor(priority: Priority): string {
  switch (priority) {
    case 'urgent': return 'text-red-600';
    case 'high': return 'text-orange-500';
    case 'medium': return 'text-yellow-500';
    case 'low': return 'text-blue-500';
    case 'none': return 'text-gray-400';
  }
}

export function getPriorityLabel(priority: Priority): string {
  switch (priority) {
    case 'urgent': return 'Urgent';
    case 'high': return 'High';
    case 'medium': return 'Medium';
    case 'low': return 'Low';
    case 'none': return 'None';
  }
}

export function getConnectionIcon(status: ConnectionStatus): string {
  switch (status) {
    case 'connected': return '🟢';
    case 'disconnected': return '🔴';
    case 'expired': return '🟡';
  }
}

export function getConnectionLabel(status: ConnectionStatus): string {
  switch (status) {
    case 'connected': return 'Connected';
    case 'disconnected': return 'Not Connected';
    case 'expired': return 'Token Expired';
  }
}

export function getWorkflowTypeLabel(type: string): string {
  switch (type) {
    case 'agenda': return 'Agenda';
    case 'meeting_notes': return 'Meeting Notes';
    case 'health_update': return 'Health Update';
    default: return type;
  }
}

// ---- Misc ----

export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 3) + '...';
}

export function classNames(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ');
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
