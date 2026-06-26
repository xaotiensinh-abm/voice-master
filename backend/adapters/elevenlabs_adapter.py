"""NEO Voice Backend — ElevenLabs cloud TTS Adapter.

Handles API key storage, voice listing, and cloud TTS rendering.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

from adapters.base import EngineHealth, TTSEngineAdapter
from config import ELEVENLABS_BASE_URL, ELEVENLABS_DEFAULT_MODEL
from models.schemas import SynthesisRequest, SynthesisResult, VoiceInfo
from utils.security import get_api_key, redact_api_key_display

logger = logging.getLogger(__name__)


class ElevenLabsAdapter(TTSEngineAdapter):
    """ElevenLabs cloud TTS adapter."""

    engine_id = "elevenlabs"

    def __init__(self) -> None:
        self._configured = False
        self._voices: list[VoiceInfo] = []
        self._check_configuration()

    def _check_configuration(self) -> None:
        """Check if API key is configured."""
        key = get_api_key()
        self._configured = key is not None and len(key) > 0

    def health(self) -> EngineHealth:
        """Return config status. Does not hit API."""
        self._check_configuration()
        if self._configured:
            return EngineHealth(status="ready", loaded=True)
        return EngineHealth(status="not_configured", loaded=False)

    def preload(self) -> None:
        """No preload needed for cloud API."""
        self._check_configuration()

    def unload(self) -> None:
        """Nothing to unload."""
        self._voices.clear()

    def list_voices(self) -> list[VoiceInfo]:
        """Return cached voices. Use fetch_voices() to refresh from API."""
        return self._voices

    async def fetch_voices(self) -> list[VoiceInfo]:
        """Fetch available voices from ElevenLabs API."""
        key = get_api_key()
        if not key:
            return []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{ELEVENLABS_BASE_URL}/v1/voices",
                    headers={"xi-api-key": key},
                )

            if resp.status_code == 401 or resp.status_code == 403:
                logger.error("ElevenLabs auth failed (status %d)", resp.status_code)
                return []

            if resp.status_code != 200:
                logger.warning("ElevenLabs voices fetch failed: %d", resp.status_code)
                return []

            data = resp.json()
            voices = []
            for v in data.get("voices", []):
                voice_id = v.get("voice_id", "")
                voices.append(
                    VoiceInfo(
                        voice_id=f"elevenlabs:{voice_id}",
                        display_name=v.get("name", f"ElevenLabs - {voice_id[:8]}..."),
                        engine="elevenlabs",
                        language="vi",
                        source="ElevenLabs API",
                        license="provider_terms_apply",
                        commercial_safe="provider_terms_apply",
                    )
                )

            self._voices = voices
            logger.info("Fetched %d voices from ElevenLabs", len(voices))
            return voices

        except httpx.TimeoutException:
            logger.error("ElevenLabs API timeout")
            return []
        except Exception as e:
            logger.error("ElevenLabs voice fetch error: %s", e)
            return []

    async def test_connection(self) -> tuple[bool, str | None]:
        """Test ElevenLabs API connection. Returns (ok, error_code)."""
        key = get_api_key()
        if not key:
            return False, "ELEVENLABS_AUTH_FAILED"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{ELEVENLABS_BASE_URL}/v1/user",
                    headers={"xi-api-key": key},
                )

            if resp.status_code in (401, 403):
                return False, "ELEVENLABS_AUTH_FAILED"
            if resp.status_code == 429:
                return False, "ELEVENLABS_RATE_LIMIT"
            if resp.status_code == 200:
                return True, None
            return False, "ELEVENLABS_NETWORK"

        except httpx.TimeoutException:
            return False, "ELEVENLABS_NETWORK"
        except Exception as e:
            logger.error("ElevenLabs connection test failed: %s", e)
            return False, "ELEVENLABS_NETWORK"

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Render text to MP3 via ElevenLabs API."""
        key = get_api_key()
        if not key:
            return SynthesisResult(
                ok=False,
                error_code="ELEVENLABS_AUTH_FAILED",
                error_message="ElevenLabs API key chưa cấu hình.",
            )

        # Extract ElevenLabs voice_id from our prefixed format
        el_voice_id = request.voice_id.split(":", 1)[1] if ":" in request.voice_id else request.voice_id

        # Build request payload (from spec §06 and §10)
        model_id = request.engine_params.get("model_id", ELEVENLABS_DEFAULT_MODEL)
        stability = request.engine_params.get("stability", 0.5)
        similarity = request.engine_params.get("similarity_boost", 0.75)

        payload = {
            "text": request.text,
            "model_id": model_id,
            "language_code": "vi",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{ELEVENLABS_BASE_URL}/v1/text-to-speech/{el_voice_id}",
                    json=payload,
                    headers={
                        "xi-api-key": key,
                        "Content-Type": "application/json",
                        "Accept": "audio/mpeg",
                    },
                    params={"output_format": "mp3_44100_128"},
                )

            # Handle errors
            if resp.status_code in (401, 403):
                return SynthesisResult(
                    ok=False,
                    error_code="ELEVENLABS_AUTH_FAILED",
                    error_message="API key không hợp lệ hoặc không có quyền.",
                )

            if resp.status_code == 429:
                return SynthesisResult(
                    ok=False,
                    error_code="ELEVENLABS_RATE_LIMIT",
                    error_message="Bị giới hạn tốc độ. Hãy thử lại sau.",
                )

            if resp.status_code == 422:
                # Check for quota
                try:
                    err_data = resp.json()
                    detail = err_data.get("detail", {})
                    if "quota" in str(detail).lower() or "billing" in str(detail).lower():
                        return SynthesisResult(
                            ok=False,
                            error_code="ELEVENLABS_QUOTA",
                            error_message="Tài khoản hết quota hoặc cần kiểm tra billing.",
                        )
                except Exception:
                    pass

            if resp.status_code == 404:
                return SynthesisResult(
                    ok=False,
                    error_code="ELEVENLABS_VOICE_NOT_FOUND",
                    error_message="Voice ID không tồn tại.",
                )

            if resp.status_code != 200:
                return SynthesisResult(
                    ok=False,
                    error_code="WORKER_CRASHED",
                    error_message=f"ElevenLabs API error: HTTP {resp.status_code}",
                )

            # Save MP3 (ElevenLabs returns audio/mpeg directly)
            mp3_filename = f"segment_{request.segment_index:04d}.mp3"
            mp3_path = os.path.join(request.output_dir, mp3_filename)

            with open(mp3_path, "wb") as f:
                f.write(resp.content)

            if os.path.getsize(mp3_path) < 100:
                return SynthesisResult(
                    ok=False,
                    error_code="WORKER_CRASHED",
                    error_message="ElevenLabs trả về audio rỗng.",
                )

            return SynthesisResult(
                ok=True,
                wav_path=mp3_path,  # MP3 directly, handled in job queue
                duration_sec=None,
                sample_rate=44100,
            )

        except httpx.TimeoutException:
            return SynthesisResult(
                ok=False,
                error_code="ELEVENLABS_NETWORK",
                error_message="Timeout khi kết nối ElevenLabs.",
            )
        except Exception as e:
            logger.error("ElevenLabs synthesis error: %s", e)
            return SynthesisResult(
                ok=False,
                error_code="ELEVENLABS_NETWORK",
                error_message=f"Lỗi kết nối: {str(e)}",
            )
