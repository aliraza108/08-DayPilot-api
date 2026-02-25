"""DayPilot - Schedule Router"""

from fastapi import APIRouter, Depends, HTTPException
from datetime import date
import aiosqlite

from db.database import get_db
from models.schemas import ScheduleGenerateRequest, TaskStatusUpdate
from services.schedule_service import (
    generate_schedule, get_schedule, update_task_status, adaptive_reschedule_today,
)

router = APIRouter()


@router.post("/generate")
async def api_generate_schedule(
    request: ScheduleGenerateRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Generate an AI-optimized daily schedule."""
    try:
        schedule = await generate_schedule(request, db)
        return schedule
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule generation failed: {e}")


@router.get("/{user_id}/{target_date}")
async def api_get_schedule(
    user_id: str,
    target_date: date,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Retrieve an existing schedule for a specific date."""
    schedule = await get_schedule(user_id, target_date, db)
    if not schedule:
        raise HTTPException(status_code=404, detail="No schedule found for that date.")
    return schedule


@router.patch("/{user_id}/task")
async def api_update_task(
    user_id: str,
    update: TaskStatusUpdate,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Mark a task as completed, skipped, or in-progress."""
    try:
        result = await update_task_status(user_id, update, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{user_id}/reschedule")
async def api_reschedule(
    user_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Adaptively reschedule the rest of today based on missed tasks."""
    try:
        schedule = await adaptive_reschedule_today(user_id, db)
        return schedule
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
