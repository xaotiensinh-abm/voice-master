"""Voice-Master Backend — MCP Server for agent-driven TTS loops.

Exposes the full agent loop over MCP (same process as the FastAPI app, mounted
at /mcp/sse): list voices → ensure model ready → synthesize a script → wait for
completion → download the audio → repeat.

Design (see docs/agent-api-plan.md):
- Every tool returns ONE JSON string in TextContent (`_ok`/`_err`).
- In-process calls to routers.tts.* catch HTTPException and map to JSON errors
  so exceptions never propagate out of MCP.
- Scope is localhost / same-machine agent: download_job_audio prefers copying to
  dest_path; base64 is opt-in.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
from typing import Any

from fastapi import HTTPException
from mcp.server import Server
from mcp.types import Tool, TextContent

from config import HOST, PORT
from database import get_db
from models.schemas import ERROR_MESSAGES, JobCreateRequest, JobInput, JobOutput
from routers.tts import cancel_job_endpoint, create_job
from services import model_manager

# Initialize MCP Server
mcp = Server("voice-master")

_TERMINAL = {"completed", "failed", "cancelled", "canceled"}
_MAX_BASE64_BYTES = 25 * 1024 * 1024  # 25 MB cap for opt-in base64


# ───────────────────── Response helpers ───────────────────────────


def _ok(data: dict[str, Any]) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False))]


def _err(code: str, message: str | None = None) -> list[TextContent]:
    return _ok({"error_code": code, "message": message or ERROR_MESSAGES.get(code, code)})


def _audio_url(job_id: str) -> str:
    return f"http://{HOST}:{PORT}/v1/tts/jobs/{job_id}/audio"


def _http_error_to_json(exc: HTTPException) -> list[TextContent]:
    """Map an HTTPException raised by routers.tts.* into a JSON error."""
    detail = exc.detail
    if isinstance(detail, dict):
        return _err(detail.get("error_code", "WORKER_CRASHED"), detail.get("message") or detail.get("detail"))
    return _err("WORKER_CRASHED", str(detail))


async def _job_row(job_id: str):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    return await cursor.fetchone()


def _job_status_payload(job: Any) -> dict[str, Any]:
    """Build the structured status dict shared by get_job_status / wait_for_job."""
    status = job["status"]
    error = None
    if job["error_code"]:
        error = {"code": job["error_code"], "message": job["error_message"] or ""}
    return {
        "job_id": job["job_id"],
        "status": status,
        "progress": job["progress"] or 0,
        "segments_done": job["segments_done"] or 0,
        "segments_total": job["segments_total"] or 0,
        "output_path": job["output_path"],
        "audio_url": _audio_url(job["job_id"]) if status == "completed" else None,
        "error": error,
    }


# ───────────────────── Tool catalog ───────────────────────────────


@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_voices",
            description="List all available voices (id, display name, engine, styles, emotions).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_model_status",
            description="Get the VieNeu model download status (downloaded, size, percent, state).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ensure_model_ready",
            description=(
                "Ensure the VieNeu model is downloaded. Starts the download if missing. "
                "Returns immediately by default (poll get_model_status); set wait=true to block."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "wait": {"type": "boolean", "description": "Block until done/error. Default false."},
                    "timeout_sec": {"type": "integer", "description": "Max seconds to wait when wait=true. Default 600."},
                },
            },
        ),
        Tool(
            name="synthesize",
            description=(
                "Create a TTS job from a script. Returns {job_id,status}. Long text is "
                "auto-split and merged. Use wait_for_job then download_job_audio."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The script text to synthesize."},
                    "voice_id": {"type": "string", "description": "Voice id, e.g. 'vieneu:ngoc_lan' (see list_voices)."},
                    "mode": {"type": "string", "description": "Reading style: neutral|news|story|podcast. Default neutral."},
                    "emotion": {"type": "string", "description": "neutral|warm|serious|storytelling|excited|sad. Default neutral."},
                    "speed": {"type": "number", "description": "0.5–2.0. Default 1.0."},
                },
                "required": ["text", "voice_id"],
            },
        ),
        Tool(
            name="get_job_status",
            description="Get a job's status, progress, segments, and audio_url (when completed).",
            inputSchema={
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        ),
        Tool(
            name="wait_for_job",
            description="Poll a job until it finishes (completed/failed/cancelled) or times out.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "timeout_sec": {"type": "integer", "description": "Default 300."},
                    "poll_sec": {"type": "number", "description": "Default 2."},
                },
                "required": ["job_id"],
            },
        ),
        Tool(
            name="download_job_audio",
            description=(
                "Get the finished MP3 for a completed job. With dest_path: copies the file there "
                "and returns saved_path. Without: returns filename + audio_url (+ base64 if include_base64)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "dest_path": {"type": "string", "description": "Absolute path (file or directory) to copy the MP3 to."},
                    "include_base64": {"type": "boolean", "description": "Return base64 audio (cap 25MB). Default false."},
                },
                "required": ["job_id"],
            },
        ),
        Tool(
            name="get_history",
            description="List recently completed TTS jobs.",
            inputSchema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Default 10."}},
            },
        ),
        Tool(
            name="cancel_job",
            description="Cancel a queued or running job.",
            inputSchema={
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        ),
    ]


# ───────────────────── Tool dispatch ──────────────────────────────


@mcp.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    args = arguments or {}
    try:
        if name == "list_voices":
            return await _list_voices()
        if name == "get_model_status":
            return await _get_model_status()
        if name == "ensure_model_ready":
            return await _ensure_model_ready(args)
        if name == "synthesize":
            return await _synthesize(args)
        if name == "get_job_status":
            return await _get_job_status(args)
        if name == "wait_for_job":
            return await _wait_for_job(args)
        if name == "download_job_audio":
            return await _download_job_audio(args)
        if name == "get_history":
            return await _get_history(args)
        if name == "cancel_job":
            return await _cancel_job(args)
    except HTTPException as e:
        return _http_error_to_json(e)
    except Exception as e:  # never let an exception break the MCP stream
        return _err("WORKER_CRASHED", str(e))

    return _err("UNKNOWN_TOOL", f"Unknown tool: {name}")


async def _list_voices() -> list[TextContent]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT voice_id, display_name, engine, styles_json, emotions_json FROM voices WHERE enabled = 1"
    )
    rows = await cursor.fetchall()
    voices = []
    for r in rows:
        voices.append({
            "voice_id": r["voice_id"],
            "display_name": r["display_name"],
            "engine": r["engine"],
            "available": True,
            "styles": _loads(r["styles_json"]),
            "emotions": _loads(r["emotions_json"]),
        })
    return _ok({"voices": voices})


async def _get_model_status() -> list[TextContent]:
    status = await asyncio.to_thread(model_manager.get_status)
    prog = await asyncio.to_thread(model_manager.get_progress)
    status["percent"] = prog["percent"]
    return _ok(status)


async def _ensure_model_ready(args: dict[str, Any]) -> list[TextContent]:
    wait = bool(args.get("wait", False))
    timeout = int(args.get("timeout_sec", 600))

    await asyncio.to_thread(model_manager.start_download)

    if wait:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        prog = await asyncio.to_thread(model_manager.get_progress)
        while prog["state"] == "downloading" and loop.time() < deadline:
            await asyncio.sleep(2)
            prog = await asyncio.to_thread(model_manager.get_progress)

    status = await asyncio.to_thread(model_manager.get_status)
    prog = await asyncio.to_thread(model_manager.get_progress)
    return _ok({
        "downloaded": status["downloaded"],
        "state": status["state"],
        "percent": prog["percent"],
        "error": status.get("error"),
    })


async def _synthesize(args: dict[str, Any]) -> list[TextContent]:
    text = args.get("text")
    voice_id = args.get("voice_id")
    if not text or not text.strip():
        return _err("TEXT_EMPTY")
    if not voice_id:
        return _err("UNKNOWN_VOICE", "Thiếu voice_id.")

    # Pre-check VieNeu model so the agent gets a clear, actionable error instead
    # of a long hang on the first (auto-downloading) synthesis.
    if voice_id.startswith("vieneu:"):
        downloaded = await asyncio.to_thread(model_manager.is_downloaded)
        if not downloaded:
            return _err("MODEL_NOT_READY", "Model VieNeu chưa tải. Gọi ensure_model_ready trước.")

    try:
        req = JobCreateRequest(
            input=JobInput(type="text", text=text),
            voice_id=voice_id,
            mode=args.get("mode", "neutral"),
            emotion=args.get("emotion", "neutral"),
            speed=float(args.get("speed", 1.0)),
            output=JobOutput(format="mp3"),
        )
    except Exception as e:  # pydantic validation (bad mode/emotion/speed)
        return _err("INVALID_REQUEST", str(e))

    job = await create_job(req)  # may raise HTTPException → mapped in call_tool
    return _ok({"job_id": job.job_id, "status": job.status})


async def _get_job_status(args: dict[str, Any]) -> list[TextContent]:
    job_id = args.get("job_id")
    if not job_id:
        return _err("JOB_NOT_FOUND", "Thiếu job_id.")
    job = await _job_row(job_id)
    if not job:
        return _err("JOB_NOT_FOUND")
    return _ok(_job_status_payload(job))


async def _wait_for_job(args: dict[str, Any]) -> list[TextContent]:
    job_id = args.get("job_id")
    if not job_id:
        return _err("JOB_NOT_FOUND", "Thiếu job_id.")
    timeout = float(args.get("timeout_sec", 300))
    poll = max(0.5, float(args.get("poll_sec", 2)))

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    last: dict[str, Any] | None = None
    while True:
        job = await _job_row(job_id)
        if not job:
            return _err("JOB_NOT_FOUND")
        last = _job_status_payload(job)
        if last["status"] in _TERMINAL:
            return _ok(last)
        if loop.time() >= deadline:
            return _ok({"error_code": "TIMEOUT", "message": "Hết thời gian chờ job.",
                        "job_id": job_id, "status": last["status"], "progress": last["progress"]})
        await asyncio.sleep(poll)


async def _download_job_audio(args: dict[str, Any]) -> list[TextContent]:
    job_id = args.get("job_id")
    if not job_id:
        return _err("JOB_NOT_FOUND", "Thiếu job_id.")
    job = await _job_row(job_id)
    if not job:
        return _err("JOB_NOT_FOUND")
    if job["status"] != "completed":
        return _err("JOB_NOT_COMPLETED", f"Job chưa hoàn thành (status={job['status']}).")
    output_path = job["output_path"]
    if not output_path or not os.path.exists(output_path):
        return _err("MP3_EXPORT_FAILED", "Không tìm thấy file audio đầu ra.")

    filename = os.path.basename(output_path)
    size = os.path.getsize(output_path)
    voice_id = job["voice_id"]

    dest_path = args.get("dest_path")
    if dest_path:
        if not os.path.isabs(dest_path):
            return _err("INVALID_DEST_PATH", "dest_path phải là đường dẫn tuyệt đối.")
        # Directory → save under it with the original filename.
        if os.path.isdir(dest_path):
            dest = os.path.join(dest_path, filename)
        else:
            parent = os.path.dirname(dest_path) or "."
            if not os.path.isdir(parent):
                try:
                    os.makedirs(parent, exist_ok=True)
                except OSError as e:
                    return _err("INVALID_DEST_PATH", f"Không tạo được thư mục đích: {e}")
            dest = dest_path
        await asyncio.to_thread(shutil.copy2, output_path, dest)
        return _ok({"saved_path": dest, "bytes": size, "voice_id": voice_id, "filename": filename})

    payload: dict[str, Any] = {
        "filename": filename,
        "audio_url": _audio_url(job_id),
        "bytes": size,
        "voice_id": voice_id,
    }
    if bool(args.get("include_base64", False)):
        if size > _MAX_BASE64_BYTES:
            return _err("AUDIO_TOO_LARGE",
                        f"File {size} bytes > 25MB; dùng dest_path hoặc audio_url để tải.")
        data = await asyncio.to_thread(_read_bytes, output_path)
        payload["base64"] = base64.b64encode(data).decode("ascii")
    return _ok(payload)


async def _get_history(args: dict[str, Any]) -> list[TextContent]:
    limit = int(args.get("limit", 10))
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT j.job_id, j.voice_id, v.display_name, j.input_text, j.output_path, j.created_at
        FROM jobs j
        LEFT JOIN voices v ON j.voice_id = v.voice_id
        WHERE j.status = 'completed' AND j.input_text IS NOT NULL
        ORDER BY j.created_at DESC LIMIT ?
        """,
        (limit,),
    )
    rows = await cursor.fetchall()
    items = []
    for r in rows:
        text = r["input_text"] or ""
        items.append({
            "job_id": r["job_id"],
            "voice_id": r["voice_id"],
            "display_name": r["display_name"],
            "text_preview": text[:80] + ("..." if len(text) > 80 else ""),
            "output_path": r["output_path"],
            "audio_url": _audio_url(r["job_id"]),
            "created_at": r["created_at"],
        })
    return _ok({"items": items})


async def _cancel_job(args: dict[str, Any]) -> list[TextContent]:
    job_id = args.get("job_id")
    if not job_id:
        return _err("JOB_NOT_FOUND", "Thiếu job_id.")
    result = await cancel_job_endpoint(job_id)  # may raise HTTPException → mapped
    return _ok(result)


# ───────────────────── small utils ────────────────────────────────


def _loads(raw: Any) -> list:
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except (ValueError, TypeError):
        return []


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()
