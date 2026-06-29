/* ============================================================
   NEO Voice — TypeScript type definitions
   Matches backend API schemas from 05_local_api_spec.md
   ============================================================ */

// ── Engine ──────────────────────────────────────────────────
export type EngineName = 'vieneu' | 'elevenlabs';

export type EngineStatusValue =
  | 'ready'
  | 'available'
  | 'loading'
  | 'not_configured'
  | 'error'
  | 'unavailable';

export interface EngineStatus {
  status: EngineStatusValue;
  loaded: boolean;
  gpu_required?: boolean;
  error?: string;
  // VieNeu: whether the local model has been downloaded. null = not applicable.
  model_downloaded?: boolean | null;
}

// ── Model download ──────────────────────────────────────────
export type ModelDownloadState = 'idle' | 'downloading' | 'done' | 'error';

export interface ModelStatus {
  repo_id: string;
  downloaded: boolean;
  total_bytes: number;
  cache_path: string;
  state: ModelDownloadState;
  error?: string | null;
}

export interface ModelProgress {
  state: ModelDownloadState;
  downloaded_bytes: number;
  total_bytes: number;
  percent: number;
  error?: string | null;
}

// ── GPU ─────────────────────────────────────────────────────
export interface GPUInfo {
  detected: boolean;
  name: string;
  vram_total_mb: number;
  vram_free_mb: number;
  cuda_available?: boolean;
  driver_version?: string;
}

// ── Health ──────────────────────────────────────────────────
export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  version: string;
  port: number;
  engines: Record<EngineName, EngineStatus>;
  gpu: GPUInfo;
  max_chars_per_chunk?: Record<string, number>;
  license?: { state: LicenseState; enforced: boolean; days_left: number | null } | null;
}

// ── License ─────────────────────────────────────────────────
export type LicenseState = 'dev' | 'trial' | 'licensed' | 'expired' | 'invalid';

export interface LicenseStatus {
  state: LicenseState;
  enforced: boolean;
  days_left: number | null;
  machine_code: string;
  exp?: string | null;
  tier?: string | null;
  reason?: string | null;
}

export interface LicenseActivateResponse {
  ok: boolean;
  state?: string | null;
  exp?: string | null;
  message: string;
}

// ── Voice ───────────────────────────────────────────────────
export type VoiceStyle = 'news' | 'story' | 'podcast' | 'neutral';
export type EmotionType = 'neutral' | 'warm' | 'serious' | 'storytelling' | 'excited' | 'sad';

export interface Voice {
  voice_id: string;
  display_name: string;
  engine: EngineName;
  language: string;
  styles: VoiceStyle[];
  emotions?: EmotionType[];
  license: string;
  source: string;
  commercial_safe: string;
  available: boolean;
  sample_url?: string;
}

export interface VoiceListResponse {
  voices: Voice[];
}

export interface VoicePreviewRequest {
  voice_id: string;
  text: string;
  output_format: 'mp3';
}

export interface VoicePreviewResponse {
  preview_id: string;
  audio_url: string;
}

// ── Job ─────────────────────────────────────────────────────
export type JobStatus =
  | 'queued'
  | 'running'
  | 'preparing_text'
  | 'loading_engine'
  | 'rendering_segment'
  | 'exporting_mp3'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'canceled';

export interface JobInput {
  type: 'text' | 'file';
  text?: string;
  path?: string;
  file_type?: 'txt' | 'md';
}

export interface JobOutput {
  format: 'mp3';
  bitrate_kbps?: number;
  sample_rate?: number;
  folder?: string;
}

export interface JobCreateRequest {
  input: JobInput;
  voice_id: string;
  mode: VoiceStyle;
  emotion?: EmotionType;
  speed?: number;
  output: JobOutput;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  progress: number;
  stage: string;
  voice_id: string;
  engine: EngineName;
  segments_total: number;
  segments_done: number;
  created_at: string;
  output_path?: string;
  error?: any;
  completed_at?: string;
  duration_seconds?: number;
  input_preview?: string;
}

export interface JobCreateResponse {
  job_id: string;
  status: JobStatus;
}

// ── Settings ────────────────────────────────────────────────
export interface Settings {
  elevenlabs_api_key?: string | null;
  elevenlabs_api_key_set: boolean;
  default_output_folder?: string | null;
  default_engine: EngineName;
  default_bitrate_kbps: number;
  local_api_port: number;
  elevenlabs_model_id?: string | null;
  elevenlabs_default_model?: string;
  elevenlabs_default_voice?: string | null;
  elevenlabs_auto_fallback?: boolean;
  vieneu_model_path?: string;
  vieneu_status?: string;
  cloud_privacy_warning: boolean;
}

export interface SettingsUpdateRequest {
  elevenlabs_api_key?: string;
  default_output_folder?: string;
  default_bitrate_kbps?: number;
  local_api_port?: number;
  default_engine?: EngineName;
  cloud_privacy_warning?: boolean;
}

// ── Diagnostics ─────────────────────────────────────────────
export interface DiagnosticsData {
  app_version: string;
  backend_version: string;
  python_version: string;
  gpu: GPUInfo;
  engines: Record<EngineName, EngineStatus>;
  errors: DiagnosticError[];
}

export interface DiagnosticError {
  timestamp: string;
  level: 'error' | 'warning';
  message: string;
  source?: string;
}

export interface BenchmarkRequest {
  engines: EngineName[];
  texts: ('short' | 'medium' | 'long')[];
  output_format: 'mp3';
}

export interface BenchmarkResult {
  engine: EngineName;
  text_label: string;
  duration_sec: number | null;
  rtf: number | null;
  ok: boolean;
  text_length?: string;
  duration_seconds?: number | null;
  success?: boolean;
  error?: string;
}

// ── API Error ───────────────────────────────────────────────
export type APIErrorCode =
  | 'UNKNOWN_VOICE'
  | 'ENGINE_UNAVAILABLE'
  | 'GPU_MEMORY_LOW'
  | 'TEXT_EMPTY'
  | 'FILE_UNSUPPORTED'
  | 'FILE_READ_ERROR'
  | 'ELEVENLABS_AUTH_FAILED'
  | 'ELEVENLABS_QUOTA'
  | 'ELEVENLABS_RATE_LIMIT'
  | 'ELEVENLABS_NETWORK'
  | 'ELEVENLABS_VOICE_NOT_FOUND'
  | 'MP3_EXPORT_FAILED'
  | 'WORKER_CRASHED';

export interface APIError {
  code: APIErrorCode;
  message: string;
  detail?: string;
}

// ── Electron IPC ────────────────────────────────────────────
export interface ElectronAPI {
  openFile: () => Promise<{ path: string; content: string; name: string } | null>;
  selectOutputDir: () => Promise<string | null>;
  openFolder: (folderPath: string) => Promise<void>;
  openFileInExplorer: (filePath: string) => Promise<void>;
  getAppVersion: () => Promise<string>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
