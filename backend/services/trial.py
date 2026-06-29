"""Trial tracking (default 7 days). See docs/licensing-packaging-spec.md §4.

State lives in the license.json "trial" object (managed by license_service) plus a
best-effort Windows registry marker so deleting the file alone does not reset the
trial. Earliest known start wins. The trial record carries an HMAC to detect manual edits.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
from datetime import datetime, timedelta, timezone

from config import APP_HMAC_SECRET, TRIAL_DAYS

_REG_PATH = r"Software\Voice-Master"
_REG_VALUE = "t"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(iso: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(iso)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _hmac(first_run_iso: str, days: int) -> str:
    msg = f"{first_run_iso}|{days}".encode("utf-8")
    return hmac.new(APP_HMAC_SECRET, msg, hashlib.sha256).hexdigest()


def _valid(trial: dict | None) -> bool:
    if not isinstance(trial, dict):
        return False
    fr, days, mac = trial.get("first_run"), trial.get("days"), trial.get("hmac")
    if not fr or days is None or not mac:
        return False
    return hmac.compare_digest(_hmac(fr, int(days)), str(mac))


# ───────────────────── registry marker (best-effort) ──────────────


def _reg_read() -> str | None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ) as k:
            val, _ = winreg.QueryValueEx(k, _REG_VALUE)
            return base64.b32decode(val).decode("utf-8")
    except Exception:
        return None


def _reg_write(first_run_iso: str) -> None:
    try:
        import winreg

        enc = base64.b32encode(first_run_iso.encode("utf-8")).decode("ascii")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as k:
            winreg.SetValueEx(k, _REG_VALUE, 0, winreg.REG_SZ, enc)
    except Exception:
        pass


# ───────────────────── public API ─────────────────────────────────


def ensure_started(store: dict) -> dict:
    """Ensure a trial start exists in `store` (mutates it). Returns the trial dict.

    Uses the earliest of: a valid file record and the registry marker; if neither
    exists, starts the trial now. Persists back to both the store and the registry.
    """
    candidates: list[datetime] = []

    t = store.get("trial")
    if _valid(t):
        dt = _parse(t["first_run"])
        if dt:
            candidates.append(dt)

    reg = _reg_read()
    if reg:
        dt = _parse(reg)
        if dt:
            candidates.append(dt)

    start = min(candidates) if candidates else _now()
    iso = start.isoformat()

    store["trial"] = {"first_run": iso, "days": TRIAL_DAYS, "hmac": _hmac(iso, TRIAL_DAYS)}
    _reg_write(iso)
    return store["trial"]


def status(store: dict) -> dict:
    """Return {first_run, days, days_left, active} from the store's trial record."""
    t = ensure_started(store)
    start = _parse(t["first_run"]) or _now()
    end = start + timedelta(days=int(t["days"]))
    remaining = (end - _now()).total_seconds()
    days_left = max(0, math.ceil(remaining / 86400)) if remaining > 0 else 0
    return {
        "first_run": t["first_run"],
        "days": int(t["days"]),
        "days_left": days_left,
        "active": remaining > 0,
    }
