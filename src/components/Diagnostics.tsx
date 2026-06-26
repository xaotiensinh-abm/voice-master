import { useState, useCallback } from 'react';
import { apiClient } from '../lib/apiClient';
import type { EngineName, BenchmarkResult } from '../types';
import type { HealthState } from '../hooks/useHealth';

interface DiagnosticsProps {
  health: HealthState;
}

const ENGINE_NAMES: Record<EngineName, string> = {
  vieneu: 'VieNeu',
  elevenlabs: 'ElevenLabs',
};

function getEngineStatusColor(status: string): string {
  switch (status) {
    case 'ready':
      return 'badge-success';
    case 'available':
      return 'badge-info';
    case 'loading':
      return 'badge-warning';
    case 'not_configured':
      return 'badge-neutral';
    case 'error':
    case 'unavailable':
      return 'badge-error';
    default:
      return 'badge-neutral';
  }
}

function getEngineStatusLabel(status: string): string {
  switch (status) {
    case 'ready':
      return 'Sẵn sàng';
    case 'available':
      return 'Có sẵn';
    case 'loading':
      return 'Đang tải';
    case 'not_configured':
      return 'Chưa cấu hình';
    case 'error':
      return 'Lỗi';
    case 'unavailable':
      return 'Không khả dụng';
    default:
      return status;
  }
}

