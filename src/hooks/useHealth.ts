import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../lib/apiClient';
import type { HealthResponse, EngineStatus, GPUInfo, EngineName } from '../types';

export interface HealthState {
  connected: boolean;
  loading: boolean;
  data: HealthResponse | null;
  engines: Record<EngineName, EngineStatus> | null;
  gpu: GPUInfo | null;
  version: string;
  error: string | null;
}

export function useHealth(pollInterval = 5000): HealthState {
  const [state, setState] = useState<HealthState>({
    connected: false,
    loading: true,
    data: null,
    engines: null,
    gpu: null,
    version: '',
    error: null,
  });

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await apiClient.getHealth();
      setState({
        connected: true,
        loading: false,
        data,
        engines: data.engines,
        gpu: data.gpu,
        version: data.version,
        error: null,
      });
    } catch {
      setState((prev) => ({
        ...prev,
        connected: false,
        loading: false,
        error: 'Không thể kết nối backend',
      }));
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    intervalRef.current = setInterval(fetchHealth, pollInterval);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchHealth, pollInterval]);

  return state;
}
