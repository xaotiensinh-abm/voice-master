"""NEO Voice Backend — Settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from adapters.base import get_engine_statuses
from config import PORT, get, save_config
from models.schemas import SettingsRequest, SettingsResponse
from utils.security import (
    delete_api_key,
    get_api_key,
    redact_api_key_display,
    store_api_key,
)

router = APIRouter(prefix="/v1", tags=["settings"])


@router.get("/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Return settings with secrets redacted.
    
    Spec §05: GET /v1/settings
    ElevenLabs API key NEVER returned by API.
    """
    api_key = get_api_key()
    engines = get_engine_statuses()
    default_engine = get("default_engine", "vieneu")
    if default_engine not in ("vieneu", "elevenlabs"):
        default_engine = "vieneu"

    return SettingsResponse(
        elevenlabs_api_key=redact_api_key_display(api_key),
        elevenlabs_api_key_set=api_key is not None,
        default_output_folder=get("default_output_folder"),
        default_engine=default_engine,
        default_bitrate_kbps=int(get("default_bitrate_kbps", 128)),
        local_api_port=int(get("local_api_port", PORT)),
        elevenlabs_model_id=get("elevenlabs_model_id"),
        elevenlabs_default_voice=get("elevenlabs_default_voice"),
        elevenlabs_auto_fallback=bool(get("elevenlabs_auto_fallback", False)),
        cloud_privacy_warning=bool(get("cloud_privacy_warning", True)),
        vieneu_status=engines.get("vieneu").status if engines.get("vieneu") else None,
    )


@router.patch("/settings")
async def update_settings(request: SettingsRequest) -> dict:
    """Update settings.
    
    Spec §05: PATCH /v1/settings
    """
    updates = {}

    # Handle API key separately (store in keyring, not config.json)
    if request.elevenlabs_api_key is not None:
        if request.elevenlabs_api_key == "":
            delete_api_key()
        else:
            store_api_key(request.elevenlabs_api_key)

    # Persist other settings to config.json
    if request.default_output_folder is not None:
        updates["default_output_folder"] = request.default_output_folder
    if request.default_engine is not None:
        if request.default_engine not in ("vieneu", "elevenlabs"):
            request.default_engine = "vieneu"
        updates["default_engine"] = request.default_engine
    if request.default_bitrate_kbps is not None:
        updates["default_bitrate_kbps"] = request.default_bitrate_kbps
    if request.local_api_port is not None:
        updates["local_api_port"] = request.local_api_port
    if request.elevenlabs_model_id is not None:
        updates["elevenlabs_model_id"] = request.elevenlabs_model_id
    if request.elevenlabs_default_voice is not None:
        updates["elevenlabs_default_voice"] = request.elevenlabs_default_voice
    if request.elevenlabs_auto_fallback is not None:
        updates["elevenlabs_auto_fallback"] = request.elevenlabs_auto_fallback
    if request.cloud_privacy_warning is not None:
        updates["cloud_privacy_warning"] = request.cloud_privacy_warning

    if updates:
        save_config(updates)

    return {"status": "ok"}
