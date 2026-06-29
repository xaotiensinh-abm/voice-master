"""NEO Voice Backend — Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from adapters.base import get_engine_statuses
from config import MAX_CHARS_PER_CHUNK, PORT, VERSION
from models.schemas import HealthResponse
from utils.gpu import detect_gpu

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return backend health status, engine statuses, GPU info.
    
    Spec §05: GET /health
    """
    gpu = detect_gpu()
    engines = get_engine_statuses()

    try:
        from services.license_service import get_status as _license_status

        ls = _license_status()
        license_summary = {
            "state": ls["state"],
            "enforced": ls["enforced"],
            "days_left": ls["days_left"],
        }
    except Exception:
        license_summary = None

    return HealthResponse(
        status="ok",
        version=VERSION,
        port=PORT,
        engines=engines,
        gpu=gpu,
        max_chars_per_chunk=dict(MAX_CHARS_PER_CHUNK),
        license=license_summary,
    )
