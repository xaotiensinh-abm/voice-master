"""NEO Voice Backend — Base TTS Engine Adapter (ABC) & engine router."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from models.schemas import EngineStatus, SynthesisRequest, SynthesisResult, VoiceInfo


class EngineHealth:
    """Engine health report."""

    def __init__(
        self,
        status: str = "not_loaded",
        loaded: bool = False,
        gpu_required: bool = False,
        error: str | None = None,
        model_downloaded: bool | None = None,
    ):
        self.status = status
        self.loaded = loaded
        self.gpu_required = gpu_required
        self.error = error
        self.model_downloaded = model_downloaded

    def to_engine_status(self) -> EngineStatus:
        return EngineStatus(
            status=self.status,
            loaded=self.loaded,
            gpu_required=self.gpu_required,
            error=self.error,
            model_downloaded=self.model_downloaded,
        )


class TTSEngineAdapter(ABC):
    """Abstract base class for all TTS engine adapters."""

    engine_id: str = ""

    @abstractmethod
    def health(self) -> EngineHealth:
        """Return engine health status. Must work even before preload."""
        ...

    @abstractmethod
    def list_voices(self) -> list[VoiceInfo]:
        """Return available voices for this engine."""
        ...

    @abstractmethod
    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Render text to WAV segment. Main TTS call."""
        ...

    def preload(self) -> None:
        """Pre-load model/resources. Called during startup or first use."""
        pass

    def unload(self) -> None:
        """Unload model/resources. Called on shutdown or OOM recovery."""
        pass

    def benchmark(self, texts: list[str]) -> list[dict[str, Any]]:
        """Run benchmark on given texts. Optional."""
        return []


# ───────────────────── Engine Router ──────────────────────────────

_adapters: dict[str, TTSEngineAdapter] = {}


def register_adapter(prefix: str, adapter: TTSEngineAdapter) -> None:
    """Register an engine adapter for a voice_id prefix."""
    _adapters[prefix] = adapter


def get_adapter(voice_id: str) -> TTSEngineAdapter:
    """Route voice_id to the correct engine adapter.
    
    Routing rule from spec §06:
    - vieneu:* → VieneuAdapter
    - elevenlabs:* → ElevenLabsAdapter
    """
    prefix = voice_id.split(":", 1)[0] if ":" in voice_id else ""
    if prefix not in _adapters:
        raise KeyError(f"No adapter registered for prefix: {prefix}")
    return _adapters[prefix]


def get_all_adapters() -> dict[str, TTSEngineAdapter]:
    """Return all registered adapters."""
    return dict(_adapters)


def get_engine_statuses() -> dict[str, EngineStatus]:
    """Get health status for all registered engines."""
    result = {}
    for prefix, adapter in _adapters.items():
        try:
            health = adapter.health()
            # Map prefix to display name
            engine_name = {
                "vieneu": "vieneu",
                "elevenlabs": "elevenlabs",
            }.get(prefix, prefix)
            result[engine_name] = health.to_engine_status()
        except Exception:
            result[prefix] = EngineStatus(status="error")
    return result
