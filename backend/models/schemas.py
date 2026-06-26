"""NEO Voice Backend — Pydantic v2 schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ───────────────────────────── Enums ──────────────────────────────


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ErrorCode(str, Enum):
    UNKNOWN_VOICE = "UNKNOWN_VOICE"
    ENGINE_UNAVAILABLE = "ENGINE_UNAVAILABLE"
    GPU_MEMORY_LOW = "GPU_MEMORY_LOW"
    TEXT_EMPTY = "TEXT_EMPTY"
    FILE_UNSUPPORTED = "FILE_UNSUPPORTED"
    FILE_READ_ERROR = "FILE_READ_ERROR"
    ELEVENLABS_AUTH_FAILED = "ELEVENLABS_AUTH_FAILED"
    ELEVENLABS_QUOTA = "ELEVENLABS_QUOTA"
    ELEVENLABS_RATE_LIMIT = "ELEVENLABS_RATE_LIMIT"
    ELEVENLABS_NETWORK = "ELEVENLABS_NETWORK"
    ELEVENLABS_VOICE_NOT_FOUND = "ELEVENLABS_VOICE_NOT_FOUND"
    MP3_EXPORT_FAILED = "MP3_EXPORT_FAILED"
    WORKER_CRASHED = "WORKER_CRASHED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"


# Map error codes → Vietnamese UI messages
ERROR_MESSAGES: dict[str, str] = {
    "UNKNOWN_VOICE": "Không tìm thấy giọng đã chọn.",
    "ENGINE_UNAVAILABLE": "Engine chưa sẵn sàng. Kiểm tra cài đặt/model.",
    "GPU_MEMORY_LOW": "GPU không đủ VRAM cho engine này. Hãy dùng VieNeu hoặc ElevenLabs.",
    "TEXT_EMPTY": "Nội dung trống.",
    "FILE_UNSUPPORTED": "MVP chỉ hỗ trợ .txt, .md.",
    "FILE_READ_ERROR": "Không đọc được file. Kiểm tra encoding/quyền truy cập.",
    "ELEVENLABS_AUTH_FAILED": "ElevenLabs API key không hợp lệ.",
    "ELEVENLABS_QUOTA": "Tài khoản ElevenLabs hết quota hoặc bị giới hạn.",
    "ELEVENLABS_RATE_LIMIT": "Bị giới hạn tốc độ. Hãy thử lại sau.",
    "ELEVENLABS_NETWORK": "Không kết nối được ElevenLabs.",
    "ELEVENLABS_VOICE_NOT_FOUND": "Voice ID không tồn tại.",
    "MP3_EXPORT_FAILED": "Không xuất được MP3. Kiểm tra ffmpeg/logs.",
    "WORKER_CRASHED": "Worker bị lỗi. App đã ghi log và có thể retry.",
    "JOB_NOT_FOUND": "Không tìm thấy job.",
}


# ───────────────────────────── Health ─────────────────────────────


class EngineStatus(BaseModel):
    status: str = "not_loaded"  # ready | available | not_loaded | not_configured | error | unavailable
    loaded: bool = False
    gpu_required: bool = False
    error: str | None = None
    # None for engines where it does not apply (e.g. cloud). For VieNeu: whether
    # the local model has been downloaded to the HuggingFace cache.
    model_downloaded: bool | None = None


class GPUInfo(BaseModel):
    detected: bool = False
    name: str | None = None
    vram_total_mb: int | None = None
    vram_free_mb: int | None = None
    cuda_available: bool = False
    driver_version: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0-mvp"
    port: int = 8757
    engines: dict[str, EngineStatus] = {}
    gpu: GPUInfo = GPUInfo()
    # Per-engine max chars/chunk so the UI segment estimate stays in sync with
    # the backend chunker (services/text_pipeline.py) instead of hardcoding.
    max_chars_per_chunk: dict[str, int] = {}


# ───────────────────────────── Models (download) ──────────────────


class ModelStatusResponse(BaseModel):
    repo_id: str
    downloaded: bool = False
    total_bytes: int = 0
    cache_path: str = ""
    state: str = "idle"  # idle | downloading | done | error
    error: str | None = None


class ModelProgressResponse(BaseModel):
    state: str = "idle"  # idle | downloading | done | error
    downloaded_bytes: int = 0
    total_bytes: int = 0
    percent: float = 0
    error: str | None = None


# ───────────────────────────── Voices ─────────────────────────────


class VoiceInfo(BaseModel):
    voice_id: str
    display_name: str
    engine: str
    language: str = "vi"
    gender: str | None = None
    region: str | None = None
    styles: list[str] = []
    emotions: list[str] = []
    source: str | None = None
    license: str | None = None
    commercial_safe: str = "internal_review_required"
    available: bool = True
    local_path: str | None = None
    preview_path: str | None = None
    quality_score: float | None = None
    enabled: bool = True


class VoiceListResponse(BaseModel):
    voices: list[VoiceInfo]


class PreviewRequest(BaseModel):
    voice_id: str
    text: str = "Xin chào, đây là giọng đọc mẫu."
    output_format: str = "mp3"


class PreviewResponse(BaseModel):
    preview_id: str
    audio_url: str


# ───────────────────────────── Jobs ───────────────────────────────


class JobInput(BaseModel):
    type: Literal["text", "file"]
    text: str | None = None
    path: str | None = None
    file_type: str | None = None


class JobOutput(BaseModel):
    format: str = "mp3"
    bitrate_kbps: int = 128
    sample_rate: int = 44100
    folder: str | None = None


class JobCreateRequest(BaseModel):
    input: JobInput
    voice_id: str
    mode: Literal["neutral", "news", "story", "podcast"] = "neutral"
    emotion: Literal["neutral", "warm", "serious", "storytelling", "excited", "sad"] = "neutral"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    output: JobOutput = JobOutput()


class JobResponse(BaseModel):
    job_id: str
    status: str = "queued"


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float = 0
    stage: str | None = None
    voice_id: str
    engine: str | None = None
    segments_total: int = 0
    segments_done: int = 0
    created_at: str
    updated_at: str | None = None
    completed_at: str | None = None
    output_path: str | None = None
    audio_url: str | None = None  # absolute download URL when completed
    error: dict[str, str] | None = None


# ───────────────────────────── Synthesis (engine-level) ────────────


class SynthesisRequest(BaseModel):
    job_id: str
    voice_id: str
    text: str
    language: str = "vi"
    mode: Literal["neutral", "news", "story", "podcast"] = "neutral"
    emotion: Literal["neutral", "warm", "serious", "storytelling", "excited", "sad"] = "neutral"
    speed: float = 1.0
    seed: int | None = None
    output_dir: str = ""
    segment_index: int = 0
    engine_params: dict[str, Any] = {}


class SynthesisResult(BaseModel):
    ok: bool
    wav_path: str | None = None
    duration_sec: float | None = None
    sample_rate: int | None = None
    rtf: float | None = None
    error_code: str | None = None
    error_message: str | None = None
    metrics: dict[str, Any] = {}


# ───────────────────────────── Settings ───────────────────────────


class SettingsRequest(BaseModel):
    elevenlabs_api_key: str | None = None
    default_output_folder: str | None = None
    default_engine: str | None = None
    default_bitrate_kbps: int | None = None
    local_api_port: int | None = None
    elevenlabs_model_id: str | None = None
    elevenlabs_default_voice: str | None = None
    elevenlabs_auto_fallback: bool | None = None
    cloud_privacy_warning: bool | None = None


class SettingsResponse(BaseModel):
    elevenlabs_api_key: str | None = None  # always redacted
    elevenlabs_api_key_set: bool = False
    default_output_folder: str | None = None
    default_engine: str = "vieneu"
    default_bitrate_kbps: int = 128
    local_api_port: int = 8757
    elevenlabs_model_id: str | None = None
    elevenlabs_default_voice: str | None = None
    elevenlabs_auto_fallback: bool = False
    cloud_privacy_warning: bool = True
    vieneu_status: str | None = None


# ───────────────────────────── Diagnostics ────────────────────────


class DiagnosticsResponse(BaseModel):
    gpu: GPUInfo
    engines: dict[str, EngineStatus] = {}
    ffmpeg_available: bool = False


class BenchmarkRequest(BaseModel):
    engines: list[str] = ["vieneu"]
    texts: list[str] = ["short"]
    output_format: str = "mp3"


class BenchmarkResult(BaseModel):
    engine: str
    text_label: str
    duration_sec: float | None = None
    rtf: float | None = None
    ok: bool = True
    error: str | None = None


class BenchmarkResponse(BaseModel):
    results: list[BenchmarkResult]


# ───────────────────────────── OpenAI compat ──────────────────────


class OpenAISpeechRequest(BaseModel):
    model: str = "neo-vieneu"
    voice: str
    input: str
    response_format: str = "mp3"
    speed: float = 1.0


# ──────────────────────── ElevenLabs compat ───────────────────────


class ElevenLabsVoiceSettings(BaseModel):
    stability: float = 0.5
    similarity_boost: float = 0.75


class ElevenLabsSpeechRequest(BaseModel):
    text: str
    model_id: str = "neo-local"
    voice_settings: ElevenLabsVoiceSettings = ElevenLabsVoiceSettings()


# ───────────────────────────── Error ──────────────────────────────


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: str | None = None


def make_error(code: str, detail: str | None = None) -> ErrorResponse:
    """Create an error response with Vietnamese message from the code map."""
    return ErrorResponse(
        error_code=code,
        message=ERROR_MESSAGES.get(code, code),
        detail=detail,
    )
