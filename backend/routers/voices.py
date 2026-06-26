"""NEO Voice Backend — Voices endpoints."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from adapters.base import get_adapter, get_engine_statuses
from models.schemas import (
    PreviewRequest,
    PreviewResponse,
    SynthesisRequest,
    VoiceListResponse,
    make_error,
)
from services.voice_registry import list_voices

router = APIRouter(prefix="/v1", tags=["voices"])


@router.get("/voices", response_model=VoiceListResponse)
async def get_voices(
    engine: str | None = Query(None, description="Filter by engine: vieneu|elevenlabs"),
    style: str | None = Query(None, description="Filter by style: news|story|podcast|neutral"),
    available_only: bool = Query(False, description="Only show available/enabled voices"),
) -> VoiceListResponse:
    """List voices with optional filters.
    
    Spec §05: GET /v1/voices
    """
    voices = await list_voices(
        engine=engine,
        style=style,
        available_only=available_only,
    )
    engine_statuses = get_engine_statuses()
    for voice in voices:
        status = engine_statuses.get(voice.engine)
        engine_ready = status is None or status.status not in (
            "unavailable",
            "error",
            "not_configured",
        )
        voice.available = bool(voice.enabled and engine_ready)

    if available_only:
        voices = [voice for voice in voices if voice.available]

    return VoiceListResponse(voices=voices)


@router.post("/voices/preview", response_model=PreviewResponse)
async def preview_voice(request: PreviewRequest) -> PreviewResponse:
    """Generate a short voice preview.
    
    Spec §05: POST /v1/voices/preview
    """
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail=make_error("TEXT_EMPTY").model_dump(),
        )

    # Resolve engine
    try:
        adapter = get_adapter(request.voice_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=make_error("UNKNOWN_VOICE").model_dump(),
        )

    # Check engine health
    health = adapter.health()
    if health.status in ("unavailable", "error", "not_configured"):
        raise HTTPException(
            status_code=503,
            detail=make_error("ENGINE_UNAVAILABLE").model_dump(),
        )

    preview_id = f"preview_{uuid.uuid4().hex[:12]}"

    # Quick synthesis for preview
    from config import TEMP_DIR
    import os

    preview_dir = os.path.join(str(TEMP_DIR), "previews", preview_id)
    os.makedirs(preview_dir, exist_ok=True)

    synth_req = SynthesisRequest(
        job_id=preview_id,
        voice_id=request.voice_id,
        text=request.text,
        output_dir=preview_dir,
        segment_index=0,
    )

    try:
        result = await adapter.synthesize(synth_req)
        if not result.ok:
            raise HTTPException(
                status_code=500,
                detail=make_error(
                    result.error_code or "WORKER_CRASHED",
                    result.error_message,
                ).model_dump(),
            )
    except NotImplementedError:
        # Engine not yet connected — return placeholder
        pass

    return PreviewResponse(
        preview_id=preview_id,
        audio_url=f"/v1/previews/{preview_id}/audio",
    )


@router.get("/previews/{preview_id}/audio")
async def get_preview_audio(preview_id: str):
    """Serve generated preview audio."""
    from config import TEMP_DIR
    import os
    
    # Path where preview was saved. Local engines produce WAV; ElevenLabs produces MP3.
    preview_dir = os.path.join(str(TEMP_DIR), "previews", preview_id)
    candidates = [
        (os.path.join(preview_dir, "segment_0000.mp3"), "audio/mpeg"),
        (os.path.join(preview_dir, "segment_0000.wav"), "audio/wav"),
    ]
    audio_path = None
    media_type = "application/octet-stream"
    for candidate, candidate_type in candidates:
        if os.path.exists(candidate):
            audio_path = candidate
            media_type = candidate_type
            break

    if not audio_path:
        raise HTTPException(
            status_code=404,
            detail=make_error("NOT_FOUND", "Preview audio not found").model_dump(),
        )
        
    return FileResponse(audio_path, media_type=media_type)
