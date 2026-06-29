import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useVoices } from '../hooks/useVoices';
import { useJobs } from '../hooks/useJobs';
import { useModelStatus } from '../hooks/useModelStatus';
import ModelDownloadGate from './ModelDownloadGate';
import VoicePicker from './create/VoicePicker';
import EmotionGuide from './create/EmotionGuide';
import JobResult from './create/JobResult';
import { apiClient } from '../lib/apiClient';
import type { Voice, EngineName, VoiceStyle, EmotionType } from '../types';
import type { HealthState } from '../hooks/useHealth';

interface CreateVoiceProps {
  health: HealthState;
}

const MODES: { value: VoiceStyle; label: string }[] = [
  { value: 'neutral', label: 'Trung tính' },
  { value: 'news', label: 'Tin tức' },
  { value: 'story', label: 'Đọc truyện' },
  { value: 'podcast', label: 'Podcast' },
];

const EMOTIONS: { value: EmotionType; label: string }[] = [
  { value: 'neutral', label: 'Trung tính' },
  { value: 'warm', label: 'Ấm áp' },
  { value: 'serious', label: 'Nghiêm túc' },
  { value: 'storytelling', label: 'Kể chuyện' },
  { value: 'excited', label: 'Hào hứng' },
  { value: 'sad', label: 'Trầm buồn' },
];

// Inline emotion cues — embedded directly in the text (VieNeu, experimental).
// Source: pnnbao97/VieNeu-TTS — e.g. "[cười] Trời ơi, cái giọng nó tự nhiên..."
const EMOTION_TAGS: { tag: string; label: string }[] = [
  { tag: '[cười]', label: '😄 Cười' },
  { tag: '[thở dài]', label: '😮‍💨 Thở dài' },
  { tag: '[hắng giọng]', label: '🗣 Hắng giọng' },
];

// Fallback chunk limits if /health hasn't reported them yet
// (authoritative source: backend/config.py MAX_CHARS_PER_CHUNK, surfaced via /health).
const FALLBACK_MAX_CHARS: Record<EngineName, number> = {
  vieneu: 900,
  elevenlabs: 2000,
};

/** Rough segment estimate matching the backend paragraph/sentence chunker. */
function estimateSegments(text: string, maxChars: number): number {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  const paragraphs = trimmed.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  let segments = 0;
  for (const para of paragraphs) {
    segments += Math.max(1, Math.ceil(para.length / maxChars));
  }
  return Math.max(1, segments);
}

