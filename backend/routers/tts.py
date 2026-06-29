"""NEO Voice Backend — TTS job endpoints + OpenAI/ElevenLabs compat."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from adapters.base import get_adapter
from config import HOST, PORT, TEMP_DIR
from database import get_db
from models.schemas import (
    ElevenLabsSpeechRequest,
    JobCreateRequest,
    JobResponse,
    JobStatusResponse,
    OpenAISpeechRequest,
    SynthesisRequest,
    make_error,
)
from services.job_queue import cancel_job, canonical_engine_name, enqueue_job

router = APIRouter(prefix="/v1", tags=["tts"])


def _generate_job_id() -> str:
    """Generate a unique job ID: job_YYYYMMDD_XXXX."""
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%d")
    unique = uuid.uuid4().hex[:8]
    return f"job_{date_part}_{unique}"


# ───────────────────── Job CRUD ───────────────────────────────────


@router.post("/tts/jobs", response_model=JobResponse, status_code=201)
async def create_job(request: JobCreateRequest) -> JobResponse:
    """Create an async TTS render job.
    
    Spec §05: POST /v1/tts/jobs
    """
    # License gate (single chokepoint for REST + MCP). No-op when enforcement is
    # off (dev/demo). See docs/licensing-packaging-spec.md §5.
    from services import license_service

    if not license_service.is_allowed():
        status = license_service.get_status()
        raise HTTPException(
            status_code=402,
            detail=make_error("LICENSE_REQUIRED").model_dump()
            | {"machine_code": status["machine_code"], "days_left": status["days_left"] or 0},
        )

    # Validate voice
    try:
        adapter = get_adapter(request.voice_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=make_error("UNKNOWN_VOICE").model_dump(),
        )

    # Validate input
    if request.input.type == "text":
        if not request.input.text or not request.input.text.strip():
            raise HTTPException(
                status_code=400,
                detail=make_error("TEXT_EMPTY").model_dump(),
            )
        input_text = request.input.text
        input_path = None
    elif request.input.type == "file":
        if not request.input.path:
            raise HTTPException(
                status_code=400,
                detail=make_error("FILE_READ_ERROR").model_dump(),
            )
        # Validate file extension
        ext = os.path.splitext(request.input.path)[1].lower()
        if ext not in (".txt", ".md"):
            raise HTTPException(
                status_code=400,
                detail=make_error("FILE_UNSUPPORTED").model_dump(),
            )
        if not os.path.exists(request.input.path):
            raise HTTPException(
                status_code=400,
                detail=make_error("FILE_READ_ERROR").model_dump(),
            )
        input_text = None
        input_path = request.input.path
    else:
        raise HTTPException(status_code=400, detail="Unsupported input type")

    health = adapter.health()
    if health.status in ("unavailable", "error", "not_configured"):
        raise HTTPException(
            status_code=503,
            detail=make_error("ENGINE_UNAVAILABLE", health.error).model_dump(),
        )

    # Create job record
    job_id = _generate_job_id()
    now = datetime.now(timezone.utc).isoformat()
    engine_name = canonical_engine_name(request.voice_id)

    db = await get_db()
    await db.execute(
        """INSERT INTO jobs
           (job_id, status, voice_id, engine, input_type, input_text, input_path,
            mode, emotion, speed, output_format, created_at, updated_at)
           VALUES (?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job_id,
            request.voice_id,
            engine_name,
            request.input.type,
            input_text,
            input_path,
            request.mode,
            request.emotion,
            request.speed,
            request.output.format,
            now,
            now,
        ),
    )
    await db.commit()

    # Enqueue for processing
    await enqueue_job(job_id)

    return JobResponse(job_id=job_id, status="queued")


@router.get("/tts/jobs")
async def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
) -> dict:
    """List recent TTS jobs for history and polling recovery."""
    db = await get_db()
    where = []
    params: list = []

    if status:
        where.append("j.status = ?")
        params.append(status)

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    params.extend([limit, offset])
    cursor = await db.execute(
        f"""
        SELECT j.*, v.display_name AS voice_name
        FROM jobs j
        LEFT JOIN voices v ON j.voice_id = v.voice_id
        {where_sql}
        ORDER BY j.created_at DESC
        LIMIT ? OFFSET ?
        """,
        params,
    )
    rows = await cursor.fetchall()

    jobs = []
    for row in rows:
        item = dict(row)
        input_text = item.get("input_text")
        input_path = item.get("input_path")
        if input_text:
            preview = input_text[:120] + ("..." if len(input_text) > 120 else "")
        elif input_path:
            preview = Path(input_path).name
        else:
            preview = None
        item["input_preview"] = preview
        item["duration_seconds"] = None
        jobs.append(item)

    return {"jobs": jobs}


