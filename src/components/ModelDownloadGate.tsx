import type { ModelStatus, ModelProgress } from '../types';

interface ModelDownloadGateProps {
  status: ModelStatus | null;
  progress: ModelProgress | null;
  downloading: boolean;
  error: string | null;
  onDownload: () => void;
}

function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return '—';
  const gb = bytes / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(2)} GB`;
  return `${(bytes / 1024 ** 2).toFixed(0)} MB`;
}

/**
 * First-run gate shown when a VieNeu voice is selected but the model has not
 * been downloaded yet. The model is fetched on demand (not bundled in the
 * installer). No cancel — download runs to completion or fails (retry resumes).
 */
export default function ModelDownloadGate({
  status,
  progress,
  downloading,
  error,
  onDownload,
}: ModelDownloadGateProps) {
  const totalBytes = progress?.total_bytes || status?.total_bytes || 0;
  const percent = progress ? Math.round(progress.percent) : 0;
  const isError = !!error || progress?.state === 'error';

  return (
    <div className="card model-gate">
      <div className="model-gate-icon">⬇️</div>
      <h3 className="model-gate-title">Cần tải mô hình VieNeu</h3>
      <p className="model-gate-desc">
        Lần đầu sử dụng cần tải mô hình <strong>VieNeu-TTS v3 Turbo</strong>
        {totalBytes > 0 && <> (~{formatBytes(totalBytes)})</>} về máy. Mô hình không
        đi kèm bộ cài để giữ bộ cài nhẹ; chỉ cần tải một lần và dùng được offline
        sau đó.
      </p>

      {downloading ? (
        <div className="model-gate-progress">
          <div className="progress-bar-container">
            <div
              className="progress-bar-fill"
              style={{ width: `${percent}%`, transition: 'width 0.4s ease' }}
            />
          </div>
          <div className="progress-info">
            <span>Đang tải mô hình...</span>
            <span style={{ fontWeight: 600 }}>{percent}%</span>
          </div>
          {totalBytes > 0 && progress && (
            <div className="text-xs text-muted" style={{ marginTop: 4 }}>
              {formatBytes(progress.downloaded_bytes)} / {formatBytes(totalBytes)}
            </div>
          )}
        </div>
      ) : (
        <>
          {isError && (
            <div role="alert" className="model-gate-error">
              ❌ {error || progress?.error || 'Tải mô hình thất bại.'}
            </div>
          )}
          <button type="button" className="btn-render" onClick={onDownload} style={{ marginTop: 'var(--space-4)' }}>
            {isError ? '🔄 Thử lại tải mô hình' : '⬇️ Tải mô hình'}
          </button>
          <div className="text-xs text-muted" style={{ marginTop: 'var(--space-3)' }}>
            Nếu mất mạng giữa chừng, bấm thử lại — quá trình tải sẽ tiếp tục từ chỗ dở.
          </div>
        </>
      )}
    </div>
  );
}
