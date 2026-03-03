import { useState, useCallback, useEffect, useRef } from 'react';
import { CheckCircleIcon, ExclamationCircleIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { LoadingSpinner } from './LoadingSpinner';
import type { ResolveResult } from '../types';

interface ResolvableFieldProps {
  label: string;
  placeholder: string;
  helpText?: string;
  value: string;
  resolvedId: string;
  resolvedName: string;
  onValueChange: (value: string) => void;
  onResolved: (id: string, name: string) => void;
  onClear: () => void;
  resolveFn: (value: string) => Promise<ResolveResult>;
  disabled?: boolean;
  /** Increment this to programmatically trigger a re-verify (e.g. "Verify All" button) */
  verifyTrigger?: number;
}

export function ResolvableField({
  label,
  placeholder,
  helpText,
  value,
  resolvedId,
  resolvedName,
  onValueChange,
  onResolved,
  onClear,
  resolveFn,
  disabled = false,
  verifyTrigger = 0,
}: ResolvableFieldProps) {
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const prevTrigger = useRef(verifyTrigger);

  const handleResolve = useCallback(async () => {
    if (!value.trim() || resolving) return;

    setResolving(true);
    setError(null);
    try {
      const result = await resolveFn(value.trim());
      if (result.valid && result.id) {
        onResolved(result.id, result.name || result.id);
      } else {
        setError(result.error || 'Could not resolve');
        onClear();
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })
        .response?.data?.detail || (err as { message?: string }).message || 'Resolution failed';
      setError(msg);
      onClear();
    } finally {
      setResolving(false);
    }
  }, [value, resolving, resolveFn, onResolved, onClear]);

  // Fire when parent increments verifyTrigger
  useEffect(() => {
    if (verifyTrigger > 0 && verifyTrigger !== prevTrigger.current && value.trim()) {
      prevTrigger.current = verifyTrigger;
      handleResolve();
    }
  }, [verifyTrigger, value, handleResolve]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onValueChange(e.target.value);
    if (resolvedId) {
      onClear();
    }
    setError(null);
  };

  const handleBlur = () => {
    if (value.trim() && !resolvedId) {
      handleResolve();
    }
  };

  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex items-center gap-2 mt-1">
        <input
          type="text"
          value={value}
          onChange={handleChange}
          onBlur={handleBlur}
          className="input-field flex-1"
          placeholder={placeholder}
          disabled={disabled}
        />
        <button
          type="button"
          onClick={handleResolve}
          disabled={resolving || !value.trim() || disabled}
          className="btn-secondary text-sm px-3 py-2 flex items-center gap-1 whitespace-nowrap"
        >
          {resolving ? (
            <>
              <LoadingSpinner size="sm" />
              <span>Checking...</span>
            </>
          ) : resolvedId ? (
            <>
              <ArrowPathIcon className="h-4 w-4" />
              <span>Re-verify</span>
            </>
          ) : (
            <>
              <ArrowPathIcon className="h-4 w-4" />
              <span>Resolve</span>
            </>
          )}
        </button>
      </div>

      {resolvedId && resolvedName && !error && (
        <div className="mt-1 flex items-center gap-1.5 text-sm text-green-600">
          <CheckCircleIcon className="h-4 w-4 flex-shrink-0" />
          <span>
            Resolved: <strong>{resolvedName !== resolvedId ? resolvedName : resolvedId}</strong>
          </span>
          {resolvedName !== resolvedId && (
            <span className="text-gray-400 text-xs">({resolvedId.length > 20 ? resolvedId.slice(0, 20) + '...' : resolvedId})</span>
          )}
        </div>
      )}

      {error && (
        <div className="mt-1 flex items-center gap-1.5 text-sm text-red-600">
          <ExclamationCircleIcon className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {helpText && !resolvedId && !error && (
        <p className="mt-1 text-xs text-gray-500">{helpText}</p>
      )}
    </div>
  );
}
