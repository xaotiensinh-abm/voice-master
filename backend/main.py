"""Voice-Master Backend — FastAPI entry point.

Starts the backend server on 127.0.0.1:8757 (configurable via NEO_VOICE_PORT).
Initializes DB, registers engine adapters, starts job worker.
"""

from __future__ import annotations

import json
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from config import HOST, NEO_VOICE_HOME, PORT, PRELOAD_ENGINES, RUNTIME_JSON, VERSION
from database import close_db, init_db
from utils.security import RedactingFilter
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.requests import Request
from starlette.responses import Response
from mcp_server import mcp

# Modern MCP transport (Streamable HTTP) — most agents default to this. Stateless
# + json_response keeps each tool call a simple request/response over HTTP.
_mcp_session_manager = StreamableHTTPSessionManager(app=mcp, stateless=True, json_response=True)


def _configure_stdio_encoding() -> None:
    """Keep Windows redirected logs from crashing on third-party Unicode messages."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_stdio_encoding()

# ───────────────────── Logging setup ──────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Add redacting filter to root logger
root_logger = logging.getLogger()
root_logger.addFilter(RedactingFilter())

logger = logging.getLogger("voice_master")


# ───────────────────── Lifespan ───────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # ── Startup ──
    logger.info("Voice-Master Backend %s starting...", VERSION)
    
    # Ensure directories
    config.ensure_dirs()

    # Initialize database
    await init_db()
    logger.info("Database initialized at %s", config.DB_PATH)

    # Register engine adapters
    _register_adapters()

    # Keep startup fast by default; engines lazy-load on first synthesis.
    _preload_configured_adapters()

    # Remove legacy OmniVoice records so stale DB data cannot reappear in UI.
    try:
        await _purge_legacy_omnivoice_data()
    except Exception as e:
        logger.warning("Legacy OmniVoice cleanup failed: %s", e)

    # Register VieNeu voices (fallback if SDK not installed), then remove stale
    # VieNeu records that no longer map to the active SDK/fallback inventory.
    try:
        valid_vieneu_voice_ids = await _register_vieneu_fallback_voices()
        await _purge_stale_vieneu_voices(valid_vieneu_voice_ids)
    except Exception as e:
        logger.warning("VieNeu voice registration failed: %s", e)

    # Start job worker
    from services.job_queue import start_worker
    await start_worker()

    # Write runtime.json for Electron
    _write_runtime_json()

    logger.info("Voice-Master Backend ready on http://%s:%d", HOST, PORT)

    # Run the Streamable HTTP session manager for the lifetime of the app.
    async with _mcp_session_manager.run():
        yield

    # ── Shutdown ──
    logger.info("Voice-Master Backend shutting down...")
    
    # Unload engines
    from adapters.base import get_all_adapters
    for prefix, adapter in get_all_adapters().items():
        try:
            adapter.unload()
        except Exception:
            pass

    # Close database
    await close_db()
    
    # Clean up runtime.json
    try:
        RUNTIME_JSON.unlink(missing_ok=True)
    except Exception:
        pass

    logger.info("Shutdown complete.")


# ───────────────────── App creation ───────────────────────────────

app = FastAPI(
    title="Voice-Master Local TTS",
    version=VERSION,
    description="Local TTS backend for Voice-Master - supports VieNeu and ElevenLabs.",
    lifespan=lifespan,
)

# ───────────────────── CORS ───────────────────────────────────────
# Only allow localhost origins (Electron + dev)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8757",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8757",
        "app://.",  # Electron custom protocol
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───────────────────── Routers ────────────────────────────────────

from routers.health import router as health_router
from routers.voices import router as voices_router
from routers.tts import router as tts_router
from routers.settings import router as settings_router
from routers.diagnostics import router as diagnostics_router
from routers.history import router as history_router
from routers.models import router as models_router
from routers.license import router as license_router

app.include_router(health_router)
app.include_router(voices_router)
app.include_router(tts_router)
app.include_router(settings_router)
app.include_router(diagnostics_router)
app.include_router(history_router)
app.include_router(models_router)
app.include_router(license_router)

# ───────────────────── MCP Server ──────────────────────────────────
# Primary (modern) transport: Streamable HTTP at POST/GET /mcp — recommended for
# agents. Mounted AFTER the explicit /mcp/sse + /mcp/messages routes so those
# legacy SSE paths still match first.

async def _handle_mcp_http(scope, receive, send) -> None:
    await _mcp_session_manager.handle_request(scope, receive, send)


# Legacy SSE transport (kept for older clients): GET /mcp/sse + POST /mcp/messages
sse = SseServerTransport("/mcp/messages")

@app.get("/mcp/sse")
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp.run(streams[0], streams[1], mcp.create_initialization_options())
    return Response()

@app.post("/mcp/messages")
async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

# Streamable HTTP endpoint (prefix mount; matched after the explicit routes above).
app.mount("/mcp", app=_handle_mcp_http)

# ───────────────────── Helpers ────────────────────────────────────

def _register_adapters() -> None:
    """Instantiate and register all engine adapters."""
    from adapters.base import register_adapter
    from adapters.vieneu_adapter import VieneuAdapter
    from adapters.elevenlabs_adapter import ElevenLabsAdapter

    register_adapter("vieneu", VieneuAdapter())
    register_adapter("elevenlabs", ElevenLabsAdapter())

    logger.info("Engine adapters registered: vieneu, elevenlabs")


def _preload_configured_adapters() -> None:
    """Preload only engines explicitly requested via NEO_VOICE_PRELOAD_ENGINES."""
    if not PRELOAD_ENGINES:
        logger.info(
            "Engine preload disabled; adapters will lazy-load on first synthesis. "
            "Set NEO_VOICE_PRELOAD_ENGINES=vieneu to warm up at startup."
        )
        return

    import os

    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

    from adapters.base import get_all_adapters

    requested = set(PRELOAD_ENGINES)
    adapters = get_all_adapters()

    for prefix in requested:
        adapter = adapters.get(prefix)
        if adapter is None:
            logger.warning("Configured preload engine is not registered: %s", prefix)
            continue
        try:
            adapter.preload()
            logger.info("Preloaded adapter %s", prefix)
        except Exception as e:
            logger.error("Failed to preload %s: %s", prefix, e)


async def _register_vieneu_fallback_voices() -> set[str]:
    """Register VieNeu voices from the adapter while preserving user enabled flags."""
    from adapters.base import get_adapter
    from services.voice_registry import upsert_voice

    adapter = get_adapter("vieneu:default")
    voices = adapter.list_voices()
    valid_voice_ids = {voice.voice_id for voice in voices}

    for voice in voices:
        slug = voice.voice_id.split(":", 1)[1] if ":" in voice.voice_id else voice.voice_id
        await upsert_voice(
            voice_id=voice.voice_id,
            display_name=voice.display_name,
            engine="vieneu",
            language=voice.language,
            gender=voice.gender,
            region=voice.region,
            styles=voice.styles,
            emotions=voice.emotions,
            source=voice.source,
            license=voice.license,
            commercial_safe="internal_review_required",
            engine_params={"sdk_voice": voice.display_name, "slug": slug},
        )
    logger.info("Registered/updated %d VieNeu voices", len(voices))
    return valid_voice_ids


async def _purge_stale_vieneu_voices(valid_voice_ids: set[str]) -> None:
    """Remove legacy VieNeu voice rows that are not renderable by the adapter."""
    if not valid_voice_ids:
        return

    from database import get_db

    db = await get_db()
    placeholders = ",".join("?" for _ in valid_voice_ids)
    params = tuple(sorted(valid_voice_ids))

    await db.execute(
        f"""
        DELETE FROM voice_engine_params
        WHERE voice_id LIKE 'vieneu:%'
          AND voice_id NOT IN ({placeholders})
        """,
        params,
    )
    cursor = await db.execute(
        f"""
        DELETE FROM voices
        WHERE engine = 'vieneu'
          AND voice_id NOT IN ({placeholders})
        """,
        params,
    )
    await db.commit()

    if cursor.rowcount:
        logger.info("Removed %d stale VieNeu voices", cursor.rowcount)


async def _purge_legacy_omnivoice_data() -> None:
    """Remove OmniVoice voices/jobs left over from older builds."""
    from database import get_db

    db = await get_db()
    await db.execute(
        """
        DELETE FROM voice_engine_params
        WHERE voice_id IN (
            SELECT voice_id FROM voices
            WHERE engine = 'omnivoice' OR voice_id LIKE 'omni:%'
        )
        OR voice_id LIKE 'omni:%'
        """
    )
    voices_cursor = await db.execute(
        "DELETE FROM voices WHERE engine = 'omnivoice' OR voice_id LIKE 'omni:%'"
    )
    jobs_cursor = await db.execute(
        "DELETE FROM jobs WHERE engine IN ('omni', 'omnivoice') OR voice_id LIKE 'omni:%'"
    )
    await db.commit()
    if voices_cursor.rowcount or jobs_cursor.rowcount:
        logger.info(
            "Removed legacy OmniVoice data: %d voices, %d jobs",
            voices_cursor.rowcount,
            jobs_cursor.rowcount,
        )


def _write_runtime_json() -> None:
    """Write runtime.json for Electron to discover backend port."""
    try:
        NEO_VOICE_HOME.mkdir(parents=True, exist_ok=True)
        runtime_data = {
            "port": PORT,
            "host": HOST,
            "version": VERSION,
            "pid": __import__("os").getpid(),
        }
        with open(RUNTIME_JSON, "w", encoding="utf-8") as f:
            json.dump(runtime_data, f, indent=2)
        logger.info("runtime.json written to %s", RUNTIME_JSON)
    except Exception as e:
        logger.warning("Failed to write runtime.json: %s", e)


# ───────────────────── Main ───────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=HOST,  # NEVER 0.0.0.0
        port=PORT,
        reload=False,
        log_level="info",
    )
