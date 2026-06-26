import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../lib/apiClient';
import type { ModelStatus, ModelProgress } from '../types';

export interface ModelStatusState {
  status: ModelStatus | null;
  progress: ModelProgress | null;
  loading: boolean;
  downloaded: boolean;
  downloading: boolean;
  error: string | null;
}

/**
 * Tracks the VieNeu model download. Polls progress (1.5s) only while a download
 * is active, mirroring the job-polling pattern in useJobs.
 */
export function useModelStatus() {
  const [state, setState] = useState<ModelStatusState>({
    status: null,
    progress: null,
    loading: true,
    downloaded: false,
    downloading: false,
    error: null,
  });

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const status = await apiClient.getModelStatus();
      setState((prev) => ({
        ...prev,
        status,
        loading: false,
        downloaded: status.downloaded,
        downloading: status.state === 'downloading',
        error: status.error ?? null,
      }));
      return status;
    } catch {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: 'Không thể lấy trạng thái mô hình',
      }));
      return null;
    }
  }, []);

  const startPolling = useCallback(() => {
    stopPolling();
    const poll = async () => {
      try {
        const progress = await apiClient.getModelProgress();
        setState((prev) => ({
          ...prev,
          progress,
          downloading: progress.state === 'downloading',
          error: progress.error ?? null,
        }));
        if (progress.state === 'done' || progress.state === 'error') {
          stopPolling();
          fetchStatus();
        }
      } catch {
        // keep polling through transient errors
      }
    };
    poll();
    pollRef.current = setInterval(poll, 1500);
  }, [stopPolling, fetchStatus]);

  const startDownload = useCallback(async () => {
    setState((prev) => ({ ...prev, downloading: true, error: null }));
    try {
      const progress = await apiClient.startModelDownload();
      setState((prev) => ({ ...prev, progress }));
      if (progress.state === 'done') {
        await fetchStatus();
      } else {
        startPolling();
      }
    } catch {
      setState((prev) => ({
        ...prev,
        downloading: false,
        error: 'Không thể bắt đầu tải mô hình',
      }));
    }
  }, [fetchStatus, startPolling]);

  const deleteModel = useCallback(async () => {
    try {
      const status = await apiClient.deleteModel();
      setState((prev) => ({
        ...prev,
        status,
        progress: null,
        downloaded: status.downloaded,
        downloading: false,
      }));
    } catch {
      setState((prev) => ({ ...prev, error: 'Không thể xoá mô hình' }));
    }
  }, []);

  useEffect(() => {
    fetchStatus().then((status) => {
      // Resume polling if a download was already running (e.g. another window).
      if (status?.state === 'downloading') startPolling();
    });
    return () => stopPolling();
  }, [fetchStatus, startPolling, stopPolling]);

  return { ...state, fetchStatus, startDownload, deleteModel };
}
