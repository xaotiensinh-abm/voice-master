"""NEO Voice Backend — Diagnostics endpoints."""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter

from adapters.base import get_all_adapters, get_engine_statuses
from models.schemas import (
    BenchmarkRequest,
    BenchmarkResponse,
    BenchmarkResult,
    DiagnosticsResponse,
    SynthesisRequest,
)
from utils.audio import is_ffmpeg_available
from utils.gpu import detect_gpu

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["diagnostics"])

# Benchmark test texts
BENCHMARK_TEXTS = {
    "short": "Xin chào, đây là NEO Voice đang chạy bằng VieNeu-TTS.",
    "medium": (
        "Hôm nay, ban chuyển đổi số công bố kế hoạch triển khai nền tảng dữ liệu nội bộ "
        "trong quý tới. Đây là bước tiến quan trọng trong hành trình số hóa của tổ chức, "
        "giúp tối ưu quy trình làm việc và nâng cao hiệu suất."
    ),
}


@router.get("/diagnostics/gpu", response_model=DiagnosticsResponse)
async def diagnostics_gpu() -> DiagnosticsResponse:
    """Return GPU info, engine statuses, and ffmpeg availability.
    
    Spec §05: GET /v1/diagnostics/gpu
    """
    return DiagnosticsResponse(
        gpu=detect_gpu(),
        engines=get_engine_statuses(),
        ffmpeg_available=is_ffmpeg_available(),
    )


@router.post("/diagnostics/benchmark", response_model=BenchmarkResponse)
async def run_benchmark(request: BenchmarkRequest) -> BenchmarkResponse:
    """Run benchmark suite on selected engines.
    
    Spec §05: POST /v1/diagnostics/benchmark
    """
    adapters = get_all_adapters()
    results: list[BenchmarkResult] = []

    # Map engine names to adapter prefixes
    engine_prefix_map = {
        "vieneu": "vieneu",
        "elevenlabs": "elevenlabs",
    }

    for engine_name in request.engines:
        prefix = engine_prefix_map.get(engine_name, engine_name)
        adapter = adapters.get(prefix)

        if adapter is None:
            results.append(
                BenchmarkResult(
                    engine=engine_name,
                    text_label="N/A",
                    ok=False,
                    error=f"Engine '{engine_name}' not registered.",
                )
            )
            continue

        # Check health first
        health = adapter.health()
        if health.status in ("unavailable", "error", "not_configured"):
            results.append(
                BenchmarkResult(
                    engine=engine_name,
                    text_label="N/A",
                    ok=False,
                    error=f"Engine unavailable: {health.error or health.status}",
                )
            )
            continue

        for text_label in request.texts:
            text = BENCHMARK_TEXTS.get(text_label, text_label)

            try:
                import tempfile
                import os

                temp_dir = tempfile.mkdtemp(prefix=f"bench_{engine_name}_")
                synth_req = SynthesisRequest(
                    job_id=f"bench_{engine_name}_{text_label}",
                    voice_id=f"{prefix}:{_get_default_voice(prefix)}",
                    text=text,
                    output_dir=temp_dir,
                )

                start = time.time()
                result = await adapter.synthesize(synth_req)
                elapsed = time.time() - start

                if result.ok:
                    results.append(
                        BenchmarkResult(
                            engine=engine_name,
                            text_label=text_label,
                            duration_sec=elapsed,
                            rtf=result.rtf,
                            ok=True,
                        )
                    )
                else:
                    results.append(
                        BenchmarkResult(
                            engine=engine_name,
                            text_label=text_label,
                            ok=False,
                            error=result.error_message,
                        )
                    )

            except Exception as e:
                results.append(
                    BenchmarkResult(
                        engine=engine_name,
                        text_label=text_label,
                        ok=False,
                        error=str(e),
                    )
                )

    return BenchmarkResponse(results=results)


def _get_default_voice(prefix: str) -> str:
    """Get default voice slug for benchmarking."""
    defaults = {
        "vieneu": "ngoc_lan",
        "elevenlabs": "default",
    }
    return defaults.get(prefix, "default")
