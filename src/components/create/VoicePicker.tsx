import { useMemo } from 'react';
import type { Voice, EngineName } from '../../types';
import type { HealthState } from '../../hooks/useHealth';

const ENGINE_LABELS: Record<EngineName, string> = {
  vieneu: 'VieNeu',
  elevenlabs: 'ElevenLabs',
};

function getVoiceStatusBadge(voice: Voice, health: HealthState) {
  if (!voice.available) {
    const engineStatus = health.engines?.[voice.engine];
    if (engineStatus?.gpu_required && health.gpu && !health.gpu.detected) {
      return { label: 'Không đủ VRAM', cls: 'badge-warning' };
    }
    return { label: 'Chưa cấu hình', cls: 'badge-neutral' };
  }
  return { label: 'Sẵn sàng', cls: 'badge-success' };
}

interface VoicePickerProps {
  voices: Voice[];
  voicesLoading: boolean;
  engineFilter: EngineName | '';
  onEngineFilterChange: (value: EngineName | '') => void;
  selectedVoiceId: string;
  onSelectVoice: (voiceId: string) => void;
  selectedVoice: Voice | null;
  health: HealthState;
  previewing: boolean;
  onPreview: (voice: Voice) => void;
}

/** Step 1 — engine filter + voice dropdown (optgroup by engine) + preview. */
export default function VoicePicker({
  voices,
  voicesLoading,
  engineFilter,
  onEngineFilterChange,
  selectedVoiceId,
  onSelectVoice,
  selectedVoice,
  health,
  previewing,
  onPreview,
}: VoicePickerProps) {
  const voicesByEngine = useMemo(() => {
    const groups: Record<string, Voice[]> = {};
    for (const v of voices) {
      (groups[v.engine] ??= []).push(v);
    }
    return groups;
  }, [voices]);

  return (
    <div className="card">
      <div className="card-header" style={{ marginBottom: 'var(--space-3)' }}>
        <h3 className="card-title">1 · Chọn giọng</h3>
        {selectedVoice && (
          <span className={`badge ${getVoiceStatusBadge(selectedVoice, health).cls}`}>
            {getVoiceStatusBadge(selectedVoice, health).label}
          </span>
        )}
      </div>

      <div className="voice-picker-row">
        <select
          className="select"
          value={engineFilter}
          aria-label="Lọc theo engine"
          onChange={(e) => onEngineFilterChange(e.target.value as EngineName | '')}
          style={{ maxWidth: 160 }}
        >
          <option value="">Tất cả engine</option>
          <option value="vieneu">VieNeu</option>
          <option value="elevenlabs">ElevenLabs</option>
        </select>

        <select
          className="select"
          value={selectedVoiceId}
          aria-label="Chọn giọng nói"
          disabled={voicesLoading}
          onChange={(e) => onSelectVoice(e.target.value)}
          style={{ flex: 1 }}
        >
          <option value="">
            {voicesLoading ? 'Đang tải giọng...' : '— Chọn một giọng đọc —'}
          </option>
          {Object.entries(voicesByEngine).map(([engine, list]) => (
            <optgroup key={engine} label={ENGINE_LABELS[engine as EngineName] ?? engine}>
              {list.map((voice) => (
                <option key={voice.voice_id} value={voice.voice_id} disabled={!voice.available}>
                  {voice.display_name}
                  {!voice.available ? ' (chưa sẵn sàng)' : ''}
                </option>
              ))}
            </optgroup>
          ))}
        </select>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => selectedVoice && onPreview(selectedVoice)}
          disabled={!selectedVoice || !selectedVoice.available || previewing}
          aria-label="Nghe thử giọng đã chọn"
          title={selectedVoice ? 'Nghe thử' : 'Hãy chọn một giọng trước'}
        >
          {previewing ? <span className="spinner" style={{ width: 16, height: 16 }} /> : '▶'}
          Nghe thử
        </button>
      </div>

      {selectedVoice && (
        <div className="voice-picker-meta">
          <span className={`badge badge-engine-${selectedVoice.engine}`}>
            {ENGINE_LABELS[selectedVoice.engine]}
          </span>
          {selectedVoice.styles.length > 0 && (
            <span className="text-xs text-muted">Phù hợp: {selectedVoice.styles.join(', ')}</span>
          )}
          {selectedVoice.engine === 'elevenlabs' && (
            <span className="voice-card-privacy" style={{ marginTop: 0 }}>
              ⚠️ Gửi văn bản tới ElevenLabs Cloud
            </span>
          )}
        </div>
      )}
    </div>
  );
}
