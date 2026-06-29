import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../lib/apiClient';
import type { LicenseStatus } from '../types';

export interface UseLicense {
  status: LicenseStatus | null;
  loading: boolean;
  activating: boolean;
  activate: (key: string) => Promise<{ ok: boolean; message: string }>;
  refetch: () => void;
}

export function useLicense(): UseLicense {
  const [status, setStatus] = useState<LicenseStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [activating, setActivating] = useState(false);

  const refetch = useCallback(async () => {
    try {
      const s = await apiClient.getLicenseStatus();
      setStatus(s);
    } catch {
      // leave previous status
    } finally {
      setLoading(false);
    }
  }, []);

  const activate = useCallback(
    async (key: string) => {
      setActivating(true);
      try {
        const res = await apiClient.activateLicense(key.trim());
        await refetch();
        return { ok: !!res.ok, message: res.message || 'Kích hoạt thành công.' };
      } catch (err: unknown) {
        const message = (err as { message?: string })?.message || 'Mã đăng ký không hợp lệ.';
        return { ok: false, message };
      } finally {
        setActivating(false);
      }
    },
    [refetch]
  );

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { status, loading, activating, activate, refetch };
}
