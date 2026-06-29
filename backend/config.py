"""NEO Voice Backend — Configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_APPDATA = os.environ.get("APPDATA", str(Path.home()))

old_neo_home = Path(os.path.join(_APPDATA, "NEO Voice"))
new_vm_home = Path(os.path.join(_APPDATA, "Voice-Master"))

# Auto-migrate folder if upgrading from NEO Voice
if old_neo_home.exists() and not new_vm_home.exists():
    try:
        old_neo_home.rename(new_vm_home)
    except Exception:
        pass

# Fallback to env var if explicitly set, otherwise use Voice-Master
NEO_VOICE_HOME = Path(
    os.environ.get("NEO_VOICE_HOME", str(new_vm_home))
)

DB_PATH = NEO_VOICE_HOME / "voice_master.db"
# Auto-migrate db file name if it exists as old name
old_db = NEO_VOICE_HOME / "neo_voice.db"
if old_db.exists() and not DB_PATH.exists():
    try:
        old_db.rename(DB_PATH)
    except Exception:
        pass
LOG_DIR = NEO_VOICE_HOME / "logs"
MODEL_DIR = NEO_VOICE_HOME / "models"
EXPORT_DIR = NEO_VOICE_HOME / "exports"
TEMP_DIR = NEO_VOICE_HOME / "temp"
CONFIG_JSON = NEO_VOICE_HOME / "config.json"
RUNTIME_JSON = NEO_VOICE_HOME / "runtime.json"

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = int(os.environ.get("NEO_VOICE_PORT", "8757"))
VERSION = "1.0.0-mvp"

# ---------------------------------------------------------------------------
# Engine defaults
# ---------------------------------------------------------------------------
PRELOAD_ENGINES = tuple(
    engine.strip().lower()
    for engine in os.environ.get("NEO_VOICE_PRELOAD_ENGINES", "").split(",")
    if engine.strip()
)
GPU_DETECT_TTL_SEC = float(os.environ.get("NEO_VOICE_GPU_DETECT_TTL_SEC", "2"))

# ---------------------------------------------------------------------------
# Text pipeline defaults
# ---------------------------------------------------------------------------
MAX_CHARS_PER_CHUNK = {
    "vieneu": 900,
    "elevenlabs": 2000,
}

# ---------------------------------------------------------------------------
# Audio export defaults
# ---------------------------------------------------------------------------
DEFAULT_BITRATE_KBPS = 128
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_SILENCE_MS = 400  # ms silence between joined segments

# ---------------------------------------------------------------------------
# ElevenLabs defaults
# ---------------------------------------------------------------------------
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io"
ELEVENLABS_DEFAULT_MODEL = "eleven_multilingual_v2"

# ---------------------------------------------------------------------------
# Licensing (see docs/licensing-packaging-spec.md)
# ---------------------------------------------------------------------------
# Enforcement is OFF by default (dev/source = demo). The packaged .exe sets
# VOICE_MASTER_LICENSE_ENFORCED=1 when spawning the backend.
LICENSE_ENFORCED = os.environ.get("VOICE_MASTER_LICENSE_ENFORCED", "").strip().lower() in (
    "1", "true", "yes", "on",
)
# Fixed salt — DO NOT change after release (would change every machine_code).
APP_SALT = os.environ.get("VOICE_MASTER_SALT", "voice-master-machine-salt-v1")
# Best-effort tamper-evidence for the local trial record (symmetric; see spec §10).
APP_HMAC_SECRET = os.environ.get("VOICE_MASTER_HMAC", "voice-master-trial-hmac-v1").encode("utf-8")
TRIAL_DAYS = int(os.environ.get("VOICE_MASTER_TRIAL_DAYS", "7"))
LICENSE_PATH = NEO_VOICE_HOME / "license.json"

# ---------------------------------------------------------------------------
# Load user overrides from config.json
# ---------------------------------------------------------------------------
_user_config: dict[str, Any] = {}


def _load_config_json() -> dict[str, Any]:
    """Load config.json if it exists."""
    global _user_config
    if CONFIG_JSON.exists():
        try:
            with open(CONFIG_JSON, "r", encoding="utf-8") as f:
                _user_config = json.load(f)
        except Exception:
            _user_config = {}
    return _user_config


def get(key: str, default: Any = None) -> Any:
    """Get a config value from env → config.json → default."""
    env_val = os.environ.get(f"NEO_VOICE_{key.upper()}")
    if env_val is not None:
        return env_val
    if not _user_config:
        _load_config_json()
    return _user_config.get(key, default)


def save_config(updates: dict[str, Any]) -> None:
    """Merge updates into config.json and persist."""
    if not _user_config:
        _load_config_json()
    _user_config.update(updates)
    NEO_VOICE_HOME.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_JSON, "w", encoding="utf-8") as f:
        json.dump(_user_config, f, indent=2, ensure_ascii=False)


def ensure_dirs() -> None:
    """Create required directories."""
    for d in (NEO_VOICE_HOME, LOG_DIR, MODEL_DIR, EXPORT_DIR, TEMP_DIR):
        d.mkdir(parents=True, exist_ok=True)
