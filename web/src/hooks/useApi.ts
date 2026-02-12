import { useState, useEffect, useCallback, useRef } from 'react';

interface UseApiOptions {
  immediate?: boolean;
}

interface UseApiReturn<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  execute: (...args: unknown[]) => Promise<T | null>;
  refetch: () => Promise<T | null>;
  setData: React.Dispatch<React.SetStateAction<T | null>>;
}

function extractErrorMessage(err: unknown): string {
  const errorObj = err as {
    response?: { status?: number; data?: { detail?: string } };
    message?: string;
    code?: string;
  };

  // Server returned an error response
  if (errorObj.response) {
    const status = errorObj.response.status;
    const detail = errorObj.response.data?.detail;

    if (detail) return detail;

    switch (status) {
      case 400:
        return 'Invalid request. Please check your input and try again.';
      case 404:
        return 'The requested resource was not found. This feature may not be configured yet.';
      case 409:
        return 'A conflict occurred. This item may already exist.';
      case 422:
        return 'Invalid data provided. Please check the form fields.';
      case 500:
        return 'An internal server error occurred. Check the backend logs for details.';
      case 502:
        return 'The backend service is not reachable. Ensure Docker Compose is running.';
      case 503:
        return 'This service is temporarily unavailable. The required integration may not be connected yet — check Settings.';
      default:
        return `Server error (${status}). Please try again or check backend logs.`;
    }
  }

  // Network error (no response received)
  if (errorObj.code === 'ERR_NETWORK' || errorObj.message === 'Network Error') {
    return 'Cannot reach the backend API. Make sure Docker Compose is running and the backend service is healthy.';
  }

  if (errorObj.message) return errorObj.message;

  return 'An unexpected error occurred.';
}

export function useApi<T>(
  apiCall: (...args: unknown[]) => Promise<T>,
  deps: unknown[] = [],
  options: UseApiOptions = { immediate: true }
): UseApiReturn<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const argsRef = useRef<unknown[]>([]);

  const execute = useCallback(
    async (...args: unknown[]): Promise<T | null> => {
      argsRef.current = args;
      setLoading(true);
      setError(null);
      try {
        const result = await apiCall(...args);
        setData(result);
        return result;
      } catch (err: unknown) {
        const message = extractErrorMessage(err);
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    deps
  );

  const refetch = useCallback(() => {
    return execute(...argsRef.current);
  }, [execute]);

  useEffect(() => {
    if (options.immediate) {
      execute();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [execute]);

  return { data, loading, error, execute, refetch, setData };
}

export function usePolling<T>(
  apiCall: () => Promise<T>,
  intervalMs: number = 30000,
  deps: unknown[] = []
): UseApiReturn<T> {
  const result = useApi(apiCall, deps);

  useEffect(() => {
    const interval = setInterval(() => {
      result.refetch();
    }, intervalMs);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, result.refetch]);

  return result;
}
