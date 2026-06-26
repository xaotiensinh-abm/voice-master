"""Voice-Master Backend — History endpoints (Redo feature)."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import get_db
from models.schemas import JobCreateRequest, JobInput, JobOutput, JobResponse, make_error
from routers.tts import create_job

router = APIRouter(prefix="/v1/history", tags=["history"])

class HistoryEntry(BaseModel):
    job_id: str
    voice_id: str
    voice_name: str | None = None
    engine: str | None = None
    input_text: str | None = None
    mode: str | None = None
    emotion: str | None = None
    speed: float = 1.0
    output_path: str | None = None
    created_at: str
    completed_at: str | None = None

class HistoryListResponse(BaseModel):
    items: list[HistoryEntry]
    total: int

@router.get("", response_model=HistoryListResponse)
async def get_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> HistoryListResponse:
    """Get history of completed jobs."""
    db = await get_db()
    
    # Query jobs and join with voices to get display_name
    query = """
        SELECT j.job_id, j.voice_id, v.display_name as voice_name, j.engine, 
               j.input_text, j.mode, j.emotion, j.speed, j.output_path, 
               j.created_at, j.completed_at
        FROM jobs j
        LEFT JOIN voices v ON j.voice_id = v.voice_id
        WHERE j.status = 'completed' AND j.input_text IS NOT NULL
        ORDER BY j.created_at DESC
        LIMIT ? OFFSET ?
    """
    
    cursor = await db.execute(query, (limit, offset))
    rows = await cursor.fetchall()
    
    # Get total count
    count_cursor = await db.execute("SELECT COUNT(*) FROM jobs WHERE status = 'completed' AND input_text IS NOT NULL")
    total = (await count_cursor.fetchone())[0]
    
    items = []
    for r in rows:
        items.append(HistoryEntry(**dict(r)))
        
    return HistoryListResponse(items=items, total=total)

@router.post("/{job_id}/redo", response_model=JobResponse)
async def redo_job(job_id: str) -> JobResponse:
    """Create a new job from a historical job's parameters."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    job = await cursor.fetchone()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=make_error("JOB_NOT_FOUND").model_dump()
        )
        
    if not job["input_text"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "Chỉ có thể làm lại các job tạo từ văn bản."}
        )
        
    # Reconstruct request for create_job
    req = JobCreateRequest(
        input=JobInput(type="text", text=job["input_text"]),
        voice_id=job["voice_id"],
        mode=job["mode"] or "neutral",
        emotion=job["emotion"] or "neutral",
        speed=job["speed"] or 1.0,
        output=JobOutput(format=job["output_format"] or "mp3")
    )
    
    # Call the existing create_job logic
    return await create_job(req)
