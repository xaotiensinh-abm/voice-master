"""NEO Voice Backend — Async job queue with sequential local execution."""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from config import EXPORT_DIR, TEMP_DIR
from database import get_db
from models.schemas import SynthesisRequest, SynthesisResult, make_error
from services.text_pipeline import preprocess, read_input_file
from utils.audio import (
    export_encoded_audio_segments,
    export_mp3,
    generate_output_filename,
    join_wav_segments,
    normalize_loudness,
)

if TYPE_CHECKING:
    from adapters.base import TTSEngineAdapter

logger = logging.getLogger(__name__)

# ───────────────────── Job Queue ──────────────────────────────────

_local_lock = asyncio.Lock()  # Sequential execution for local models
_queue: asyncio.Queue[str] = asyncio.Queue()
_running = False
_cancel_flags: dict[str, bool] = {}

PREFIX_TO_ENGINE = {
    "vieneu": "vieneu",
    "elevenlabs": "elevenlabs",
}


def canonical_engine_name(voice_id: str) -> str:
    """Return the public engine name for a voice id."""
    prefix = voice_id.split(":", 1)[0] if ":" in voice_id else "unknown"
    return PREFIX_TO_ENGINE.get(prefix, prefix)


def engine_prefix(voice_id: str) -> str:
    """Return the adapter prefix for a voice id."""
    return voice_id.split(":", 1)[0] if ":" in voice_id else "unknown"


async def start_worker() -> None:
    """Start the background job worker."""
    global _running
    if _running:
        return
    _running = True
    asyncio.create_task(_worker_loop())
    logger.info("Job worker started")


