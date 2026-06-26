import pytest
from fastapi import HTTPException

from adapters.base import EngineHealth
from models.schemas import JobCreateRequest, JobInput, JobOutput
from routers.tts import create_job, delete_job_endpoint


class UnavailableAdapter:
    def health(self) -> EngineHealth:
        return EngineHealth(status="unavailable", error="missing model")


class FakeCursor:
    def __init__(self, row=None, rowcount=0):
        self._row = row
        self.rowcount = rowcount

    async def fetchone(self):
        return self._row


class FakeDb:
    def __init__(self):
        self.queries = []
        self.committed = False

    async def execute(self, sql, params=()):
        self.queries.append((sql, params))
        if sql.startswith("SELECT status"):
            return FakeCursor({"status": "completed"})
        if sql.startswith("DELETE FROM jobs"):
            return FakeCursor(rowcount=1)
        return FakeCursor()

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_create_job_rejects_unavailable_engine_before_enqueue(monkeypatch):
    monkeypatch.setattr("routers.tts.get_adapter", lambda voice_id: UnavailableAdapter())

    async def fail_get_db():
        raise AssertionError("unavailable engine should not reach the database")

    monkeypatch.setattr("routers.tts.get_db", fail_get_db)

    request = JobCreateRequest(
        voice_id="vieneu:ngoc_lan",
        input=JobInput(type="text", text="Xin chao."),
        output=JobOutput(format="mp3"),
    )

    with pytest.raises(HTTPException) as exc:
        await create_job(request)

    assert exc.value.status_code == 503
    assert exc.value.detail["error_code"] == "ENGINE_UNAVAILABLE"
    assert exc.value.detail["detail"] == "missing model"


@pytest.mark.asyncio
async def test_delete_job_removes_history_record(monkeypatch):
    db = FakeDb()

    async def fake_get_db():
        return db

    monkeypatch.setattr("routers.tts.get_db", fake_get_db)

    result = await delete_job_endpoint("job_123")

    assert result == {"status": "deleted", "deleted": 1}
    assert db.committed is True
    assert any(
        sql == "DELETE FROM jobs WHERE job_id = ?" and params == ("job_123",)
        for sql, params in db.queries
    )
