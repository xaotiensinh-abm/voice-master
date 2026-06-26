"""NEO Voice Backend — Voice Registry service (CRUD for voices table)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from database import get_db
from models.schemas import VoiceInfo

logger = logging.getLogger(__name__)

# Valid engine prefixes
VALID_PREFIXES = {"vieneu", "elevenlabs"}


def validate_voice_id(voice_id: str) -> bool:
    """Validate voice_id has a known engine prefix."""
    if ":" not in voice_id:
        return False
    prefix = voice_id.split(":", 1)[0]
    return prefix in VALID_PREFIXES


async def upsert_voice(
    voice_id: str,
    display_name: str,
    engine: str,
    language: str = "vi",
    gender: str | None = None,
    region: str | None = None,
    styles: list[str] | None = None,
    emotions: list[str] | None = None,
    source: str | None = None,
    license: str | None = None,
    commercial_safe: str = "internal_review_required",
    local_path: str | None = None,
    preview_path: str | None = None,
    engine_params: dict | None = None,
) -> None:
    """Insert or update a voice record. Preserves user-set enabled flag on update."""
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    styles_json = json.dumps(styles or [])
    emotions_json = json.dumps(emotions or [])

    # Check if exists
    cursor = await db.execute("SELECT voice_id, enabled FROM voices WHERE voice_id = ?", (voice_id,))
    existing = await cursor.fetchone()

    if existing:
        # Preserve enabled flag
        await db.execute(
            """UPDATE voices
               SET display_name = ?, engine = ?, language = ?,
                   gender = ?, region = ?, styles_json = ?, emotions_json = ?,
                   source = ?, license = ?, commercial_safe = ?,
                   local_path = ?, preview_path = ?, updated_at = ?
               WHERE voice_id = ?""",
            (
                display_name, engine, language,
                gender, region, styles_json, emotions_json,
                source, license, commercial_safe,
                local_path, preview_path, now,
                voice_id,
            ),
        )
    else:
        await db.execute(
            """INSERT INTO voices
               (voice_id, display_name, engine, language, gender, region,
                styles_json, emotions_json, source, license, commercial_safe,
                local_path, preview_path, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                voice_id, display_name, engine, language, gender, region,
                styles_json, emotions_json, source, license, commercial_safe,
                local_path, preview_path, now, now,
            ),
        )

    # Upsert engine params
    if engine_params:
        params_json = json.dumps(engine_params)
        await db.execute(
            """INSERT INTO voice_engine_params (voice_id, params_json)
               VALUES (?, ?)
               ON CONFLICT(voice_id) DO UPDATE SET params_json = excluded.params_json""",
            (voice_id, params_json),
        )

    await db.commit()
    logger.info("Upserted voice: %s", voice_id)


async def get_voice(voice_id: str) -> VoiceInfo | None:
    """Get a single voice by ID."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM voices WHERE voice_id = ?", (voice_id,))
    row = await cursor.fetchone()
    if not row:
        return None
    return _row_to_voice_info(row)


async def list_voices(
    engine: str | None = None,
    style: str | None = None,
    available_only: bool = False,
) -> list[VoiceInfo]:
    """List voices with optional filters."""
    db = await get_db()
    query = "SELECT * FROM voices WHERE 1=1"
    params: list = []

    if available_only:
        query += " AND enabled = 1"

    if engine:
        query += " AND engine = ?"
        params.append(engine)

    query += " ORDER BY engine, display_name"

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    voices = [_row_to_voice_info(row) for row in rows]

    # Filter by style in-memory (styles are stored as JSON array)
    if style:
        voices = [v for v in voices if style in v.styles]

    return voices


async def delete_voice(voice_id: str) -> bool:
    """Delete a voice record."""
    db = await get_db()
    await db.execute("DELETE FROM voice_engine_params WHERE voice_id = ?", (voice_id,))
    cursor = await db.execute("DELETE FROM voices WHERE voice_id = ?", (voice_id,))
    await db.commit()
    return cursor.rowcount > 0


async def set_voice_enabled(voice_id: str, enabled: bool) -> bool:
    """Enable or disable a voice."""
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    cursor = await db.execute(
        "UPDATE voices SET enabled = ?, updated_at = ? WHERE voice_id = ?",
        (1 if enabled else 0, now, voice_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_engine_params(voice_id: str) -> dict | None:
    """Get engine-specific params for a voice."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT params_json FROM voice_engine_params WHERE voice_id = ?",
        (voice_id,),
    )
    row = await cursor.fetchone()
    if row:
        return json.loads(row["params_json"])
    return None


async def count_voices(engine: str | None = None) -> int:
    """Count total voices, optionally filtered by engine."""
    db = await get_db()
    if engine:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM voices WHERE engine = ?", (engine,)
        )
    else:
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM voices")
    row = await cursor.fetchone()
    return row["cnt"] if row else 0


def _row_to_voice_info(row) -> VoiceInfo:
    """Convert a database row to VoiceInfo schema."""
    styles = json.loads(row["styles_json"]) if row["styles_json"] else []
    emotions = json.loads(row["emotions_json"]) if row["emotions_json"] else []
    return VoiceInfo(
        voice_id=row["voice_id"],
        display_name=row["display_name"],
        engine=row["engine"],
        language=row["language"],
        gender=row["gender"],
        region=row["region"],
        styles=styles,
        emotions=emotions,
        source=row["source"],
        license=row["license"],
        commercial_safe=row["commercial_safe"],
        local_path=row["local_path"],
        preview_path=row["preview_path"],
        quality_score=row["quality_score"],
        enabled=bool(row["enabled"]),
        available=bool(row["enabled"]),
    )
