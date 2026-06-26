import { useState, useCallback, useRef, useEffect } from 'react';
import { apiClient } from '../lib/apiClient';
import type { Job, JobCreateRequest, JobCreateResponse } from '../types';

export interface JobsState {
  jobs: Job[];
  currentJob: Job | null;
  loading: boolean;
  creating: boolean;
  error: string | null;
}

export function useJobs() {
  const [state, setState] = useState<JobsState>({
    jobs: [],
    currentJob: null,
    loading: true,
    creating: false,
    error: null,
  });

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch all jobs (history)
  const fetchJobs = useCallback(async () => {
    try {
      const jobs = await apiClient.getJobs();
      setState((prev) => ({ ...prev, jobs, loading: false, error: null }));
    } catch {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: 'Không thể tải lịch sử công việc',
      }));
    }
  }, []);

  // Poll a specific job's progress
  const startPolling = useCallback((jobId: string) => {
    // Clear previous polling
    if (pollRef.current) clearInterval(pollRef.current);

    const poll = async () => {
      try {
        const job = await apiClient.getJob(jobId);
        setState((prev) => ({
          ...prev,
          currentJob: job,
          // Update job in history list too
          jobs: prev.jobs.map((j) => (j.job_id === jobId ? job : j)),
        }));

        // Stop polling when job is done
        if (['completed', 'failed', 'cancelled', 'canceled'].includes(job.status)) {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          // Refresh full job list
          fetchJobs();
        }
      } catch {
        // Keep polling even if one request fails
      }
    };

    poll(); // immediate first check
    pollRef.current = setInterval(poll, 1500);
  }, [fetchJobs]);

  // Create a new job
  const createJob = useCallback(
    async (req: JobCreateRequest): Promise<JobCreateResponse | null> => {
      setState((prev) => ({ ...prev, creating: true, error: null }));
      try {
        const result = await apiClient.createJob(req);
        // Start polling for this job
        startPolling(result.job_id);
        setState((prev) => ({ ...prev, creating: false }));
        return result;
      } catch (err: unknown) {
        const message =
          (err as { message?: string })?.message || 'Không thể tạo công việc';
        setState((prev) => ({
          ...prev,
          creating: false,
          error: message,
        }));
        return null;
      }
    },
    [startPolling]
  );

  // Cancel job
  const cancelJob = useCallback(async (jobId: string) => {
    try {
      await apiClient.cancelJob(jobId);
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      fetchJobs();
    } catch {
      // ignore
    }
  }, [fetchJobs]);

  // Retry job
  const retryJob = useCallback(async (jobId: string) => {
    try {
      const result = await apiClient.retryJob(jobId);
      startPolling(result.job_id);
    } catch {
      // ignore
    }
  }, [startPolling]);

  const deleteJob = useCallback(async (jobId: string) => {
    try {
      await apiClient.deleteJob(jobId);
      setState((prev) => ({
        ...prev,
        jobs: prev.jobs.filter((job) => job.job_id !== jobId),
        currentJob: prev.currentJob?.job_id === jobId ? null : prev.currentJob,
      }));
    } catch {
      fetchJobs();
    }
  }, [fetchJobs]);

  // Clear current job
  const clearCurrentJob = useCallback(() => {
    setState((prev) => ({ ...prev, currentJob: null }));
  }, []);

  // Initial load
  useEffect(() => {
    fetchJobs();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchJobs]);

  return {
    ...state,
    fetchJobs,
    createJob,
    cancelJob,
    retryJob,
    deleteJob,
    clearCurrentJob,
    startPolling,
  };
}
