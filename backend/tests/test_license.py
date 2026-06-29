"""License unit/integration tests (see docs/licensing-packaging-spec.md §12).

No real private key needed: an ephemeral keypair is generated and the embedded
public key is monkeypatched. Registry access is stubbed so tests don't touch HKCU.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import HTTPException

import config
from services import license_core, license_service, machine_id, trial


@pytest.fixture
def eph(monkeypatch):
    priv = Ed25519PrivateKey.generate()
    pub_raw = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    monkeypatch.setattr(license_core, "PUBLIC_KEY_B64", license_core.b64u_encode(pub_raw))
    return priv


def make_key(priv, mc, exp=None):
    return license_core.encode_key(license_core.make_payload(mc, exp=exp), priv)


# ───────────────────── crypto core ────────────────────────────────


def test_verify_ok(eph):
    k = make_key(eph, "AAAA-BBBB-CCCC-DDDD")
    assert license_core.verify_key(k, "AAAA-BBBB-CCCC-DDDD")["ok"] is True


def test_verify_wrong_machine(eph):
    k = make_key(eph, "AAAA-BBBB-CCCC-DDDD")
    res = license_core.verify_key(k, "ZZZZ-ZZZZ-ZZZZ-ZZZZ")
    assert not res["ok"] and res["reason"] == "wrong_machine"


def test_verify_tampered(eph):
    k = make_key(eph, "AAAA-BBBB-CCCC-DDDD")
    prefix, payload, sig = k.split(".")
    flipped = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    res = license_core.verify_key(f"{prefix}.{flipped}.{sig}", "AAAA-BBBB-CCCC-DDDD")
    assert not res["ok"] and res["reason"] in ("bad_signature", "bad_format")


def test_verify_expired(eph):
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    k = make_key(eph, "AAAA-BBBB-CCCC-DDDD", exp=yesterday)
    res = license_core.verify_key(k, "AAAA-BBBB-CCCC-DDDD")
    assert not res["ok"] and res["reason"] == "expired"


def test_verify_bad_format(eph):
    assert license_core.verify_key("garbage", "AAAA-BBBB-CCCC-DDDD")["reason"] == "bad_format"
    assert license_core.verify_key("VM1.only-two", "AAAA-BBBB-CCCC-DDDD")["reason"] == "bad_format"


# ───────────────────── machine code ───────────────────────────────


def test_machine_code_format_stable():
    mc = machine_id.get_machine_code()
    assert re.fullmatch(r"[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}", mc)
    assert mc == machine_id.get_machine_code()  # stable


# ───────────────────── trial + service ────────────────────────────


@pytest.fixture
def lic_env(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "NEO_VOICE_HOME", tmp_path)
    monkeypatch.setattr(config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(trial, "_reg_read", lambda: None)
    monkeypatch.setattr(trial, "_reg_write", lambda iso: None)


def _write_store(data: dict):
    config.LICENSE_PATH.write_text(__import__("json").dumps(data), encoding="utf-8")


def test_dev_mode_allows(lic_env, monkeypatch):
    monkeypatch.setattr(config, "LICENSE_ENFORCED", False)
    assert license_service.is_allowed() is True
    assert license_service.get_status()["state"] == "dev"


def test_fresh_trial_active(lic_env, monkeypatch):
    monkeypatch.setattr(config, "LICENSE_ENFORCED", True)
    st = license_service.get_status()
    assert st["state"] == "trial" and st["days_left"] == trial.TRIAL_DAYS
    assert license_service.is_allowed() is True


def test_expired_trial_blocks(lic_env, monkeypatch):
    monkeypatch.setattr(config, "LICENSE_ENFORCED", True)
    past = (datetime.now(timezone.utc) - timedelta(days=trial.TRIAL_DAYS + 1)).isoformat()
    _write_store({"trial": {"first_run": past, "days": trial.TRIAL_DAYS, "hmac": trial._hmac(past, trial.TRIAL_DAYS)}})
    assert license_service.get_status()["state"] == "expired"
    assert license_service.is_allowed() is False


def test_activate_unlocks(lic_env, eph, monkeypatch):
    monkeypatch.setattr(config, "LICENSE_ENFORCED", True)
    past = (datetime.now(timezone.utc) - timedelta(days=trial.TRIAL_DAYS + 1)).isoformat()
    _write_store({"trial": {"first_run": past, "days": trial.TRIAL_DAYS, "hmac": trial._hmac(past, trial.TRIAL_DAYS)}})
    assert license_service.is_allowed() is False

    mc = machine_id.get_machine_code()
    res = license_service.activate(make_key(eph, mc))
    assert res["ok"] is True
    assert license_service.get_status()["state"] == "licensed"
    assert license_service.is_allowed() is True


def test_activate_wrong_machine_rejected(lic_env, eph, monkeypatch):
    monkeypatch.setattr(config, "LICENSE_ENFORCED", True)
    res = license_service.activate(make_key(eph, "ZZZZ-ZZZZ-ZZZZ-ZZZZ"))
    assert res["ok"] is False and res["reason"] == "wrong_machine"


# ───────────────────── gate at create_job ─────────────────────────


@pytest.mark.asyncio
async def test_create_job_blocked_when_not_allowed(monkeypatch):
    from routers import tts
    from models.schemas import JobCreateRequest, JobInput, JobOutput

    monkeypatch.setattr("services.license_service.is_allowed", lambda: False)
    monkeypatch.setattr(
        "services.license_service.get_status",
        lambda: {"machine_code": "AAAA-BBBB-CCCC-DDDD", "days_left": 0, "state": "expired"},
    )

    req = JobCreateRequest(
        voice_id="vieneu:ngoc_lan",
        input=JobInput(type="text", text="Xin chao."),
        output=JobOutput(format="mp3"),
    )
    with pytest.raises(HTTPException) as exc:
        await tts.create_job(req)
    assert exc.value.status_code == 402
    assert exc.value.detail["error_code"] == "LICENSE_REQUIRED"
    assert exc.value.detail["machine_code"] == "AAAA-BBBB-CCCC-DDDD"