export default function CreateVoice({ health }: CreateVoiceProps) {
  // Voice selection
  const [engineFilter, setEngineFilter] = useState<EngineName | ''>('');
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>('');

  // Input
  const [inputTab, setInputTab] = useState<'text' | 'file'>('text');
  const [textInput, setTextInput] = useState('');
  const [fileInfo, setFileInfo] = useState<{ path: string; content: string; name: string } | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Controls
  const [mode, setMode] = useState<VoiceStyle>('neutral');
  const [emotion, setEmotion] = useState<EmotionType>('neutral');
  const [speed, setSpeed] = useState(1.0);
  const [showEmotionGuide, setShowEmotionGuide] = useState(false);

  // Voices
  const voicesFilter = engineFilter ? { engine: engineFilter as EngineName } : undefined;
  const { voices, loading: voicesLoading, refetch: refetchVoices } = useVoices(voicesFilter);

  // Re-fetch voices when the backend transitions disconnected → connected, so a
  // single failed fetch (e.g. backend restart) doesn't leave the dropdown empty.
  const wasConnected = useRef(health.connected);
  useEffect(() => {
    if (health.connected && !wasConnected.current) {
      refetchVoices();
    }
    wasConnected.current = health.connected;
  }, [health.connected, refetchVoices]);

  // Jobs
  const { currentJob, creating, createJob, cancelJob, clearCurrentJob } = useJobs();

  // VieNeu model download (first-run)
  const model = useModelStatus();

  const selectedVoice = useMemo(
    () => voices.find((v) => v.voice_id === selectedVoiceId) ?? null,
    [voices, selectedVoiceId]
  );

  // Clear a stale selection when the engine filter (or refetch) removes the
  // currently selected voice from the list, so the dropdown can't show blank
  // while selectedVoiceId silently retains an out-of-list id.
  useEffect(() => {
    if (selectedVoiceId && !voicesLoading && !voices.some((v) => v.voice_id === selectedVoiceId)) {
      setSelectedVoiceId('');
    }
  }, [voices, voicesLoading, selectedVoiceId]);

  // First-run gate: VieNeu voice picked but the local model isn't downloaded yet.
  const showModelGate =
    selectedVoice?.engine === 'vieneu' && !model.loading && !model.downloaded;

  // License gate: enforced build + trial expired / invalid key blocks voice creation.
  const lic = health.data?.license;
  const licenseBlocked = !!lic?.enforced && (lic.state === 'expired' || lic.state === 'invalid');

  // Insert an inline emotion tag at the cursor position in the textarea
  const insertEmotionTag = useCallback((tag: string) => {
    setInputTab('text');
    const el = textareaRef.current;
    if (!el) {
      setTextInput((prev) => (prev ? `${prev} ${tag} ` : `${tag} `));
      return;
    }
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    setTextInput((prev) => {
      const before = prev.slice(0, start);
      const after = prev.slice(end);
      const insert = `${tag} `;
      const next = `${before}${insert}${after}`;
      // Restore cursor after the inserted tag on next tick
      requestAnimationFrame(() => {
        el.focus();
        const pos = start + insert.length;
        el.setSelectionRange(pos, pos);
      });
      return next;
    });
  }, []);

  // Handle file upload
  const handleFileUpload = useCallback(async () => {
    if (window.electronAPI) {
      const result = await window.electronAPI.openFile();
      if (result) {
        setFileInfo(result);
      }
    }
  }, []);

  // Effective content + char count for the active input
  const activeContent = inputTab === 'text' ? textInput : fileInfo?.content ?? '';
  const charCount = activeContent.length;
  const engineForEstimate = selectedVoice?.engine ?? 'vieneu';
  const maxChars =
    health.data?.max_chars_per_chunk?.[engineForEstimate] ??
    FALLBACK_MAX_CHARS[engineForEstimate] ??
    900;
  const segmentEstimate = useMemo(
    () => estimateSegments(activeContent, maxChars),
    [activeContent, maxChars]
  );

  // Handle render
  const handleRender = useCallback(async () => {
    if (!selectedVoice) return;

    if (inputTab === 'text' && !textInput.trim()) return;
    if (inputTab === 'file' && !fileInfo) return;

    await createJob({
      input:
        inputTab === 'text'
          ? { type: 'text', text: textInput }
          : { type: 'file', path: fileInfo!.path, file_type: fileInfo!.name.endsWith('.md') ? 'md' : 'txt' },
      voice_id: selectedVoice.voice_id,
      mode,
      emotion,
      speed,
      output: { format: 'mp3' },
    });
  }, [selectedVoice, inputTab, textInput, fileInfo, mode, emotion, speed, createJob]);

  // Preview voice
  const [previewAudio, setPreviewAudio] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const handlePreview = useCallback(async (voice: Voice) => {
    setPreviewing(true);
    try {
      const result = await apiClient.previewVoice({
        voice_id: voice.voice_id,
        text: 'Xin chào, đây là giọng đọc mẫu.',
        output_format: 'mp3',
      });
      setPreviewAudio(apiClient.getPreviewAudioUrl(result.preview_id));
    } catch {
      // ignore preview errors
    } finally {
      setPreviewing(false);
    }
  }, []);

  const jobActive = !!currentJob && ['queued', 'running'].includes(currentJob.status);

  const canRender =
    selectedVoice &&
    selectedVoice.available &&
    !showModelGate &&
    !licenseBlocked &&
    ((inputTab === 'text' && textInput.trim().length > 0) ||
      (inputTab === 'file' && fileInfo)) &&
    !creating &&
    !jobActive;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Tạo giọng nói</h1>
        <p className="page-subtitle">Chọn giọng, nhập văn bản và tạo file MP3 chất lượng cao</p>
      </div>

      {licenseBlocked && (
        <div className="card" style={{ maxWidth: 880, margin: '0 auto var(--space-4)', borderColor: 'var(--color-error-200, #fecaca)' }}>
          <div style={{ fontWeight: 600, color: 'var(--color-error-700, #b91c1c)', marginBottom: 'var(--space-1)' }}>
            ⚠️ {lic?.state === 'expired' ? 'Hết hạn dùng thử' : 'Mã đăng ký không hợp lệ'}
          </div>
          <div className="text-sm text-muted">
            Không thể tạo giọng nói cho tới khi kích hoạt. Mở tab <strong>🔑 Bản quyền</strong> để nhập mã đăng ký.
          </div>
        </div>
      )}

      <div className="create-form">
        {/* ── 1. Voice selection ──────────────────────────────── */}
        <VoicePicker
          voices={voices}
          voicesLoading={voicesLoading}
          engineFilter={engineFilter}
          onEngineFilterChange={setEngineFilter}
          selectedVoiceId={selectedVoiceId}
          onSelectVoice={setSelectedVoiceId}
          selectedVoice={selectedVoice}
          health={health}
          previewing={previewing}
          onPreview={handlePreview}
        />

        {showModelGate ? (
          <ModelDownloadGate
            status={model.status}
            progress={model.progress}
            downloading={model.downloading}
            error={model.error}
            onDownload={model.startDownload}
          />
        ) : (
        <>
        {/* ── 2. Text / file input ────────────────────────────── */}
        <div className="card">
          <div className="tabs">
            <button
              type="button"
              className={`tab ${inputTab === 'text' ? 'active' : ''}`}
              aria-pressed={inputTab === 'text'}
              onClick={() => setInputTab('text')}
            >
              ✏️ Nhập văn bản
            </button>
            <button
              type="button"
              className={`tab ${inputTab === 'file' ? 'active' : ''}`}
              aria-pressed={inputTab === 'file'}
              onClick={() => setInputTab('file')}
            >
              📁 Chọn file
            </button>
          </div>

          {inputTab === 'text' ? (
            <>
              <textarea
                ref={textareaRef}
                className="textarea textarea-compact"
                placeholder="Nhập nội dung cần tạo giọng đọc tại đây..."
                aria-label="Văn bản cần đọc"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
              />
              <div className="input-meta-row">
                <span className="text-xs text-muted">
                  {charCount.toLocaleString()} ký tự
                </span>
                {segmentEstimate > 1 && (
                  <span className="segment-estimate" title="Văn bản dài sẽ được tự động chia đoạn, tạo lần lượt rồi ghép lại thành một file">
                    🧩 ~{segmentEstimate} đoạn (tự động ghép)
                  </span>
                )}
              </div>

              {/* Inline emotion cues */}
              <div className="emotion-tags">
                <span className="text-xs text-muted">Chèn cảm xúc:</span>
                {EMOTION_TAGS.map((t) => (
                  <button
                    type="button"
                    key={t.tag}
                    className="chip chip-sm"
                    onClick={() => insertEmotionTag(t.tag)}
                    title={`Chèn ${t.tag} vào vị trí con trỏ`}
                  >
                    {t.label}
                  </button>
                ))}
                <button
                  type="button"
                  className="btn btn-ghost btn-sm emotion-guide-toggle"
                  onClick={() => setShowEmotionGuide((s) => !s)}
                  aria-expanded={showEmotionGuide}
                >
                  {showEmotionGuide ? '▾ Ẩn hướng dẫn' : '❔ Hướng dẫn cảm xúc'}
                </button>
              </div>

              {showEmotionGuide && <EmotionGuide />}
            </>
          ) : (
            <>
              {!fileInfo ? (
                <button type="button" className="upload-zone" onClick={handleFileUpload}>
                  <div className="upload-zone-icon">📄</div>
                  <div className="upload-zone-text">Nhấn để chọn file .txt hoặc .md</div>
                  <div className="upload-zone-hint">Hỗ trợ định dạng text và markdown</div>
                </button>
              ) : (
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <span style={{ fontSize: 24 }}>📄</span>
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--color-gray-800)' }}>
                          {fileInfo.name}
                        </div>
                        <div className="text-xs text-muted">
                          {fileInfo.content.length.toLocaleString()} ký tự
                          {segmentEstimate > 1 && ` · ~${segmentEstimate} đoạn`}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      aria-label="Xóa file đã chọn"
                      onClick={() => setFileInfo(null)}
                    >
                      ✕ Xóa
                    </button>
                  </div>
                  <div className="file-preview">
                    {fileInfo.content.slice(0, 2000)}
                    {fileInfo.content.length > 2000 && (
                      <span className="text-muted">... (đã cắt để xem trước)</span>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* ── 3. Controls ─────────────────────────────────────── */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-4)' }}>
            3 · Tuỳ chỉnh
          </h3>

          <div className="controls-grid">
            <div className="input-group">
              <label className="input-label" htmlFor="mode-select">Phong cách đọc</label>
              <select
                id="mode-select"
                className="select"
                value={mode}
                onChange={(e) => setMode(e.target.value as VoiceStyle)}
              >
                {MODES.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>

            <div className="input-group">
              <label className="input-label" htmlFor="emotion-select">Cảm xúc</label>
              <select
                id="emotion-select"
                className="select"
                value={emotion}
                onChange={(e) => setEmotion(e.target.value as EmotionType)}
              >
                {EMOTIONS.map((em) => (
                  <option key={em.value} value={em.value}>{em.label}</option>
                ))}
              </select>
            </div>

            <div className="input-group">
              <div className="slider-header">
                <label className="input-label" htmlFor="speed-range">Tốc độ đọc</label>
                <span className="slider-value">{speed.toFixed(1)}x</span>
              </div>
              <input
                id="speed-range"
                type="range"
                min="0.5"
                max="2.0"
                step="0.1"
                value={speed}
                aria-label="Tốc độ đọc"
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
              />
              <div className="flex justify-between text-xs text-muted">
                <span>Chậm 0.5x</span>
                <span>Nhanh 2.0x</span>
              </div>
            </div>
          </div>

          <div className="input-group" style={{ marginTop: 'var(--space-4)' }}>
            <label className="input-label">Định dạng đầu ra</label>
            <div className="flex items-center gap-2">
              <span className="badge badge-primary">MP3</span>
              <span className="text-xs text-muted">128 kbps, 44100 Hz</span>
            </div>
          </div>
        </div>
        </>
        )}
      </div>

      {/* ── Sticky bottom bar: Render + progress + result ─────── */}
      <div className="create-bottom">
        <div className="create-bottom-bar">
          <div className="create-bottom-actions">
            <button
              type="button"
              className="btn-render"
              disabled={!canRender}
              onClick={handleRender}
              aria-label="Tạo MP3"
              title={canRender ? 'Tạo MP3' : 'Chọn giọng và nhập văn bản trước'}
            >
              {creating || jobActive ? (
                <>
                  <span className="spinner" style={{ width: 18, height: 18, borderTopColor: 'white', borderColor: 'rgba(255,255,255,0.3)' }} />
                  Đang tạo...
                </>
              ) : (
                '🎙 Tạo MP3'
              )}
            </button>

            {jobActive && currentJob && (
              <button
                type="button"
                className="btn btn-danger-ghost"
                onClick={() => cancelJob(currentJob.job_id)}
                aria-label="Hủy tạo"
                style={{ marginLeft: 'var(--space-3)' }}
              >
                ✕ Hủy
              </button>
            )}
          </div>

          <div className="create-bottom-progress">
            {currentJob && <JobResult job={currentJob} onClear={clearCurrentJob} />}
          </div>
        </div>
      </div>

      {/* Hidden audio for preview */}
      {previewAudio && (
        <audio
          src={previewAudio}
          autoPlay
          onEnded={() => setPreviewAudio(null)}
          style={{ display: 'none' }}
        />
      )}
    </div>
  );
}