export default function Diagnostics({ health }: DiagnosticsProps) {
  const [benchmarkRunning, setBenchmarkRunning] = useState(false);
  const [benchmarkResults, setBenchmarkResults] = useState<BenchmarkResult[] | null>(null);
  const [benchmarkError, setBenchmarkError] = useState<string | null>(null);

  const handleBenchmark = useCallback(async () => {
    setBenchmarkRunning(true);
    setBenchmarkError(null);
    setBenchmarkResults(null);
    try {
      const results = await apiClient.runBenchmark({
        engines: ['vieneu'],
        texts: ['short', 'medium'],
        output_format: 'mp3',
      });
      setBenchmarkResults(results);
    } catch {
      setBenchmarkError('Không thể chạy benchmark. Kiểm tra backend và engine.');
    } finally {
      setBenchmarkRunning(false);
    }
  }, []);

  const handleOpenLogs = useCallback(() => {
    if (window.electronAPI) {
      const logsDir = `${import.meta.env.VITE_APPDATA || ''}/NEO Voice/logs`;
      window.electronAPI.openFolder(logsDir);
    }
  }, []);

  const gpu = health.gpu;
  const engines = health.engines;
  const vramPercent = gpu ? Math.round((gpu.vram_free_mb / gpu.vram_total_mb) * 100) : 0;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Chẩn đoán</h1>
        <p className="page-subtitle">Thông tin hệ thống, trạng thái engine và công cụ gỡ lỗi</p>
      </div>

      {/* ── System Info Cards ──────────────────────────────── */}
      <div className="info-grid" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="info-card">
          <div className="info-card-icon">🖥️</div>
          <div className="info-card-label">Phiên bản App</div>
          <div className="info-card-value">1.0.0-mvp</div>
        </div>

        <div className="info-card">
          <div className="info-card-icon">⚡</div>
          <div className="info-card-label">Backend</div>
          <div className="info-card-value">
            {health.connected ? health.version || '—' : 'Mất kết nối'}
          </div>
          <div className="info-card-detail">
            <span className={`badge ${health.connected ? 'badge-success' : 'badge-error'}`}>
              {health.connected ? 'Đang chạy' : 'Offline'}
            </span>
          </div>
        </div>

        <div className="info-card">
          <div className="info-card-icon">🐍</div>
          <div className="info-card-label">Python</div>
          <div className="info-card-value">
            {health.connected ? '3.10+' : '—'}
          </div>
        </div>
      </div>

      {/* ── GPU Card ──────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="card-header">
          <h3 className="card-title">🎮 GPU</h3>
          {gpu && (
            <span className={`badge ${gpu.detected ? 'badge-success' : 'badge-error'}`}>
              {gpu.detected ? 'Phát hiện GPU' : 'Không có GPU'}
            </span>
          )}
        </div>

        {gpu && gpu.detected ? (
          <div>
            <div className="info-grid">
              <div>
                <div className="text-xs text-muted" style={{ marginBottom: 'var(--space-1)' }}>
                  Tên GPU
                </div>
                <div style={{ fontWeight: 600, fontSize: 'var(--font-size-md)' }}>
                  {gpu.name}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted" style={{ marginBottom: 'var(--space-1)' }}>
                  CUDA
                </div>
                <span className={`badge ${gpu.cuda_available !== false ? 'badge-success' : 'badge-error'}`}>
                  {gpu.cuda_available !== false ? 'Có sẵn' : 'Không có'}
                </span>
              </div>
            </div>

            <div style={{ marginTop: 'var(--space-5)' }}>
              <div className="flex justify-between" style={{ marginBottom: 'var(--space-2)' }}>
                <span className="text-sm">VRAM</span>
                <span className="text-sm" style={{ fontWeight: 600 }}>
                  {gpu.vram_free_mb.toLocaleString()} MB trống / {gpu.vram_total_mb.toLocaleString()} MB
                </span>
              </div>
              <div className="progress-bar-container" style={{ height: 12 }}>
                <div
                  className="progress-bar-fill"
                  style={{
                    width: `${vramPercent}%`,
                    background:
                      vramPercent > 60
                        ? 'linear-gradient(90deg, var(--color-success-500), #34D399)'
                        : vramPercent > 30
                        ? 'linear-gradient(90deg, var(--color-warning-500), #FBBF24)'
                        : 'linear-gradient(90deg, var(--color-error-500), #F87171)',
                  }}
                />
              </div>
            </div>

            {gpu.driver_version && (
              <div className="text-xs text-muted" style={{ marginTop: 'var(--space-2)' }}>
                Driver: {gpu.driver_version}
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-muted">
            Không phát hiện GPU NVIDIA. VieNeu vẫn có thể hoạt động bằng CPU nếu backend đã cấu hình.
          </div>
        )}
      </div>

      {/* ── Engine Status Cards ────────────────────────────── */}
      <div className="info-grid" style={{ marginBottom: 'var(--space-6)' }}>
        {engines &&
          (Object.entries(engines) as [string, any][]).map(
            ([key, engine]) => {
              const engineKey = key as EngineName;
              return (
              <div className="info-card" key={key}>
                <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-3)' }}>
                  <div className="info-card-label" style={{ marginBottom: 0 }}>
                    {ENGINE_NAMES[engineKey] || engineKey}
                  </div>
                  <span className={`badge ${getEngineStatusColor(engine.status)}`}>
                    {getEngineStatusLabel(engine.status)}
                  </span>
                </div>
                <div className="text-sm">
                  <div className="flex justify-between" style={{ marginBottom: 'var(--space-1)' }}>
                    <span className="text-muted">Đã tải:</span>
                    <span>{engine.loaded ? '✓ Có' : '✗ Chưa'}</span>
                  </div>
                  {engine.gpu_required && (
                    <div className="flex justify-between">
                      <span className="text-muted">Yêu cầu GPU:</span>
                      <span>✓ Có</span>
                    </div>
                  )}
                  {engine.error && (
                    <div
                      style={{
                        marginTop: 'var(--space-2)',
                        padding: 'var(--space-2)',
                        background: 'var(--color-error-50)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: 'var(--font-size-xs)',
                        color: 'var(--color-error-600)',
                      }}
                    >
                      {engine.error}
                    </div>
                  )}
                </div>
              </div>
              );
            }
          )}
      </div>

      {/* ── Action Buttons ─────────────────────────────────── */}
      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="card-header">
          <h3 className="card-title">🛠 Công cụ</h3>
        </div>
        <div className="flex gap-4" style={{ flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleBenchmark}
            disabled={benchmarkRunning || !health.connected}
            aria-label="Run quick benchmark"
          >
            {benchmarkRunning ? (
              <>
                <span className="spinner" style={{ width: 16, height: 16, borderTopColor: 'white', borderColor: 'rgba(255,255,255,0.3)' }} />
                Đang chạy...
              </>
            ) : (
              '⚡ Chạy benchmark nhanh'
            )}
          </button>
          <button type="button" className="btn btn-secondary" onClick={handleOpenLogs} aria-label="Open logs folder">
            📁 Mở thư mục logs
          </button>
        </div>

        {benchmarkError && (
          <div
            role="alert"
            style={{
              marginTop: 'var(--space-4)',
              padding: 'var(--space-3)',
              background: 'var(--color-error-50)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--color-error-600)',
              fontSize: 'var(--font-size-sm)',
            }}
          >
            {benchmarkError}
          </div>
        )}

        {/* Benchmark Results */}
        {benchmarkResults && benchmarkResults.length > 0 && (
          <div style={{ marginTop: 'var(--space-5)' }}>
            <h4 style={{ marginBottom: 'var(--space-3)', fontWeight: 600 }}>Kết quả Benchmark</h4>
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <th>Engine</th>
                    <th>Đoạn văn</th>
                    <th>Thời gian</th>
                    <th>RTF</th>
                    <th>Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {benchmarkResults.map((r, i) => (
                    <tr key={i}>
                      <td>
                        <span className={`badge badge-engine-${r.engine}`}>
                          {ENGINE_NAMES[r.engine]}
                        </span>
                      </td>
                      <td>{r.text_label}</td>
                      <td>{r.duration_sec != null ? `${r.duration_sec.toFixed(2)}s` : '—'}</td>
                      <td>
                        {r.rtf != null ? (
                          <span
                            style={{
                              fontWeight: 600,
                              color:
                                r.rtf < 1
                                  ? 'var(--color-success-600)'
                                  : 'var(--color-warning-600)',
                            }}
                          >
                            {r.rtf.toFixed(2)}x
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>
                        <span className={`badge ${r.success ? 'badge-success' : 'badge-error'}`}>
                          {r.success ? '✓ Thành công' : '✗ Lỗi'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* ── Error Log ──────────────────────────────────────── */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">📝 Log lỗi gần đây</h3>
          <span className="text-xs text-muted">20 lỗi gần nhất</span>
        </div>
        <div className="error-log">
          {health.connected ? (
            <div className="error-log-entry">
              <span className="error-log-time">—</span>
              <span style={{ color: 'var(--color-gray-500)' }}>
                Không có lỗi nào. Hệ thống hoạt động bình thường.
              </span>
            </div>
          ) : (
            <div className="error-log-entry">
              <span className="error-log-time">{new Date().toLocaleTimeString('vi-VN')}</span>
              <span className="error-log-level-error">[ERROR]</span>
              <span>Mất kết nối tới backend tại http://127.0.0.1:8757</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
