import { useState, useCallback } from 'react';
import { useLicense } from '../hooks/useLicense';
import type { LicenseState } from '../types';

const STATE_BADGE: Record<LicenseState, { label: string; cls: string }> = {
  dev: { label: 'Chế độ phát triển (không khoá)', cls: 'badge-neutral' },
  trial: { label: 'Đang dùng thử', cls: 'badge-info' },
  licensed: { label: '✓ Đã kích hoạt', cls: 'badge-success' },
  expired: { label: 'Hết hạn dùng thử', cls: 'badge-error' },
  invalid: { label: 'Mã không hợp lệ', cls: 'badge-warning' },
};

export default function License() {
  const { status, loading, activating, activate } = useLicense();
  const [key, setKey] = useState('');
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const copyCode = useCallback(() => {
    if (status?.machine_code) {
      navigator.clipboard?.writeText(status.machine_code).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      });
    }
  }, [status]);

  const onActivate = useCallback(async () => {
    if (!key.trim()) return;
    const res = await activate(key);
    setMsg({ ok: res.ok, text: res.message });
    if (res.ok) setKey('');
  }, [key, activate]);

  const badge = status ? STATE_BADGE[status.state] : null;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Bản quyền</h1>
        <p className="page-subtitle">Dùng thử 7 ngày · sau đó kích hoạt bằng mã đăng ký theo máy</p>
      </div>

      <div className="agent-layout">
        {/* Trạng thái */}
        <div className="card">
          <div className="flex items-center justify-between">
            <h3 className="card-title">Trạng thái</h3>
            {loading ? (
              <span className="badge badge-neutral">Đang kiểm tra...</span>
            ) : badge ? (
              <span className={`badge ${badge.cls}`}>{badge.label}</span>
            ) : null}
          </div>
          {status?.state === 'trial' && (
            <p className="text-sm text-muted" style={{ marginTop: 'var(--space-2)' }}>
              Còn <strong>{status.days_left}</strong> ngày dùng thử.
            </p>
          )}
          {status?.state === 'licensed' && (
            <p className="text-sm text-muted" style={{ marginTop: 'var(--space-2)' }}>
              Đã kích hoạt cho máy này{status.exp ? ` · hết hạn ${status.exp}` : ' · vĩnh viễn'}.
            </p>
          )}
          {status?.state === 'expired' && (
            <p className="text-sm" style={{ marginTop: 'var(--space-2)', color: 'var(--color-error-600)' }}>
              Đã hết hạn dùng thử. Vui lòng kích hoạt để tiếp tục tạo giọng nói.
            </p>
          )}
          {!status?.enforced && (
            <p className="text-xs text-muted" style={{ marginTop: 'var(--space-2)' }}>
              (Bản chạy từ mã nguồn — license không bắt buộc.)
            </p>
          )}
        </div>

        {/* Mã máy */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-3)' }}>Mã máy của bạn</h3>
          <div className="agent-endpoint">
            <code className="agent-endpoint-url" style={{ fontSize: 'var(--font-size-md)', letterSpacing: '0.05em' }}>
              {status?.machine_code || '...'}
            </code>
            <button type="button" className="btn btn-secondary btn-sm" onClick={copyCode}>
              {copied ? '✓ Đã chép' : '📋 Copy'}
            </button>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: 'var(--space-3)' }}>
            Gửi <strong>mã máy</strong> này cho tác giả để nhận <strong>mã đăng ký</strong>:
            <br />ABM · DũngTQ — 📞 <strong>0976202028</strong>
          </p>
        </div>

        {/* Kích hoạt */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-3)' }}>Nhập mã đăng ký</h3>
          <textarea
            className="textarea"
            style={{ minHeight: 90, fontFamily: 'monospace', fontSize: 'var(--font-size-sm)' }}
            placeholder="Dán mã đăng ký (VM1....) vào đây"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            aria-label="Mã đăng ký"
          />
          <div className="flex items-center gap-3" style={{ marginTop: 'var(--space-3)' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={onActivate}
              disabled={activating || !key.trim()}
            >
              {activating ? 'Đang kích hoạt...' : '🔑 Kích hoạt'}
            </button>
            {msg && (
              <span className={`badge ${msg.ok ? 'badge-success' : 'badge-error'}`}>{msg.text}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
