"""Contract tests for the MCP agent tools (T1–T6, T10).

Fully mocked — no worker, no ffmpeg, no GPU. Exercises the private tool handlers
in mcp_server directly (plain async funcs) plus the registered tool catalog.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

import mcp_server
from models.schemas import JobResponse, make_error


def parse(res):
    """Extract the single JSON payload from a tool's TextContent result."""
    assert len(res) == 1
    return json.loads(res[0].text)


# ───────────────────── DB / model fakes ───────────────────────────


class FakeCursor:
    def __init__(self, one=None, many=None, one_seq=None):
        self._one = one
        self._many = many or []
        self._one_seq = one_seq

    async def fetchone(self):
        if self._one_seq is not None:
            return self._one_seq.pop(0) if self._one_seq else None
        return self._one

    async def fetchall(self):
        return self._many


class FakeDb:
    """Routes SELECTs to preset rows by SQL prefix."""

    def __init__(self, *, job=None, jobs=None, voices=None, history=None, job_seq=None):
        self.job = job
        self.jobs = jobs or []
        self.voices = voices or []
        self.history = history or []
        self.job_seq = job_seq

    async def execute(self, sql, params=()):
        s = sql.strip()
        if s.startswith("SELECT * FROM jobs"):
            return FakeCursor(one=self.job, one_seq=self.job_seq)
        if "FROM voices WHERE enabled" in s:
            return FakeCursor(many=self.voices)
        if "FROM jobs j" in s:  # history join
            return FakeCursor(many=self.history)
        return FakeCursor()


def use_db(monkeypatch, db):
    async def _get_db():
        return db
    monkeypatch.setattr(mcp_server, "get_db", _get_db)


# ───────────────────── Tool catalog (T1) ──────────────────────────


@pytest.mark.asyncio
async def test_tool_catalog_complete():
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}
    assert names == {
        "list_voices", "get_model_status", "ensure_model_ready", "synthesize",
        "get_job_status", "wait_for_job", "download_job_audio", "get_history", "cancel_job",
    }


@pytest.mark.asyncio
async def test_unknown_tool_returns_json_error():
    res = await mcp_server.call_tool("nope", {})
    assert parse(res)["error_code"] == "UNKNOWN_TOOL"


# ───────────────────── list_voices ────────────────────────────────


@pytest.mark.asyncio
async def test_list_voices(monkeypatch):
    use_db(monkeypatch, FakeDb(voices=[
        {"voice_id": "vieneu:ngoc_lan", "display_name": "Ngọc Lan", "engine": "vieneu",
         "styles_json": '["neutral","news"]', "emotions_json": '["neutral"]'},
    ]))
    data = parse(await mcp_server.call_tool("list_voices", {}))
    assert data["voices"][0]["voice_id"] == "vieneu:ngoc_lan"
    assert data["voices"][0]["styles"] == ["neutral", "news"]


# ───────────────────── model readiness (T2) ───────────────────────


@pytest.mark.asyncio
async def test_get_model_status(monkeypatch):
    monkeypatch.setattr(mcp_server.model_manager, "get_status",
                        lambda: {"repo_id": "r", "downloaded": True, "total_bytes": 100, "cache_path": "c", "state": "done", "error": None})
    monkeypatch.setattr(mcp_server.model_manager, "get_progress",
                        lambda: {"state": "done", "downloaded_bytes": 100, "total_bytes": 100, "percent": 100.0, "error": None})
    data = parse(await mcp_server.call_tool("get_model_status", {}))
    assert data["downloaded"] is True and data["percent"] == 100.0


@pytest.mark.asyncio
async def test_ensure_model_ready_no_wait(monkeypatch):
    calls = {"start": 0}
    monkeypatch.setattr(mcp_server.model_manager, "start_download", lambda: calls.__setitem__("start", calls["start"] + 1))
    monkeypatch.setattr(mcp_server.model_manager, "get_status",
                        lambda: {"downloaded": False, "state": "downloading", "error": None})
    monkeypatch.setattr(mcp_server.model_manager, "get_progress",
                        lambda: {"state": "downloading", "percent": 12.0, "error": None})
    data = parse(await mcp_server.call_tool("ensure_model_ready", {}))
    assert calls["start"] == 1
    assert data["state"] == "downloading" and data["percent"] == 12.0


# ───────────────────── synthesize (T3) ────────────────────────────


@pytest.mark.asyncio
async def test_synthesize_text_empty():
    data = parse(await mcp_server.call_tool("synthesize", {"text": "  ", "voice_id": "vieneu:x"}))
    assert data["error_code"] == "TEXT_EMPTY"


@pytest.mark.asyncio
async def test_synthesize_model_not_ready(monkeypatch):
    monkeypatch.setattr(mcp_server.model_manager, "is_downloaded", lambda *a, **k: False)
    data = parse(await mcp_server.call_tool("synthesize", {"text": "Xin chào", "voice_id": "vieneu:ngoc_lan"}))
    assert data["error_code"] == "MODEL_NOT_READY"


@pytest.mark.asyncio
async def test_synthesize_ok(monkeypatch):
    monkeypatch.setattr(mcp_server.model_manager, "is_downloaded", lambda *a, **k: True)

    async def fake_create_job(req):
        assert req.mode == "news"
        return JobResponse(job_id="job_test_1", status="queued")

    monkeypatch.setattr(mcp_server, "create_job", fake_create_job)
    data = parse(await mcp_server.call_tool(
        "synthesize", {"text": "Xin chào", "voice_id": "vieneu:ngoc_lan", "mode": "news"}))
    assert data == {"job_id": "job_test_1", "status": "queued"}


