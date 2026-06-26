import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../lib/apiClient';
import type { Voice, EngineName, VoiceStyle } from '../types';

export interface VoicesState {
  voices: Voice[];
  loading: boolean;
  error: string | null;
}

export function useVoices(filters?: {
  engine?: EngineName;
  style?: VoiceStyle;
  available_only?: boolean;
}): VoicesState & { refetch: () => void } {
  const engine = filters?.engine;
  const style = filters?.style;
  const availableOnly = filters?.available_only;

  const [state, setState] = useState<VoicesState>({
    voices: [],
    loading: true,
    error: null,
  });

  const fetchVoices = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await apiClient.getVoices({
        engine,
        style,
        available_only: availableOnly,
      });
      setState({ voices: data.voices, loading: false, error: null });
    } catch {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: 'Không thể tải danh sách giọng nói',
      }));
    }
  }, [engine, style, availableOnly]);

  useEffect(() => {
    fetchVoices();
  }, [fetchVoices]);

  return { ...state, refetch: fetchVoices };
}
