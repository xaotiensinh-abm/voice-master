import { useCallback, useState } from 'react';
import { useJobs } from '../hooks/useJobs';
import { apiClient } from '../lib/apiClient';
import type { Job, JobStatus as TJobStatus } from '../types';

const STATUS_CONFIG: Partial<Record<TJobStatus, { label: string; cls: string }>> = {
  queued: { label: 'Đang chờ', cls: 'badge-info' },
  preparing_text: { label: 'Chuẩn bị', cls: 'badge-info' },
  loading_engine: { label: 'Tải engine', cls: 'badge-info' },
  rendering_segment: { label: 'Đang chạy', cls: 'badge-info' },
  exporting_mp3: { label: 'Xuất MP3', cls: 'badge-info' },
  completed: { label: 'Hoàn thành', cls: 'badge-success' },
  failed: { label: 'Lỗi', cls: 'badge-error' },
  canceled: { label: 'Đã hủy', cls: 'badge-neutral' },
};

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function formatDuration(seconds?: number): string {
  if (!seconds) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function History() {
  const { jobs, loading, retryJob, deleteJob, fetchJobs } = useJobs();
  const [deletingJobId, setDeletingJobId] = useState<string | null>(null);

  const handleOpenFile = useCallback((job: Job) => {
    if (window.electronAPI && job.output_path) {
      window.electronAPI.openFileInExplorer(job.output_path);
    }
  }, []);

  const handleOpenFolder = useCallback((job: Job) => {
    if (window.electronAPI && job.output_path) {
      const folder = job.output_path.replace(/[\\/][^\\/]+$/, '');
      window.electronAPI.openFolder(folder);
    }
  }, []);

  const handleDelete = useCallback(async (job: Job) => {
    if (!window.confirm('Xóa job này khỏi lịch sử? File MP3 đã xuất vẫn được giữ nguyên.')) {
      return;
    }
    setDeletingJobId(job.job_id);
    try {
      await deleteJob(job.job_id);
    } finally {
      setDeletingJobId(null);
    }
  }, [deleteJob]);

  const handlePlayAudio = useCallback((job: Job) => {
    const url = apiClient.getJobAudioUrl(job.job_id);
    const audio = new Audio(url);
    audio.play().catch(() => {});
  }, []);

  // Sort jobs by creation time, newest first
  const sortedJobs = [...jobs].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="page-title">Lịch sử</h1>
            <p className="page-subtitle">Xem và quản lý các công việc đã tạo</p>
          </div>
          <button type="button" className="btn btn-secondary" onClick={fetchJobs} disabled={loading}>
            🔄 Làm mới
          </button>
        </div>
      </div>

      {loading ? (
        <div className="card">
          <div className="skeleton" style={{ height: 40, marginBottom: 'var(--space-3)' }} />
          <div className="skeleton" style={{ height: 40, marginBottom: 'var(--space-3)' }} />
          <div className="skeleton" style={{ height: 40, marginBottom: 'var(--space-3)' }} />
          <div className="skeleton" style={{ height: 40 }} />
        </div>
      ) : sortedJobs.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-title">Chưa có lịch sử</div>
            <div className="empty-state-text">
              Khi bạn tạo file MP3, lịch sử sẽ hiển thị tại đây. Hãy bắt đầu bằng cách chọn giọng nói và nhập văn bản!
            </div>
          </div>
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Thời gian</th>
                <th>Input</th>
                <th>Giọng</th>
                <th>Engine</th>
                <th>Thời lượng</th>
                <th>Trạng thái</th>
                <th>Hành động</th>
              </tr>
            </thead>
            <tbody>
              {sortedJobs.map((job) => {
                const statusCfg =
                  job.status === 'running'
                    ? { label: 'Đang chạy', cls: 'badge-info' }
                    : job.status === 'cancelled'
                      ? { label: 'Đã hủy', cls: 'badge-neutral' }
                      : STATUS_CONFIG[job.status] || STATUS_CONFIG.queued!;
                return (
                  <tr key={job.job_id}>
                    <td>
                      <span className="text-sm">{formatTime(job.created_at)}</span>
                    </td>
                    <td>
                      <span className="truncate" style={{ maxWidth: 200, display: 'inline-block' }}>
                        {job.input_preview || job.voice_id}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontWeight: 500 }}>{job.voice_id.split(':').pop()}</span>
                    </td>
                    <td>
                      <span className={`badge badge-engine-${job.engine}`}>
                        {job.engine}
                      </span>
                    </td>
                    <td>
                      <span className="text-sm text-muted">
                        {formatDuration(job.duration_seconds)}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${statusCfg.cls}`}>
                        {statusCfg.label}
                      </span>
                      {job.status === 'rendering_segment' && (
                        <span className="text-xs text-muted" style={{ marginLeft: 'var(--space-2)' }}>
                          {Math.round((job.progress || 0) * 100)}%
                        </span>
                      )}
                    </td>
                    <td>
                      <div className="table-actions">
                        {job.status === 'completed' && job.output_path && (
                          <>
                            <button
                              type="button"
                              className="btn btn-sm btn-ghost btn-icon"
                              onClick={() => handlePlayAudio(job)}
                              title="Phát audio"
                              aria-label={`Play audio for job ${job.job_id}`}
                            >
                              ▶
                            </button>
                            <button
                              type="button"
                              className="btn btn-sm btn-ghost btn-icon"
                              onClick={() => handleOpenFile(job)}
                              title="Mở file"
                              aria-label={`Open file for job ${job.job_id}`}
                            >
                              📄
                            </button>
                            <button
                              type="button"
                              className="btn btn-sm btn-ghost btn-icon"
                              onClick={() => handleOpenFolder(job)}
                              title="Mở thư mục"
                              aria-label={`Open folder for job ${job.job_id}`}
                            >
                              📂
                            </button>
                          </>
                        )}
                        {job.status === 'failed' && (
                          <button
                            type="button"
                            className="btn btn-sm btn-secondary"
                            onClick={() => retryJob(job.job_id)}
                            title="Thử lại"
                            aria-label={`Retry job ${job.job_id}`}
                          >
                            🔄 Thử lại
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn btn-sm btn-danger-ghost btn-icon"
                          onClick={() => handleDelete(job)}
                          title="Xóa khỏi lịch sử"
                          aria-label={`Delete job ${job.job_id} from history`}
                          disabled={deletingJobId === job.job_id}
                        >
                          {deletingJobId === job.job_id ? (
                            <span className="spinner" style={{ width: 14, height: 14 }} />
                          ) : (
                            '🗑'
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
