import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../lib/apiClient';
import { useModelStatus } from '../hooks/useModelStatus';
import type { Settings as TSettings, SettingsUpdateRequest, EngineName } from '../types';

function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return '—';
  const gb = bytes / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(2)} GB`;
  return `${(bytes / 1024 ** 2).toFixed(0)} MB`;
}

export default function Settings() {
  const model = useModelStatus();
  const [settings, setSettings] = useState<TSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  // ElevenLabs
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'success' | 'error'>('idle');

  // General
  const [outputFolder, setOutputFolder] = useState('');
  const [defaultEngine, setDefaultEngine] = useState<EngineName>('vieneu');
  const [bitrate, setBitrate] = useState(128);
  const [apiPort, setApiPort] = useState(8757);

  // Privacy
  const [cloudWarning, setCloudWarning] = useState(true);

  const fetchSettings = useCallback(async () => {
    try {
      const data = await apiClient.getSettings();
      setSettings(data);
      setOutputFolder(data.default_output_folder || '');
      setDefaultEngine(data.default_engine || 'vieneu');
      setBitrate(data.default_bitrate_kbps || 128);
      setApiPort(data.local_api_port || 8757);
      setCloudWarning(data.cloud_privacy_warning !== false);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleSave = useCallback(async (updates: SettingsUpdateRequest) => {
    setSaving(true);
    setSaveMessage(null);
    try {
      await apiClient.updateSettings(updates);
      setSaveMessage('Đã lưu thành công!');
      fetchSettings();
      setTimeout(() => setSaveMessage(null), 3000);
    } catch {
      setSaveMessage('Lỗi khi lưu. Vui lòng thử lại.');
    } finally {
      setSaving(false);
    }
  }, [fetchSettings]);

  const handleSelectOutputFolder = useCallback(async () => {
    if (window.electronAPI) {
      const folder = await window.electronAPI.selectOutputDir();
      if (folder) {
        setOutputFolder(folder);
        handleSave({ default_output_folder: folder });
      }
    }
  }, [handleSave]);

  const handleTestConnection = useCallback(async () => {
    setTestingConnection(true);
    setConnectionStatus('idle');
    try {
      // Save the API key first, then test
      if (apiKey) {
        await apiClient.updateSettings({ elevenlabs_api_key: apiKey });
      }
      const health = await apiClient.getHealth();
      if (health.engines.elevenlabs?.status === 'ready') {
        setConnectionStatus('success');
      } else {
        setConnectionStatus('error');
      }
    } catch {
      setConnectionStatus('error');
    } finally {
      setTestingConnection(false);
    }
  }, [apiKey]);

  const canTestElevenLabs = Boolean(apiKey || settings?.elevenlabs_api_key_set);

  if (loading) {
    return (
      <div>
        <div className="page-header">
          <h1 className="page-title">Cài đặt</h1>
        </div>
        <div className="settings-grid">
          <div className="skeleton" style={{ height: 200 }} />
          <div className="skeleton" style={{ height: 200 }} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="page-title">Cài đặt</h1>
            <p className="page-subtitle">Cấu hình ứng dụng và quản lý engine</p>
          </div>
          {saveMessage && (
            <span
              className={`badge ${saveMessage.includes('thành công') ? 'badge-success' : 'badge-error'}`}
              style={{ fontSize: 'var(--font-size-sm)', padding: 'var(--space-2) var(--space-3)' }}
            >
              {saveMessage}
            </span>
          )}
        </div>
      </div>

      <div className="settings-grid">
        {/* ── Section 1: General ───────────────────────────── */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-5)' }}>
            ⚙️ Chung
          </h3>

          <div className="settings-row">
            <label className="settings-label">Thư mục đầu ra</label>
            <div className="settings-value">
              <input
                type="text"
                className="input"
                value={outputFolder}
                readOnly
                placeholder="Chọn thư mục..."
                aria-label="Output folder"
                style={{ flex: 1 }}
              />
              <button type="button" className="btn btn-secondary btn-sm" onClick={handleSelectOutputFolder}>
                📁 Chọn
              </button>
            </div>
          </div>

          <div className="settings-row">
            <label className="settings-label">Engine mặc định</label>
            <div className="settings-value">
              <select
                className="select"
                value={defaultEngine}
                aria-label="Default engine"
                onChange={(e) => {
                  const val = e.target.value as EngineName;
                  setDefaultEngine(val);
                  handleSave({ default_engine: val });
                }}
              >
                <option value="vieneu">VieNeu</option>
                <option value="elevenlabs">ElevenLabs</option>
              </select>
            </div>
          </div>

          <div className="settings-row">
            <label className="settings-label">Bitrate MP3</label>
            <div className="settings-value">
              <select
                className="select"
                value={bitrate}
                aria-label="MP3 bitrate"
                onChange={(e) => {
                  const val = parseInt(e.target.value);
                  setBitrate(val);
                  handleSave({ default_bitrate_kbps: val });
                }}
              >
                <option value={64}>64 kbps</option>
                <option value={96}>96 kbps</option>
                <option value={128}>128 kbps</option>
                <option value={192}>192 kbps</option>
                <option value={256}>256 kbps</option>
                <option value={320}>320 kbps</option>
              </select>
            </div>
          </div>

          <div className="settings-row">
            <label className="settings-label">API Port</label>
            <div className="settings-value">
              <input
                type="number"
                className="input"
                value={apiPort}
                aria-label="Local API port"
                onChange={(e) => setApiPort(parseInt(e.target.value))}
                style={{ width: 120 }}
              />
              <span className="text-xs text-muted">Yêu cầu khởi động lại</span>
            </div>
          </div>
        </div>

        {/* ── Section 2: ElevenLabs ────────────────────────── */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-5)' }}>
            🔊 ElevenLabs
          </h3>

          <div className="settings-row">
            <label className="settings-label">API Key</label>
            <div className="settings-value">
              <div className="input-password-wrapper" style={{ flex: 1 }}>
                <input
                  type={showApiKey ? 'text' : 'password'}
                  className="input"
                  placeholder={settings?.elevenlabs_api_key_set ? '••••••••••••' : 'Nhập API key...'}
                  value={apiKey}
                  aria-label="ElevenLabs API key"
                  onChange={(e) => setApiKey(e.target.value)}
                />
                <button
                  className="input-password-toggle"
                  onClick={() => setShowApiKey(!showApiKey)}
                  type="button"
                  aria-label={showApiKey ? 'Hide ElevenLabs API key' : 'Show ElevenLabs API key'}
                  title={showApiKey ? 'Hide API key' : 'Show API key'}
                >
                  {showApiKey ? '🙈' : '👁'}
                </button>
              </div>
            </div>
          </div>

          <div className="settings-row">
            <label className="settings-label">Kết nối</label>
            <div className="settings-value">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleTestConnection}
                disabled={testingConnection || !canTestElevenLabs}
                title={canTestElevenLabs ? 'Test ElevenLabs connection' : 'Enter or save an ElevenLabs API key first'}
                aria-label="Test ElevenLabs connection"
              >
                {testingConnection ? (
                  <>
                    <span className="spinner" style={{ width: 14, height: 14 }} />
                    Đang kiểm tra...
                  </>
                ) : (
                  '🔗 Kiểm tra kết nối'
                )}
              </button>
              {connectionStatus === 'success' && (
                <span className="badge badge-success">✓ Kết nối thành công</span>
              )}
              {connectionStatus === 'error' && (
                <span className="badge badge-error">✗ Kết nối thất bại</span>
              )}
            </div>
          </div>

          {apiKey && (
            <div style={{ marginTop: 'var(--space-3)' }}>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => handleSave({ elevenlabs_api_key: apiKey })}
                disabled={saving}
                aria-label="Save ElevenLabs API key"
              >
                {saving ? 'Đang lưu...' : '💾 Lưu API Key'}
              </button>
            </div>
          )}
        </div>

        {/* ── Section 3: Models ─────────────────────────────── */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-5)' }}>
            🤖 Mô hình
          </h3>

          <div className="settings-row">
            <label className="settings-label">VieNeu Turbo</label>
            <div>
              <div className="flex items-center gap-3 mb-4" style={{ flexWrap: 'wrap' }}>
                {model.loading ? (
                  <span className="badge badge-neutral">Đang kiểm tra...</span>
                ) : model.downloaded ? (
                  <span className="badge badge-success">✓ Đã tải</span>
                ) : model.downloading ? (
                  <span className="badge badge-info">Đang tải...</span>
                ) : (
                  <span className="badge badge-warning">Chưa tải</span>
                )}
                {model.status && model.status.total_bytes > 0 && (
                  <span className="text-xs text-muted">
                    {formatBytes(model.status.total_bytes)}
                  </span>
                )}
              </div>

              {model.downloading && model.progress && (
                <div style={{ marginBottom: 'var(--space-4)' }}>
                  <div className="progress-bar-container">
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${Math.round(model.progress.percent)}%`, transition: 'width 0.4s ease' }}
                    />
                  </div>
                  <div className="progress-info">
                    <span>
                      {formatBytes(model.progress.downloaded_bytes)} / {formatBytes(model.progress.total_bytes)}
                    </span>
                    <span style={{ fontWeight: 600 }}>{Math.round(model.progress.percent)}%</span>
                  </div>
                </div>
              )}

              {model.error && !model.downloading && (
                <div role="alert" className="text-sm" style={{ color: 'var(--color-error-600)', marginBottom: 'var(--space-3)' }}>
                  ❌ {model.error}
                </div>
              )}

              {!model.downloading && (
                <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={model.startDownload}
                    aria-label={model.downloaded ? 'Tải lại mô hình' : 'Tải mô hình'}
                  >
                    {model.downloaded ? '🔄 Tải lại' : '⬇️ Tải mô hình'}
                  </button>
                  {model.downloaded && (
                    <button
                      type="button"
                      className="btn btn-danger-ghost btn-sm"
                      onClick={() => {
                        if (window.confirm('Xoá mô hình khỏi máy? Lần dùng sau sẽ phải tải lại (~700 MB).')) {
                          model.deleteModel();
                        }
                      }}
                      aria-label="Xoá mô hình khỏi máy"
                    >
                      🗑 Xoá
                    </button>
                  )}
                </div>
              )}

              {model.status?.cache_path && (
                <div className="text-xs text-muted" style={{ wordBreak: 'break-all', marginTop: 'var(--space-3)' }}>
                  📁 {model.status.cache_path}
                </div>
              )}
            </div>
          </div>

        </div>

        {/* ── Section 4: Privacy ────────────────────────────── */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-5)' }}>
            🔒 Quyền riêng tư
          </h3>

          <div className="settings-row">
            <label className="settings-label">Cảnh báo Cloud</label>
            <div className="flex items-center gap-3">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={cloudWarning}
                  aria-label="Show cloud privacy warning"
                  onChange={(e) => {
                    setCloudWarning(e.target.checked);
                    handleSave({ cloud_privacy_warning: e.target.checked });
                  }}
                />
                <span className="toggle-track" />
              </label>
              <span className="text-sm text-muted">
                Hiện cảnh báo khi dùng provider cloud (ElevenLabs)
              </span>
            </div>
          </div>

          <div
            style={{
              marginTop: 'var(--space-4)',
              padding: 'var(--space-4)',
              background: 'var(--color-warning-50)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-warning-100)',
            }}
          >
            <div style={{ fontWeight: 600, color: 'var(--color-warning-600)', marginBottom: 'var(--space-2)' }}>
              ⚠️ Lưu ý về quyền riêng tư
            </div>
            <div className="text-sm" style={{ color: 'var(--color-gray-600)' }}>
              VieNeu xử lý hoàn toàn trên máy tính của bạn. Khi sử dụng ElevenLabs,
              văn bản sẽ được gửi tới máy chủ ElevenLabs để tạo giọng nói. Không sử dụng ElevenLabs
              cho nội dung nhạy cảm hoặc bảo mật.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