@router.get("/tts/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get job status.
    
    Spec §05: GET /v1/tts/jobs/{job_id}
    """
    db = await get_db()
    cursor = await db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    job = await cursor.fetchone()

    if not job:
        raise HTTPException(
            status_code=404,
            detail=make_error("JOB_NOT_FOUND").model_dump(),
        )

    error = None
    if job["error_code"]:
        error = {
            "code": job["error_code"],
            "message": job["error_message"] or "",
        }

    # Determine stage
    stage = None
    if job["status"] == "running":
        if job["segments_done"] and job["segments_done"] > 0:
            stage = "rendering_segment"
        else:
            stage = "preprocessing"

    audio_url = (
        f"http://{HOST}:{PORT}/v1/tts/jobs/{job['job_id']}/audio"
        if job["status"] == "completed"
        else None
    )

    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"] or 0,
        stage=stage,
        voice_id=job["voice_id"],
        engine=job["engine"],
        segments_total=job["segments_total"] or 0,
        segments_done=job["segments_done"] or 0,
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        completed_at=job["completed_at"],
        output_path=job["output_path"],
        audio_url=audio_url,
        error=error,
    )


@router.post("/tts/jobs/{job_id}/cancel")
async def cancel_job_endpoint(job_id: str) -> dict:
    """Cancel a running job.
    
    Spec §05: POST /v1/tts/jobs/{job_id}/cancel
    """
    db = await get_db()
    cursor = await db.execute("SELECT status FROM jobs WHERE job_id = ?", (job_id,))
    job = await cursor.fetchone()

    if not job:
        raise HTTPException(
            status_code=404,
            detail=make_error("JOB_NOT_FOUND").model_dump(),
        )

    if job["status"] not in ("queued", "running"):
        return {"status": "already_" + job["status"]}

    cancel_job(job_id)

    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE jobs SET status = 'cancelled', updated_at = ? WHERE job_id = ?",
        (now, job_id),
    )
    await db.commit()

    return {"status": "cancelled"}


@router.delete("/tts/jobs/{job_id}")
async def delete_job_endpoint(job_id: str) -> dict:
    """Delete a job from local history.

    Output files are left untouched so users do not lose exported audio by
    clearing a history row.
    """
    db = await get_db()
    cursor = await db.execute("SELECT status FROM jobs WHERE job_id = ?", (job_id,))
    job = await cursor.fetchone()

    if not job:
        raise HTTPException(
            status_code=404,
            detail=make_error("JOB_NOT_FOUND").model_dump(),
        )

    if job["status"] in ("queued", "running"):
        cancel_job(job_id)

    cursor = await db.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
    await db.commit()

    return {"status": "deleted", "deleted": cursor.rowcount}


@router.post("/tts/jobs/{job_id}/retry")
async def retry_job(job_id: str) -> JobResponse:
    """Retry a failed job from last failed segment.
    
    Spec §05: POST /v1/tts/jobs/{job_id}/retry
    """
    db = await get_db()
    cursor = await db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    job = await cursor.fetchone()

    if not job:
        raise HTTPException(
            status_code=404,
            detail=make_error("JOB_NOT_FOUND").model_dump(),
        )

    if job["status"] != "failed":
        raise HTTPException(
            status_code=400,
            detail={"error": "Chỉ có thể retry job đã thất bại."},
        )

    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """UPDATE jobs SET status = 'queued', error_code = NULL, error_message = NULL,
           progress = 0, updated_at = ? WHERE job_id = ?""",
        (now, job_id),
    )
    await db.commit()

    await enqueue_job(job_id)

    return JobResponse(job_id=job_id, status="queued")


@router.get("/tts/jobs/{job_id}/audio")
async def get_job_audio(job_id: str) -> FileResponse:
    """Return final MP3 for a completed job.
    
    Spec §05: GET /v1/tts/jobs/{job_id}/audio
    """
    db = await get_db()
    cursor = await db.execute(
        "SELECT status, output_path FROM jobs WHERE job_id = ?", (job_id,)
    )
    job = await cursor.fetchone()

    if not job:
        raise HTTPException(
            status_code=404,
            detail=make_error("JOB_NOT_FOUND").model_dump(),
        )

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail={"error": "Job chưa hoàn thành."},
        )

    if not job["output_path"] or not os.path.exists(job["output_path"]):
        raise HTTPException(
            status_code=404,
            detail=make_error("MP3_EXPORT_FAILED").model_dump(),
        )

    return FileResponse(
        path=job["output_path"],
        media_type="audio/mpeg",
        filename=os.path.basename(job["output_path"]),
    )


# ──────────── OpenAI-compatible endpoint ──────────────────────────


@router.post("/audio/speech")
async def openai_speech(request: OpenAISpeechRequest) -> FileResponse:
    """OpenAI-compatible speech endpoint.
    
    Spec §05: POST /v1/audio/speech
    Returns audio bytes directly.
    """
    if not request.input or not request.input.strip():
        raise HTTPException(
            status_code=400,
            detail=make_error("TEXT_EMPTY").model_dump(),
        )

    voice_id = request.voice
    try:
        adapter = get_adapter(voice_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=make_error("UNKNOWN_VOICE").model_dump(),
        )

    health = adapter.health()
    if health.status in ("unavailable", "error", "not_configured"):
        raise HTTPException(
            status_code=503,
            detail=make_error("ENGINE_UNAVAILABLE").model_dump(),
        )

    # Quick synchronous render
    temp_dir = str(Path(TEMP_DIR) / f"openai_{uuid.uuid4().hex[:8]}")
    os.makedirs(temp_dir, exist_ok=True)

    synth_req = SynthesisRequest(
        job_id=f"openai_{uuid.uuid4().hex[:8]}",
        voice_id=voice_id,
        text=request.input,
        speed=request.speed,
        output_dir=temp_dir,
    )

    result = await adapter.synthesize(synth_req)

    if not result.ok:
        raise HTTPException(
            status_code=500,
            detail=make_error(
                result.error_code or "WORKER_CRASHED",
                result.error_message,
            ).model_dump(),
        )

    if not result.wav_path or not os.path.exists(result.wav_path):
        raise HTTPException(
            status_code=500,
            detail=make_error("MP3_EXPORT_FAILED").model_dump(),
        )

    # Convert to MP3 if needed
    if result.wav_path.endswith(".wav") and request.response_format == "mp3":
        from utils.audio import export_mp3

        mp3_path = result.wav_path.replace(".wav", ".mp3")
        await asyncio.to_thread(export_mp3, result.wav_path, mp3_path)
        return FileResponse(mp3_path, media_type="audio/mpeg")

    return FileResponse(result.wav_path, media_type="audio/mpeg")


# ──────────── ElevenLabs-compatible endpoint ──────────────────────


@router.post("/text-to-speech/{voice_id}")
async def elevenlabs_compat(voice_id: str, request: ElevenLabsSpeechRequest) -> FileResponse:
    """ElevenLabs-compatible local endpoint.
    
    Spec §05: POST /v1/text-to-speech/{voice_id}
    Routes to local or ElevenLabs voices depending on prefix.
    """
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail=make_error("TEXT_EMPTY").model_dump(),
        )

    # Determine full voice_id if prefix is missing
    full_voice_id = voice_id
    if ":" not in voice_id:
        # Default to elevenlabs prefix
        full_voice_id = f"elevenlabs:{voice_id}"

    try:
        adapter = get_adapter(full_voice_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=make_error("UNKNOWN_VOICE").model_dump(),
        )

    health = adapter.health()
    if health.status in ("unavailable", "error", "not_configured"):
        raise HTTPException(
            status_code=503,
            detail=make_error("ENGINE_UNAVAILABLE").model_dump(),
        )

    temp_dir = str(Path(TEMP_DIR) / f"el_{uuid.uuid4().hex[:8]}")
    os.makedirs(temp_dir, exist_ok=True)

    synth_req = SynthesisRequest(
        job_id=f"el_{uuid.uuid4().hex[:8]}",
        voice_id=full_voice_id,
        text=request.text,
        output_dir=temp_dir,
        engine_params={
            "stability": request.voice_settings.stability,
            "similarity_boost": request.voice_settings.similarity_boost,
            "model_id": request.model_id,
        },
    )

    result = await adapter.synthesize(synth_req)

    if not result.ok:
        raise HTTPException(
            status_code=500,
            detail=make_error(
                result.error_code or "WORKER_CRASHED",
                result.error_message,
            ).model_dump(),
        )

    if not result.wav_path or not os.path.exists(result.wav_path):
        raise HTTPException(
            status_code=500,
            detail=make_error("MP3_EXPORT_FAILED").model_dump(),
        )

    # Convert to MP3 if WAV
    if result.wav_path.endswith(".wav"):
        from utils.audio import export_mp3

        mp3_path = result.wav_path.replace(".wav", ".mp3")
        await asyncio.to_thread(export_mp3, result.wav_path, mp3_path)
        return FileResponse(mp3_path, media_type="audio/mpeg")

    return FileResponse(result.wav_path, media_type="audio/mpeg")
