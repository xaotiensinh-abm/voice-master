"""NEO Voice Backend — GPU detection utilities."""

from __future__ import annotations

import logging
import shutil
import subprocess
import time

from config import GPU_DETECT_TTL_SEC
from models.schemas import GPUInfo

logger = logging.getLogger(__name__)
_GPU_CACHE: tuple[float, GPUInfo] | None = None


def _parse_nvidia_smi() -> GPUInfo | None:
    """Detect GPU via nvidia-smi CLI."""
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        return None
    try:
        result = subprocess.run(
            [
                nvidia_smi,
                "--query-gpu=name,memory.total,memory.free,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            return None
        return GPUInfo(
            detected=True,
            name=parts[0],
            vram_total_mb=int(float(parts[1])),
            vram_free_mb=int(float(parts[2])),
            driver_version=parts[3],
            cuda_available=False,
        )
    except Exception as e:
        logger.warning("nvidia-smi failed: %s", e)
        return None


def _detect_via_torch() -> GPUInfo | None:
    """Detect GPU via PyTorch if installed."""
    try:
        import torch  # type: ignore

        if not torch.cuda.is_available():
            return GPUInfo(detected=False, cuda_available=False)

        name = torch.cuda.get_device_name(0)
        total = int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024))
        free = int(
            (torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0))
            / (1024 * 1024)
        )
        return GPUInfo(
            detected=True,
            name=name,
            vram_total_mb=total,
            vram_free_mb=free,
            cuda_available=True,
        )
    except ImportError:
        return None
    except Exception as e:
        logger.warning("torch GPU detection failed: %s", e)
        return None


def detect_gpu(force_refresh: bool = False) -> GPUInfo:
    """Detect GPU info, preferring torch then nvidia-smi."""
    global _GPU_CACHE
    now = time.monotonic()
    if (
        not force_refresh
        and _GPU_CACHE is not None
        and now - _GPU_CACHE[0] <= GPU_DETECT_TTL_SEC
    ):
        return _GPU_CACHE[1]

    info = _detect_via_torch()
    if info is not None:
        # If torch detected but didn't get driver info, supplement from nvidia-smi
        if info.detected and not info.driver_version:
            smi = _parse_nvidia_smi()
            if smi and smi.driver_version:
                info.driver_version = smi.driver_version
        _GPU_CACHE = (now, info)
        return info
    info = _parse_nvidia_smi()
    if info is not None:
        _GPU_CACHE = (now, info)
        return info
    info = GPUInfo(detected=False)
    _GPU_CACHE = (now, info)
    return info


def check_vram_threshold(min_free_mb: int) -> tuple[bool, int]:
    """Check if VRAM is above threshold. Returns (ok, free_mb)."""
    gpu = detect_gpu(force_refresh=True)
    if not gpu.detected or gpu.vram_free_mb is None:
        return False, 0
    return gpu.vram_free_mb >= min_free_mb, gpu.vram_free_mb