@pytest.mark.asyncio
async def test_synthesize_maps_http_error(monkeypatch):
    monkeypatch.setattr(mcp_server.model_manager, "is_downloaded", lambda *a, **k: True)

    async def boom(req):
        raise HTTPException(status_code=404, detail=make_error("UNKNOWN_VOICE").model_dump())

    monkeypatch.setattr(mcp_server, "create_job", boom)
    data = parse(await mcp_server.call_tool("synthesize", {"text": "hi", "voice_id": "vieneu:zzz"}))
    assert data["error_code"] == "UNKNOWN_VOICE"


@pytest.mark.asyncio
async def test_synthesize_invalid_mode(monkeypatch):
    monkeypatch.setattr(mcp_server.model_manager, "is_downloaded", lambda *a, **k: True)
    data = parse(await mcp_server.call_tool(
        "synthesize", {"text": "hi", "voice_id": "elevenlabs:x", "mode": "bogus"}))
    assert data["error_code"] == "INVALID_REQUEST"


# ───────────────────── get_job_status (T4) ────────────────────────


def _job_row(**over):
    base = {
        "job_id": "job_1", "status": "completed", "progress": 1.0, "stage": None,
        "segments_done": 3, "segments_total": 3, "output_path": "/x/out.mp3",
        "voice_id": "vieneu:ngoc_lan", "engine": "vieneu", "error_code": None,
        "error_message": None,
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_get_job_status_not_found(monkeypatch):
    use_db(monkeypatch, FakeDb(job=None))
    data = parse(await mcp_server.call_tool("get_job_status", {"job_id": "missing"}))
    assert data["error_code"] == "JOB_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_job_status_completed_has_audio_url(monkeypatch):
    use_db(monkeypatch, FakeDb(job=_job_row()))
    data = parse(await mcp_server.call_tool("get_job_status", {"job_id": "job_1"}))
    assert data["status"] == "completed"
    assert data["audio_url"].endswith("/v1/tts/jobs/job_1/audio")


@pytest.mark.asyncio
async def test_get_job_status_failed_has_error(monkeypatch):
    use_db(monkeypatch, FakeDb(job=_job_row(status="failed", error_code="WORKER_CRASHED", error_message="boom")))
    data = parse(await mcp_server.call_tool("get_job_status", {"job_id": "job_1"}))
    assert data["audio_url"] is None
    assert data["error"]["code"] == "WORKER_CRASHED"


# ───────────────────── wait_for_job (T5) ──────────────────────────


@pytest.mark.asyncio
async def test_wait_for_job_resolves(monkeypatch):
    seq = [_job_row(status="running", progress=0.5), _job_row(status="completed")]
    use_db(monkeypatch, FakeDb(job_seq=seq))
    data = parse(await mcp_server.call_tool("wait_for_job", {"job_id": "job_1", "poll_sec": 0.01, "timeout_sec": 5}))
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_wait_for_job_timeout(monkeypatch):
    # Always running → must time out.
    db = FakeDb(job=_job_row(status="running", progress=0.2))
    use_db(monkeypatch, db)
    data = parse(await mcp_server.call_tool("wait_for_job", {"job_id": "job_1", "poll_sec": 0.01, "timeout_sec": 0.05}))
    assert data["error_code"] == "TIMEOUT"


# ───────────────────── download_job_audio (T6) ────────────────────


@pytest.mark.asyncio
async def test_download_not_completed(monkeypatch):
    use_db(monkeypatch, FakeDb(job=_job_row(status="running")))
    data = parse(await mcp_server.call_tool("download_job_audio", {"job_id": "job_1"}))
    assert data["error_code"] == "JOB_NOT_COMPLETED"


@pytest.mark.asyncio
async def test_download_copies_to_dest(monkeypatch, tmp_path):
    src = tmp_path / "out.mp3"
    src.write_bytes(b"ID3fake-mp3-bytes")
    use_db(monkeypatch, FakeDb(job=_job_row(output_path=str(src))))
    dest_dir = tmp_path / "agent_out"
    dest_dir.mkdir()
    data = parse(await mcp_server.call_tool("download_job_audio", {"job_id": "job_1", "dest_path": str(dest_dir)}))
    assert data["bytes"] == len(b"ID3fake-mp3-bytes")
    assert (dest_dir / "out.mp3").exists()


@pytest.mark.asyncio
async def test_download_base64_optin(monkeypatch, tmp_path):
    src = tmp_path / "out.mp3"
    src.write_bytes(b"AUDIO")
    use_db(monkeypatch, FakeDb(job=_job_row(output_path=str(src))))
    data = parse(await mcp_server.call_tool("download_job_audio", {"job_id": "job_1", "include_base64": True}))
    import base64
    assert base64.b64decode(data["base64"]) == b"AUDIO"
    assert data["audio_url"].endswith("/v1/tts/jobs/job_1/audio")


@pytest.mark.asyncio
async def test_download_rejects_relative_dest(monkeypatch, tmp_path):
    src = tmp_path / "out.mp3"
    src.write_bytes(b"x")
    use_db(monkeypatch, FakeDb(job=_job_row(output_path=str(src))))
    data = parse(await mcp_server.call_tool("download_job_audio", {"job_id": "job_1", "dest_path": "relative/path.mp3"}))
    assert data["error_code"] == "INVALID_DEST_PATH"


# ───────────────────── cancel_job (T10) ───────────────────────────


@pytest.mark.asyncio
async def test_cancel_job(monkeypatch):
    async def fake_cancel(job_id):
        return {"status": "cancelled"}
    monkeypatch.setattr(mcp_server, "cancel_job_endpoint", fake_cancel)
    data = parse(await mcp_server.call_tool("cancel_job", {"job_id": "job_1"}))
    assert data["status"] == "cancelled"