async def _worker_loop() -> None:
    """Main worker loop processing jobs from the queue."""
    while _running:
        try:
            job_id = await asyncio.wait_for(_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        except Exception:
            continue

        try:
            await _process_job(job_id)
        except Exception as e:
            logger.error("Job %s crashed: %s\n%s", job_id, e, traceback.format_exc())
            await _update_job_status(
                job_id, "failed",
                error_code="WORKER_CRASHED",
                error_message=str(e),
            )
        finally:
            _queue.task_done()


async def enqueue_job(job_id: str) -> None:
    """Add a job to the processing queue."""
    await _queue.put(job_id)
    logger.info("Job %s enqueued", job_id)


def cancel_job(job_id: str) -> None:
    """Signal cancellation for a job."""
    _cancel_flags[job_id] = True


async def _process_job(job_id: str) -> None:
    """Process a single TTS job end-to-end."""
    from adapters.base import get_adapter  # avoid circular

    db = await get_db()
    cursor = await db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    job = await cursor.fetchone()
    if not job:
        logger.error("Job %s not found", job_id)
        return

    voice_id = job["voice_id"]
    prefix = engine_prefix(voice_id)
    engine_name = canonical_engine_name(voice_id)

    if job["status"] == "cancelled":
        _cancel_flags.pop(job_id, None)
        logger.info("Job %s was cancelled before processing", job_id)
        return

    # Update status to running
    await _update_job_status(job_id, "running", engine=engine_name)

    # Get the text content
    if job["input_type"] == "file":
        text, err = read_input_file(job["input_path"])
        if err:
            await _update_job_status(job_id, "failed", error_code=err)
            return
    else:
        text = job["input_text"] or ""

    if not text.strip():
        await _update_job_status(job_id, "failed", error_code="TEXT_EMPTY")
        return

    # Resolve engine
    try:
        adapter = get_adapter(voice_id)
    except KeyError:
        await _update_job_status(job_id, "failed", error_code="UNKNOWN_VOICE")
        return

    # Check engine health
    health = adapter.health()
    logger.info(
        "Job %s engine health check: engine=%s, status=%s, loaded=%s, error=%s, gpu_required=%s",
        job_id, engine_name, health.status, health.loaded, health.error, health.gpu_required,
    )
    if health.status in ("unavailable", "error", "not_configured"):
        logger.error(
            "Job %s ENGINE_UNAVAILABLE: adapter=%s, health.status=%s, health.error=%s",
            job_id, type(adapter).__name__, health.status, health.error,
        )
        await _update_job_status(job_id, "failed", error_code="ENGINE_UNAVAILABLE")
        return

    # Determine if it's markdown
    is_md = False
    if job["input_type"] == "file" and job["input_path"]:
        is_md = job["input_path"].lower().endswith(".md")

    # Chunk text
    chunks = preprocess(text, engine=engine_name, is_markdown=is_md)

    if not chunks:
        await _update_job_status(job_id, "failed", error_code="TEXT_EMPTY")
        return

    # Update segments count
    await _update_job_status(job_id, "running", segments_total=len(chunks))

    # Create temp dir for this job
    job_temp = Path(TEMP_DIR) / job_id
    job_temp.mkdir(parents=True, exist_ok=True)

    # Determine which lock to use
    use_lock = prefix == "vieneu"
    wav_paths: list[str] = []

    mode = job["mode"] or "neutral"
    emotion = job["emotion"] or "neutral"
    speed = job["speed"] or 1.0

    for i, chunk in enumerate(chunks):
        # Check cancellation
        if _cancel_flags.pop(job_id, False):
            await _update_job_status(job_id, "cancelled")
            return

        req = SynthesisRequest(
            job_id=job_id,
            voice_id=voice_id,
            text=chunk,
            mode=mode,
            emotion=emotion,
            speed=speed,
            output_dir=str(job_temp),
            segment_index=i,
        )

        try:
            if use_lock:
                async with _local_lock:
                    result = await adapter.synthesize(req)
            else:
                result = await adapter.synthesize(req)
        except Exception as e:
            logger.error("Segment %d failed for job %s: %s", i, job_id, e)
            await _update_job_status(
                job_id, "failed",
                error_code="WORKER_CRASHED",
                error_message=f"Segment {i}: {str(e)}",
                segments_done=len(wav_paths),
            )
            return

        if not result.ok:
            await _update_job_status(
                job_id, "failed",
                error_code=result.error_code or "WORKER_CRASHED",
                error_message=result.error_message,
                segments_done=len(wav_paths),
            )
            return

        if result.wav_path:
            wav_paths.append(result.wav_path)

        # Update progress
        progress = (i + 1) / len(chunks)
        await _update_job_status(
            job_id, "running",
            progress=progress,
            segments_done=i + 1,
        )

    # Export segments
    if not wav_paths:
        await _update_job_status(job_id, "failed", error_code="WORKER_CRASHED",
                                 error_message="No audio segments produced.")
        return

    try:
        # Determine output path
        output_format = job["output_format"] or "mp3"
        source_name = "text_input"
        if job["input_type"] == "file" and job["input_path"]:
            source_name = Path(job["input_path"]).stem

        voice_slug = voice_id.split(":", 1)[1] if ":" in voice_id else voice_id
        filename = generate_output_filename(source_name, voice_slug, output_format)

        # Use export dir with date subfolder
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        export_folder = Path(EXPORT_DIR) / today
        export_folder.mkdir(parents=True, exist_ok=True)
        output_path = str(export_folder / filename)

        bitrate = 128
        loop = asyncio.get_running_loop()
        if prefix == "elevenlabs":
            await loop.run_in_executor(
                None,
                lambda: export_encoded_audio_segments(
                    wav_paths,
                    output_path,
                    output_format=output_format,
                    bitrate_kbps=bitrate,
                ),
            )
        else:
            joined_wav = str(job_temp / "joined.wav")
            await loop.run_in_executor(
                None,
                lambda: _export_local_audio(
                    wav_paths,
                    joined_wav,
                    output_path,
                    output_format,
                    bitrate,
                ),
            )

        # Validate output
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            await _update_job_status(job_id, "failed", error_code="MP3_EXPORT_FAILED")
            return

        await _update_job_status(
            job_id, "completed",
            progress=1.0,
            output_path=output_path,
            segments_done=len(chunks),
        )
        logger.info("Job %s completed: %s", job_id, output_path)

    except Exception as e:
        logger.error("Post-processing failed for job %s: %s", job_id, e)
        await _update_job_status(
            job_id, "failed",
            error_code="MP3_EXPORT_FAILED",
            error_message=str(e),
        )


# ───────────────────── DB helpers ─────────────────────────────────


def _export_local_audio(
    wav_paths: list[str],
    joined_wav: str,
    output_path: str,
    output_format: str,
    bitrate_kbps: int,
) -> None:
    """Join local WAV segments, normalize, and export to the requested format."""
    join_wav_segments(wav_paths, joined_wav)
    normalize_loudness(joined_wav)

    if output_format == "mp3":
        export_mp3(joined_wav, output_path, bitrate_kbps=bitrate_kbps)
    else:
        import shutil

        shutil.copy2(joined_wav, output_path)


async def _update_job_status(
    job_id: str,
    status: str,
    *,
    engine: str | None = None,
    progress: float | None = None,
    segments_total: int | None = None,
    segments_done: int | None = None,
    output_path: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update job record in database."""
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    updates = ["status = ?", "updated_at = ?"]
    params: list = [status, now]

    if engine is not None:
        updates.append("engine = ?")
        params.append(engine)
    if progress is not None:
        updates.append("progress = ?")
        params.append(progress)
    if segments_total is not None:
        updates.append("segments_total = ?")
        params.append(segments_total)
    if segments_done is not None:
        updates.append("segments_done = ?")
        params.append(segments_done)
    if output_path is not None:
        updates.append("output_path = ?")
        params.append(output_path)
    if error_code is not None:
        updates.append("error_code = ?")
        params.append(error_code)
    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)
    if status == "completed":
        updates.append("completed_at = ?")
        params.append(now)

    params.append(job_id)
    sql = f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?"
    await db.execute(sql, params)
    await db.commit()
