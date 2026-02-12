import { ExclamationTriangleIcon, XMarkIcon } from '@heroicons/react/20/solid';

interface ErrorAlertProps {
  message: string;
  detail?: string;
  onDismiss?: () => void;
  onRetry?: () => void;
}

export function ErrorAlert({ message, detail, onDismiss, onRetry }: ErrorAlertProps) {
  return (
    <div className="rounded-md bg-red-50 p-4">
      <div className="flex">
        <div className="flex-shrink-0">
          <ExclamationTriangleIcon className="h-5 w-5 text-red-400" aria-hidden="true" />
        </div>
        <div className="ml-3 flex-1">
          <p className="text-sm font-medium text-red-800">{message}</p>
          {detail && (
            <p className="mt-1 text-sm text-red-600">{detail}</p>
          )}
          {onRetry && (
            <button
              type="button"
              className="mt-2 text-sm font-medium text-red-700 underline hover:text-red-600"
              onClick={onRetry}
            >
              Retry
            </button>
          )}
        </div>
        {onDismiss && (
          <div className="ml-auto pl-3">
            <button
              type="button"
              className="inline-flex rounded-md bg-red-50 p-1.5 text-red-500 hover:bg-red-100"
              onClick={onDismiss}
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
