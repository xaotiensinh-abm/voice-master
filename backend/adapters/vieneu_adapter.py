"""NEO Voice Backend — VieNeu TTS Adapter.

Default production local engine. Wraps the `vieneu` Python package.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

from adapters.base import EngineHealth, TTSEngineAdapter
from models.schemas import SynthesisRequest, SynthesisResult, VoiceInfo
from utils.audio import change_audio_speed

logger = logging.getLogger(__name__)

# ───────────────────── Check SDK availability ─────────────────────

_VIENEU_AVAILABLE = False
try:
    import vieneu  # type: ignore

    _VIENEU_AVAILABLE = True
except ImportError:
    logger.info("VieNeu SDK not installed. Engine will be unavailable.")


# ───────────────────── Emotion → mode mapping ─────────────────────
# From spec §06 and §09

EMOTION_MAP: dict[str, dict[str, Any]] = {
    "neutral": {"speed_mult": 1.0, "cue": None},
    "warm": {"speed_mult": 1.0, "cue": None},  # mild punctuation/pause only
    "serious": {"speed_mult": 0.95, "cue": None},
    "storytelling": {"speed_mult": 0.95, "cue": None},  # paragraph pause + slightly slower
    "excited": {"speed_mult": 1.0, "cue": None},  # optional [cười] only if experimental
    "sad": {"speed_mult": 0.93, "cue": None},
}

MODE_MAP: dict[str, dict[str, Any]] = {
    "neutral": {"speed_mult": 1.0},
    "news": {"speed_mult": 1.05},
    "story": {"speed_mult": 0.95},
    "podcast": {"speed_mult": 1.0},
}

# Fallback voice config — sdk_voice must match SDK's display name exactly
FALLBACK_VOICES = [
    {"slug": "ngoc_lan", "display_name": "Ngọc Lan", "sdk_voice": "Ngọc Lan"},
    {"slug": "gia_bao", "display_name": "Gia Bảo", "sdk_voice": "Gia Bảo"},
    {"slug": "thai_son", "display_name": "Thái Sơn", "sdk_voice": "Thái Sơn"},
    {"slug": "duc_tri", "display_name": "Đức Trí", "sdk_voice": "Đức Trí"},
    {"slug": "my_duyen", "display_name": "Mỹ Duyên", "sdk_voice": "Mỹ Duyên"},
    {"slug": "truc_ly", "display_name": "Trúc Ly", "sdk_voice": "Trúc Ly"},
    {"slug": "xuan_vinh", "display_name": "Xuân Vĩnh", "sdk_voice": "Xuân Vĩnh"},
    {"slug": "truong_huu", "display_name": "Trường Hữu", "sdk_voice": "Trường Hữu"},
    {"slug": "binh_an", "display_name": "Bình An", "sdk_voice": "Bình An"},
    {"slug": "ngoc_linh", "display_name": "Ngọc Linh", "sdk_voice": "Ngọc Linh"},
]

# Build slug → SDK voice name lookup
_SLUG_TO_SDK: dict[str, str] = {v["slug"]: v["sdk_voice"] for v in FALLBACK_VOICES}


class VieneuAdapter(TTSEngineAdapter):
    """VieNeu TTS engine adapter."""

    engine_id = "vieneu"

    def __init__(self) -> None:
        self._tts: Any = None
        self._loaded = False
        self._device = "unknown"  # "cuda:0" | "cpu" once loaded
        self._loading_lock = asyncio.Lock()
        self._synth_lock = asyncio.Lock()
        self._voices: list[VoiceInfo] = []

    def _resolve_device_label(self, use_cuda: bool) -> str:
        """Best-effort label of the device the loaded engine runs on."""
        try:
            eng = getattr(self._tts, "engine", None)
            dev = getattr(eng, "device", None)
            if dev is not None:
                return str(dev)
        except Exception:
            pass
        return "cuda" if use_cuda else "cpu"

    def health(self) -> EngineHealth:
        """Health works even before preload."""
        if not _VIENEU_AVAILABLE:
            return EngineHealth(
                status="unavailable",
                loaded=False,
                error="VieNeu SDK not installed. Run: pip install vieneu",
            )
        # Cheap memoized cache check so /health polling stays fast.
        from services import model_manager

        downloaded = model_manager.is_downloaded()
        if self._loaded:
            return EngineHealth(status="ready", loaded=True, model_downloaded=downloaded, device=self._device)
        return EngineHealth(status="available", loaded=False, model_downloaded=downloaded)

    def preload(self) -> None:
        """Instantiate VieNeu TTS engine."""
        if not _VIENEU_AVAILABLE:
            return
        if self._loaded:
            return
        try:
            from vieneu import Vieneu  # type: ignore

            # Default to GPU 100% when a CUDA GPU is present: force the PyTorch
            # engine on cuda instead of relying on "auto" (which can fall back to
            # ONNX/CPU). Fall back to ONNX/CPU only when CUDA is unavailable.
            use_cuda = False
            try:
                import torch  # only present in the GPU build

                use_cuda = bool(torch.cuda.is_available())
            except Exception:
                use_cuda = False

            if use_cuda:
                self._tts = Vieneu(device="cuda", backend="pytorch")
            else:
                self._tts = Vieneu()

            self._device = self._resolve_device_label(use_cuda)
            self._loaded = True
            logger.info("VieNeu engine loaded on %s", self._device)
        except Exception as e:
            logger.error("VieNeu preload failed: %s", e)
            self._loaded = False

    def unload(self) -> None:
        """Unload VieNeu engine."""
        self._tts = None
        self._loaded = False
        logger.info("VieNeu engine unloaded")

    def list_voices(self) -> list[VoiceInfo]:
        """List available voices from SDK or fallback config."""
        if self._voices:
            return self._voices

        voices: list[VoiceInfo] = []

        # Try SDK listing
        if self._tts is not None:
            try:
                if hasattr(self._tts, "list_preset_voices"):
                    for label, vid in self._tts.list_preset_voices():
                        slug = _slugify(label)
                        _SLUG_TO_SDK[slug] = label
                        voices.append(
                            VoiceInfo(
                                voice_id=f"vieneu:{slug}",
                                display_name=label,
                                engine="vieneu",
                                language="vi",
                                styles=["neutral", "news", "story", "podcast"],
                                emotions=["neutral", "warm", "serious"],
                                source="vieneu-sdk",
                                commercial_safe="internal_review_required",
                            )
                        )
            except Exception as e:
                logger.warning("VieNeu voice listing failed: %s", e)

        # Fallback if SDK listing failed or returned nothing
        if not voices:
            for v in FALLBACK_VOICES:
                voices.append(
                    VoiceInfo(
                        voice_id=f"vieneu:{v['slug']}",
                        display_name=v["display_name"],
                        engine="vieneu",
                        language="vi",
                        styles=["neutral", "news", "story", "podcast"],
                        emotions=["neutral", "warm", "serious"],
                        source="vieneu-sdk",
                        commercial_safe="internal_review_required",
                    )
                )

        self._voices = voices
        return voices

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Render text segment to WAV via VieNeu SDK."""
        if not _VIENEU_AVAILABLE or self._tts is None:
            # Auto-preload on first use
            if _VIENEU_AVAILABLE and not self._loaded:
                async with self._loading_lock:
                    if not self._loaded:
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, self.preload)
            if self._tts is None:
                return SynthesisResult(
                    ok=False,
                    error_code="ENGINE_UNAVAILABLE",
                    error_message="VieNeu engine chưa sẵn sàng.",
                )

        # Resolve voice slug → SDK display name
        voice_slug = request.voice_id.split(":", 1)[1] if ":" in request.voice_id else request.voice_id
        sdk_voice_name = _SLUG_TO_SDK.get(voice_slug, voice_slug)

        # Calculate effective speed
        mode_speed = MODE_MAP.get(request.mode, {}).get("speed_mult", 1.0)
        emotion_speed = EMOTION_MAP.get(request.emotion, {}).get("speed_mult", 1.0)
        effective_speed = request.speed * mode_speed * emotion_speed

        # Output path
        wav_filename = f"segment_{request.segment_index:04d}.wav"
        wav_path = os.path.join(request.output_dir, wav_filename)

        try:
            start = time.time()

            # Run in executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            async with self._synth_lock:
                audio = await loop.run_in_executor(
                    None,
                    lambda: self._tts.infer(
                        text=request.text,
                        voice=sdk_voice_name,
                    ),
                )

                # Save WAV
                await loop.run_in_executor(
                    None,
                    lambda: self._tts.save(audio, wav_path),
                )

                await loop.run_in_executor(
                    None,
                    lambda: change_audio_speed(wav_path, effective_speed),
                )

            elapsed = time.time() - start

            # Estimate duration (rough: 1 char ≈ 0.1s for Vietnamese)
            est_duration = len(request.text) * 0.08

            return SynthesisResult(
                ok=True,
                wav_path=wav_path,
                duration_sec=est_duration,
                rtf=elapsed / est_duration if est_duration > 0 else None,
                metrics={"inference_time": elapsed},
            )

        except Exception as e:
            logger.error("VieNeu synthesis failed: %s", e)
            return SynthesisResult(
                ok=False,
                error_code="WORKER_CRASHED",
                error_message=f"VieNeu inference error: {str(e)}",
            )


def _slugify(text: str) -> str:
    """Convert a display name to a slug."""
    import re
    import unicodedata

    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", text)
