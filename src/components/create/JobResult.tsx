import { apiClient } from '../../lib/apiClient';
import type { Job } from '../../types';

interface JobResultProps {
  job: Job;
  onClear: () => void;
}

function progressLabel(job: Job): string {
  if (job.status === 'running') return 'Đang chạy...';
  if (job.status === 'cancelled') return 'Đã hủy';
  const labels: Record<string, string> = {
    queued: 'Đang chờ...',
    preparing_text: 'Chuẩn bị văn bản...',
    loading_engine: 'Đang tải engine...',
    rendering_segment: `Tạo đoạn ${job.segments_done}/${job.segments_total}...`,
    exporting_mp3: 'Xuất MP3...',
    completed: '✓ Hoàn thành!',
    failed: '✗ Lỗi',
    canceled: 'Đã hủy',
  };
  return labels[job.status] || job.stage;
}

/** Progress bar + completed (audio/download) + failed states for the active job. */
export default function JobResult({ job, onClear }: JobResultProps) {
  const percent = Math.round((job.progress || 0) * 100);

  return (
    <>
      <div className="progress-bar-container">
        <div
          className="progress-bar-fill"
          style={{ width: `${percent}%`, transition: 'width 0.4s ease' }}
        />
      </div>
      <div className="progress-info">
        <span>{progressLabel(job)}</span>
        <span style={{ fontWeight: 600 }}>{percent}%</span>
      </div>

      {['queued', 'running'].includes(job.status) && job.segments_total > 0 && (
        <div style={{ fontSize: '0.8rem', color: 'var(--color-gray-500)', marginTop: 4 }}>
          Đoạn: {job.segments_done}/{job.segments_total}
          {job.voice_id && ` • Giọng: ${job.voice_id.split(':')[1] || job.voice_id}`}
        </div>
      )}

      {/* Completed */}
      {job.status === 'completed' && job.output_path && (
        <div style={{
          marginTop: 12,
          padding: '12px 16px',
          background: 'var(--color-success-50, #f0fdf4)',
          borderRadius: 10,
          border: '1px solid var(--color-success-100, #dcfce7)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: '1.1rem' }}>✅</span>
            <span style={{ fontWeight: 600, color: 'var(--color-success-700, #15803d)' }}>
              Hoàn thành!
            </span>
          </div>

          <div style={{
            fontSize: '0.82rem',
            color: 'var(--color-gray-600)',
            marginBottom: 10,
            wordBreak: 'break-all',
            background: 'var(--color-gray-100, #f1f5f9)',
            padding: '6px 10px',
            borderRadius: 6,
            fontFamily: 'monospace',
          }}>
            📄 {job.output_path.split(/[/\\]/).pop()}
          </div>

          <audio
            controls
            src={apiClient.getJobAudioUrl(job.job_id)}
            style={{ width: '100%', height: 40, marginBottom: 10, borderRadius: 8 }}
          />

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <a
              href={apiClient.getJobAudioUrl(job.job_id)}
              download
              className="btn btn-sm"
              aria-label="Tải MP3"
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                background: 'var(--color-primary-600, #4F46E5)', color: 'white',
                padding: '6px 14px', borderRadius: 8, fontSize: '0.85rem',
                textDecoration: 'none', fontWeight: 500,
              }}
            >
              ⬇️ Tải MP3
            </a>

            {window.electronAPI && (
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                aria-label="Mở thư mục chứa file"
                onClick={() => {
                  if (window.electronAPI && job.output_path) {
                    window.electronAPI.openFileInExplorer(job.output_path);
                  }
                }}
                style={{ padding: '6px 14px', borderRadius: 8, fontSize: '0.85rem' }}
              >
                📂 Mở thư mục
              </button>
            )}

            <button
              type="button"
              className="btn btn-sm"
              aria-label="Tạo file mới"
              onClick={onClear}
              style={{
                padding: '6px 14px', borderRadius: 8, fontSize: '0.85rem',
                background: 'var(--color-gray-200, #e2e8f0)', color: 'var(--color-gray-700)',
              }}
            >
              🔄 Tạo mới
            </button>
          </div>
        </div>
      )}

      {/* Failed */}
      {job.status === 'failed' && (
        <div role="alert" style={{
          marginTop: 12,
          padding: '12px 16px',
          background: 'var(--color-error-50, #fef2f2)',
          borderRadius: 10,
          border: '1px solid var(--color-error-100, #fee2e2)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ fontSize: '1.1rem' }}>❌</span>
            <span style={{ fontWeight: 600, color: 'var(--color-error-700, #b91c1c)' }}>
              Tạo thất bại
            </span>
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--color-error-600, #dc2626)' }}>
            {typeof job.error === 'string'
              ? job.error
              : typeof job.error === 'object' && job.error !== null
                ? (job.error as any).message || (job.error as any).code || JSON.stringify(job.error)
                : 'Đã xảy ra lỗi'}
          </div>
          <button
            type="button"
            onClick={onClear}
            className="btn btn-sm"
            aria-label="Thử lại sau khi tạo thất bại"
            style={{
              marginTop: 8, padding: '6px 14px', borderRadius: 8, fontSize: '0.85rem',
              background: 'var(--color-gray-200, #e2e8f0)', color: 'var(--color-gray-700)',
            }}
          >
            🔄 Thử lại
          </button>
        </div>
      )}
    </>
  );
}
