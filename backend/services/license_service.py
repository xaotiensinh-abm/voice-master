"""License service — state machine, activation, enforcement gate.

See docs/licensing-packaging-spec.md §5-6. Reads config attributes dynamically
(config.LICENSE_ENFORCED / config.LICENSE_PATH) so tests can monkeypatch them.
"""

from __future__ import annotations

import json
from typing import Any

import config
from services import trial
from services.license_core import verify_key
from services.machine_id import get_machine_code


def _load() -> dict[str, Any]:
    path = config.LICENSE_PATH
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: dict[str, Any]) -> None:
    config.NEO_VOICE_HOME.mkdir(parents=True, exist_ok=True)
    config.LICENSE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _eval_license(store: dict, machine_code: str) -> dict:
    """Evaluate the stored license key (if any)."""
    key = store.get("license_key")
    if not key:
        return {"present": False, "valid": False, "reason": None, "exp": None, "tier": None}
    res = verify_key(key, machine_code)
    payload = res.get("payload") or {}
    return {
        "present": True,
        "valid": res["ok"],
        "reason": res.get("reason"),
        "exp": payload.get("exp"),
        "tier": payload.get("tier"),
    }


def get_status() -> dict[str, Any]:
    machine_code = get_machine_code()
    enforced = bool(config.LICENSE_ENFORCED)

    store = _load()
    tstat = trial.status(store)  # mutates store (ensures trial start)
    _save(store)  # persist trial init

    lic = _eval_license(store, machine_code)

    if not enforced:
        state = "dev"
    elif lic["valid"]:
        state = "licensed"
    elif tstat["active"]:
        state = "trial"
    elif lic["present"]:
        state = "invalid"
    else:
        state = "expired"

    return {
        "state": state,
        "enforced": enforced,
        "days_left": tstat["days_left"] if state in ("trial", "dev") else None,
        "machine_code": machine_code,
        "exp": lic["exp"] if lic["valid"] else None,
        "tier": lic["tier"] if lic["valid"] else None,
        "reason": lic["reason"] if state == "invalid" else None,
    }


def is_allowed() -> bool:
    """Whether voice creation is permitted right now."""
    if not config.LICENSE_ENFORCED:
        return True
    machine_code = get_machine_code()
    store = _load()
    if _eval_license(store, machine_code)["valid"]:
        return True
    tstat = trial.status(store)
    _save(store)
    return tstat["active"]


def activate(key: str) -> dict[str, Any]:
    """Verify and store a license key. Returns {ok, ...}."""
    machine_code = get_machine_code()
    res = verify_key(key or "", machine_code)
    if not res["ok"]:
        return {"ok": False, "reason": res.get("reason", "bad_format")}
    store = _load()
    store["license_key"] = key.strip()
    _save(store)
    payload = res.get("payload") or {}
    return {"ok": True, "state": "licensed", "exp": payload.get("exp"), "tier": payload.get("tier")}
