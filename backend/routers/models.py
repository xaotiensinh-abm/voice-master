"""Voice-Master Backend — VieNeu model download endpoints.

First-run flow: the VieNeu-TTS v3 Turbo model is downloaded on demand into the
HuggingFace cache (it is not bundled with the installer). See
services/model_manager.py and docs/feature-plan-model-download.md.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from models.schemas import ModelProgressResponse, ModelStatusResponse
from services import model_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/status", response_model=ModelStatusResponse)
async def model_status() -> ModelStatusResponse:
    """Whether the VieNeu model is present locally, its size, and cache path."""
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, model_manager.get_status)
    return ModelStatusResponse(**data)


@router.post("/download", response_model=ModelProgressResponse)
async def model_download() -> ModelProgressResponse:
    """Start the background download (idempotent; no cancel)."""
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, model_manager.start_download)
    # start_download() may return either a progress dict or a status dict
    # (when already downloaded); normalize to progress shape.
    if "downloaded_bytes" not in data:
        prog = await loop.run_in_executor(None, model_manager.get_progress)
        return ModelProgressResponse(**prog)
    return ModelProgressResponse(**data)


@router.get("/download/progress", response_model=ModelProgressResponse)
async def model_download_progress() -> ModelProgressResponse:
    """Current download progress (poll while state == downloading)."""
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, model_manager.get_progress)
    return ModelProgressResponse(**data)


@router.delete("", response_model=ModelStatusResponse)
async def model_delete() -> ModelStatusResponse:
    """Remove the cached model to free space / force a fresh re-download."""
    loop = asyncio.get_running_loop()
    try:
        data = await loop.run_in_executor(None, model_manager.delete)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return ModelStatusResponse(**data)
