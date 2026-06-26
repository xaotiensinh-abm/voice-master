"""NEO Voice Backend — Security utilities: keyring, log redaction."""

from __future__ import annotations

import logging
import re

_SERVICE_NAME = "neo-voice-local"
_KEYRING_KEY = "elevenlabs_api_key"


# ───────────────────── Keyring helpers ────────────────────────────


def store_api_key(key: str) -> bool:
    """Encrypt and store API key via Windows DPAPI / keyring."""
    try:
        import keyring

        keyring.set_password(_SERVICE_NAME, _KEYRING_KEY, key)
        return True
    except Exception:
        return False


def get_api_key() -> str | None:
    """Retrieve stored API key, or None."""
    try:
        import keyring

        return keyring.get_password(_SERVICE_NAME, _KEYRING_KEY)
    except Exception:
        return None


def delete_api_key() -> bool:
    """Delete stored API key."""
    try:
        import keyring

        keyring.delete_password(_SERVICE_NAME, _KEYRING_KEY)
        return True
    except Exception:
        return False


# ───────────────────── Redaction ──────────────────────────────────

_API_KEY_PATTERN = re.compile(r"(sk[-_])[A-Za-z0-9_-]{6,}", re.IGNORECASE)
_BEARER_PATTERN = re.compile(r"(Bearer\s+)\S+", re.IGNORECASE)


def redact_string(value: str) -> str:
    """Redact API keys from a string."""
    value = _API_KEY_PATTERN.sub(r"\g<1>***REDACTED***", value)
    value = _BEARER_PATTERN.sub(r"\g<1>***REDACTED***", value)
    return value


def redact_api_key_display(key: str | None) -> str | None:
    """Return a masked version of the key for display, e.g. sk_...abc."""
    if not key:
        return None
    if len(key) <= 8:
        return "***"
    return f"{key[:3]}...{key[-3:]}"


class RedactingFilter(logging.Filter):
    """Logging filter that redacts API keys from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_string(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_string(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_string(str(a)) if isinstance(a, str) else a for a in record.args
                )
        return True
