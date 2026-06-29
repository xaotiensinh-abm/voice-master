"""License key crypto core — Ed25519 sign/verify.

Key format (see docs/licensing-packaging-spec.md §3):
    VM1.<b64url(payload_json)>.<b64url(signature)>
payload_json = compact JSON, sorted keys: {"v":1,"mc":..,"exp":null|"YYYY-MM-DD","tier":..,"iat":..}

The app verifies with the embedded PUBLIC key. Signing (author side) needs the
private key and is done by tools/license_gen.py — never shipped.
"""

from __future__ import annotations

import base64
import json
from datetime import date, datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# Public key (raw, base64url) — paired with tools/keys/private.pem.
# Regenerate via tools/license_keygen.py (changing it invalidates all issued keys).
PUBLIC_KEY_B64 = "cWM9MXSXD4xXMDynM_deEG2mfeT0Y-su99vNPI92mwM"

PREFIX = "VM1"


# ───────────────────── base64url helpers ──────────────────────────


def b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def b64u_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


# ───────────────────── signing (author / tests only) ──────────────


def encode_key(payload: dict[str, Any], private_key: Ed25519PrivateKey) -> str:
    """Build a signed license key string from a payload."""
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = private_key.sign(payload_bytes)
    return f"{PREFIX}.{b64u_encode(payload_bytes)}.{b64u_encode(sig)}"


def make_payload(machine_code: str, exp: str | None = None, tier: str = "std") -> dict[str, Any]:
    return {
        "v": 1,
        "mc": machine_code,
        "exp": exp,
        "tier": tier,
        "iat": datetime.now(timezone.utc).date().isoformat(),
    }


# ───────────────────── verification (app side) ────────────────────


def _public_key() -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(b64u_decode(PUBLIC_KEY_B64))


def verify_key(key: str, machine_code: str, today: date | None = None) -> dict[str, Any]:
    """Verify a license key against this machine.

    Returns {"ok": True, "payload": {...}} when fully valid, otherwise
    {"ok": False, "reason": "...", "payload": {...}|None}.
    reason ∈ {"bad_format","bad_signature","wrong_machine","expired"}.
    """
    today = today or datetime.now(timezone.utc).date()

    if not key or not isinstance(key, str):
        return {"ok": False, "reason": "bad_format", "payload": None}
    parts = key.strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        return {"ok": False, "reason": "bad_format", "payload": None}

    try:
        payload_bytes = b64u_decode(parts[1])
        sig = b64u_decode(parts[2])
    except Exception:
        return {"ok": False, "reason": "bad_format", "payload": None}

    try:
        _public_key().verify(sig, payload_bytes)
    except InvalidSignature:
        return {"ok": False, "reason": "bad_signature", "payload": None}
    except Exception:
        return {"ok": False, "reason": "bad_signature", "payload": None}

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return {"ok": False, "reason": "bad_format", "payload": None}

    if payload.get("mc") != machine_code:
        return {"ok": False, "reason": "wrong_machine", "payload": payload}

    exp = payload.get("exp")
    if exp:
        try:
            if today > date.fromisoformat(exp):
                return {"ok": False, "reason": "expired", "payload": payload}
        except ValueError:
            return {"ok": False, "reason": "bad_format", "payload": payload}

    return {"ok": True, "payload": payload}
