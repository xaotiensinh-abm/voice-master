"""NEO Voice Backend — SQLite database layer."""

from __future__ import annotations

import aiosqlite

from config import DB_PATH, NEO_VOICE_HOME

_db: aiosqlite.Connection | None = None

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS voices (
    voice_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    engine TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'vi',
    gender TEXT,
    region TEXT,
    styles_json TEXT NOT NULL DEFAULT '[]',
    emotions_json TEXT NOT NULL DEFAULT '[]',
    source TEXT,
    license TEXT,
    commercial_safe TEXT NOT NULL DEFAULT 'internal_review_required',
    local_path TEXT,
    preview_path TEXT,
    quality_score REAL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voice_engine_params (
    voice_id TEXT PRIMARY KEY,
    params_json TEXT NOT NULL,
    FOREIGN KEY (voice_id) REFERENCES voices(voice_id)
);

CREATE TABLE IF NOT EXISTS voice_quality_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_id TEXT NOT NULL,
    text_id TEXT NOT NULL,
    rating INTEGER NOT NULL,
    notes TEXT,
    reviewer TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',
    voice_id TEXT NOT NULL,
    engine TEXT,
    input_type TEXT NOT NULL,
    input_text TEXT,
    input_path TEXT,
    mode TEXT DEFAULT 'neutral',
    emotion TEXT DEFAULT 'neutral',
    speed REAL DEFAULT 1.0,
    output_format TEXT DEFAULT 'mp3',
    output_path TEXT,
    progress REAL DEFAULT 0,
    segments_total INTEGER DEFAULT 0,
    segments_done INTEGER DEFAULT 0,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


async def init_db() -> aiosqlite.Connection:
    """Initialise the database and run idempotent migrations."""
    global _db
    NEO_VOICE_HOME.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(str(DB_PATH))
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA_SQL)
    await _db.commit()
    return _db


async def get_db() -> aiosqlite.Connection:
    """Return the current DB connection, initialising if needed."""
    global _db
    if _db is None:
        return await init_db()
    return _db


async def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
