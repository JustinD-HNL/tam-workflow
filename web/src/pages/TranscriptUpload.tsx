import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUpTrayIcon, DocumentTextIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { useApi } from '../hooks/useApi';
import api from '../services/api';
import { PageLoader } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { formatDateTime, classNames } from '../utils';
import type { Customer, CalendarEvent } from '../types';

type InputMode = 'upload' | 'paste';

export function TranscriptUpload() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: customers, loading: loadingCustomers } = useApi<Customer[]>(
    () => api.getCustomers(),
    []
  );

  const [customerId, setCustomerId] = useState('');
  const [meetingDate, setMeetingDate] = useState(new Date().toISOString().split('T')[0]);
  const [inputMode, setInputMode] = useState<InputMode>('paste');
  const [transcriptText, setTranscriptText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [recentEvents, setRecentEvents] = useState<CalendarEvent[]>([]);
  const [selectedEventId, setSelectedEventId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Processing state
  const [processing, setProcessing] = useState(false);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [processingDots, setProcessingDots] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const dotsRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (dotsRef.current) clearInterval(dotsRef.current);
    };
  }, []);

  const pollWorkflow = useCallback((wfId: string) => {
    setProcessing(true);
    setProcessingDots('');

    // Animated dots
    dotsRef.current = setInterval(() => {
      setProcessingDots(prev => prev.length >= 3 ? '' : prev + '.');
    }, 500);

    // Poll every 3 seconds
    pollRef.current = setInterval(async () => {
      try {
        const wf = await api.getWorkflow(wfId);
        if (wf.status === 'completed') {
          if (pollRef.current) clearInterval(pollRef.current);
          if (dotsRef.current) clearInterval(dotsRef.current);
          setProcessing(false);
          navigate('/approvals');
        } else if (wf.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          if (dotsRef.current) clearInterval(dotsRef.current);
          setProcessing(false);
          setError(`Notes generation failed: ${wf.error_message || 'Unknown error'}`);
        }
        // If still pending/running, keep polling
      } catch {
        // Network error — keep trying
      }
    }, 3000);
  }, [navigate]);

  async function handleCustomerChange(id: string) {
    setCustomerId(id);
    if (id) {
      try {
        const events = await api.getRecentEvents(id);
        setRecentEvents(events);
      } catch {
        setRecentEvents([]);
      }
    } else {
      setRecentEvents([]);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (selected) {
      const allowedTypes = ['text/plain', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
      if (!allowedTypes.includes(selected.type) && !selected.name.match(/\.(txt|pdf|docx)$/)) {
        setError('Please upload a .txt, .pdf, or .docx file');
        return;
      }
      setFile(selected);
      setError(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!customerId) {
      setError('Please select a customer');
      return;
    }
    if (inputMode === 'paste' && !transcriptText.trim()) {
      setError('Please paste the transcript text');
      return;
    }
    if (inputMode === 'upload' && !file) {
      setError('Please select a file to upload');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const result = await api.uploadTranscript(
        customerId,
        meetingDate,
        inputMode === 'upload' ? file! : undefined,
        inputMode === 'paste' ? transcriptText : undefined,
        selectedEventId || undefined
      );
      setSubmitting(false);
      setWorkflowId(result.workflow_id);
      pollWorkflow(result.workflow_id);
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(errorObj.response?.data?.detail || errorObj.message || 'Failed to upload transcript');
      setSubmitting(false);
    }
  }

  if (loadingCustomers) return <PageLoader />;

  // Show processing state while workflow runs
  if (processing) {
    return (
      <div className="max-w-3xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Upload Transcript</h1>
        <div className="card text-center py-16">
          <ArrowPathIcon className="h-12 w-12 mx-auto text-indigo-500 animate-spin" />
          <h2 className="mt-4 text-lg font-semibold text-gray-900">
            Generating Meeting Notes{processingDots}
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Claude is analyzing the transcript and extracting key points, decisions, and action items.
            This typically takes 15-30 seconds.
          </p>
          {workflowId && (
            <p className="mt-4 text-xs text-gray-400 font-mono">
              Workflow: {workflowId}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Upload Transcript</h1>
      <p className="text-sm text-gray-500">
        Upload or paste a call transcript to generate meeting notes. The transcript will be processed
        and meeting notes will be created for your review.
      </p>

      {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Customer & Date Selection */}
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Meeting Details</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Customer</label>
              <select
                value={customerId}
                onChange={(e) => handleCustomerChange(e.target.value)}
                className="input-field mt-1"
                required
              >
                <option value="">Select a customer...</option>
                {customers?.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Meeting Date</label>
              <input
                type="date"
                value={meetingDate}
                onChange={(e) => setMeetingDate(e.target.value)}
                className="input-field mt-1"
                required
              />
            </div>
          </div>

          {/* Recent Events Suggestion */}
          {recentEvents.length > 0 && (
            <div>
              <label className="label">Match to Calendar Event (optional)</label>
              <select
                value={selectedEventId}
                onChange={(e) => setSelectedEventId(e.target.value)}
                className="input-field mt-1"
              >
                <option value="">-- No match --</option>
                {recentEvents.map((event) => (
                  <option key={event.id} value={event.id}>
                    {event.summary} - {formatDateTime(event.start)}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Input Mode Toggle */}
        <div className="card space-y-4">
          <div className="flex items-center gap-4 border-b border-gray-200 pb-4">
            <button
              type="button"
              onClick={() => setInputMode('paste')}
              className={classNames(
                'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
                inputMode === 'paste'
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-gray-500 hover:text-gray-700'
              )}
            >
              <DocumentTextIcon className="h-5 w-5" />
              Paste Text
            </button>
            <button
              type="button"
              onClick={() => setInputMode('upload')}
              className={classNames(
                'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
                inputMode === 'upload'
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-gray-500 hover:text-gray-700'
              )}
            >
              <ArrowUpTrayIcon className="h-5 w-5" />
              Upload File
            </button>
          </div>

          {inputMode === 'paste' ? (
            <div>
              <label className="label">Transcript Text</label>
              <textarea
                value={transcriptText}
                onChange={(e) => setTranscriptText(e.target.value)}
                className="input-field mt-1 min-h-[300px] font-mono text-sm"
                placeholder="Paste the meeting transcript here..."
                rows={15}
              />
              <p className="mt-1 text-xs text-gray-500">
                {transcriptText.length > 0
                  ? `${transcriptText.split(/\s+/).length} words`
                  : 'Paste the full transcript from Avoma or other source'}
              </p>
            </div>
          ) : (
            <div>
              <label className="label">Transcript File</label>
              <div
                className="mt-1 flex justify-center rounded-lg border border-dashed border-gray-900/25 px-6 py-10 cursor-pointer hover:border-indigo-400 transition-colors"
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="text-center">
                  <ArrowUpTrayIcon className="mx-auto h-12 w-12 text-gray-300" />
                  <div className="mt-4 flex text-sm leading-6 text-gray-600">
                    <span className="font-semibold text-indigo-600 hover:text-indigo-500">
                      Click to upload
                    </span>
                    <p className="pl-1">or drag and drop</p>
                  </div>
                  <p className="text-xs leading-5 text-gray-600">.txt, .pdf, or .docx</p>
                  {file && (
                    <p className="mt-2 text-sm font-medium text-indigo-600">
                      Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
                    </p>
                  )}
                </div>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.pdf,.docx"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-3">
          <button type="button" onClick={() => navigate('/')} className="btn-secondary">Cancel</button>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? 'Uploading...' : 'Generate Meeting Notes'}
          </button>
        </div>
      </form>
    </div>
  );
}
