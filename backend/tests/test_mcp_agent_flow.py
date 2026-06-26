"""T9 — Full-loop integration test for the MCP agent workflow.

Drives synthesize → process → wait_for_job → download_job_audio twice (a loop),
using a fake VieNeu adapter and mocked audio-export functions so it needs NO
ffmpeg / audio libraries / GPU. The job is processed via job_queue._process_job
directly (deterministic, no background worker lifecycle).
"""

from __future__ import annotations

import json
import os

import aiosqlite
import pytest

import database
import mcp_server
from adapters.base import EngineHealth, register_adapter
from models.schemas import SynthesisResult
from services import job_queue


class FakeVieneu:
    engine_id = "vieneu"

    def health(self) -> EngineHealth:
        return EngineHealth(status="ready", loaded=True, model_downloaded=True)

    def list_voices(self):
        return []

    async def synthesize(self, req) -> SynthesisResult:
        path = os.path.join(req.output_dir, f"segment_{req.segment_index:04d}.wav")
        with open(path, "wb") as f:
            f.write(b"RIFFfake-wav-bytes" * 8)
        return SynthesisResult(ok=True, wav_path=path, duration_sec=1.0)


def parse(res):
    return json.loads(res[0].text)


@pytest.mark.asyncio
async def test_full_agent_loop(monkeypatch, tmp_path):
    # ── In-memory DB shared by MCP tools and the worker ──
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(database.SCHEMA_SQL)
    await conn.commit()
    monkeypatch.setattr(database, "_db", conn)

    # ── Fake engine + ready model (no GPU) ──
    register_adapter("vieneu", FakeVieneu())
    monkeypatch.setattr(mcp_server.model_manager, "is_downloaded", lambda *a, **k: True)

    # ── Mock audio export so no ffmpeg/audio libs are needed ──
    monkeypatch.setattr(job_queue, "EXPORT_DIR", tmp_path / "exports")
    monkeypatch.setattr(job_queue, "TEMP_DIR", tmp_path / "temp")
    (tmp_path / "temp").mkdir()
    monkeypatch.setattr(job_queue, "join_wav_segments", lambda wavs, out: open(out, "wb").write(b"\0" * 2048))
    monkeypatch.setattr(job_queue, "normalize_loudness", lambda p: None)
    monkeypatch.setattr(job_queue, "export_mp3", lambda src, out, bitrate_kbps=128: open(out, "wb").write(b"\0" * 4096))

    dest_dir = tmp_path / "agent_downloads"
    dest_dir.mkdir()

    async def run_one(text: str, n: int) -> str:
        created = parse(await mcp_server.call_tool(
            "synthesize", {"text": text, "voice_id": "vieneu:ngoc_lan", "mode": "story"}))
        assert "job_id" in created, created
        job_id = created["job_id"]

        # Process the queued job deterministically (stands in for the worker).
        await job_queue._process_job(job_id)

        status = parse(await mcp_server.call_tool(
            "wait_for_job", {"job_id": job_id, "poll_sec": 0.01, "timeout_sec": 5}))
        assert status["status"] == "completed", status

        dest = dest_dir / f"voice_{n}.mp3"
        dl = parse(await mcp_server.call_tool(
            "download_job_audio", {"job_id": job_id, "dest_path": str(dest)}))
        assert dl["saved_path"] == str(dest)
        assert dl["bytes"] >= 1024
        assert os.path.exists(dest)
        return dl["saved_path"]

    # ── The loop: two scripts back-to-back ──
    p1 = await run_one("Kịch bản số một. Xin chào cả nhà.", 1)
    p2 = await run_one("Kịch bản số hai. Hẹn gặp lại.", 2)

    assert p1 != p2
    assert os.path.exists(p1) and os.path.exists(p2)

    await conn.close()
    monkeypatch.setattr(database, "_db", None)
