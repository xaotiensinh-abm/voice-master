"""License endpoints — status & activation. See docs/licensing-packaging-spec.md §6."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from models.schemas import (
    LicenseActivateRequest,
    LicenseActivateResponse,
    LicenseStatusResponse,
    make_error,
)
from services import license_service

router = APIRouter(prefix="/license", tags=["license"])


@router.get("/status", response_model=LicenseStatusResponse)
async def license_status() -> LicenseStatusResponse:
    data = await asyncio.to_thread(license_service.get_status)
    return LicenseStatusResponse(**data)


@router.post("/activate", response_model=LicenseActivateResponse)
async def license_activate(req: LicenseActivateRequest) -> LicenseActivateResponse:
    result = await asyncio.to_thread(license_service.activate, req.key)
    if not result.get("ok"):
        reason = result.get("reason", "bad_format")
        raise HTTPException(
            status_code=400,
            detail=make_error("LICENSE_INVALID").model_dump() | {"reason": reason},
        )
    return LicenseActivateResponse(
        ok=True,
        state=result.get("state"),
        exp=result.get("exp"),
        message="Kích hoạt thành công.",
    )
