"""DayPilot - Progress Router"""

from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from db.database import get_db
from models.schemas import DailyCheckIn
from services.progress_service import log_checkin, get_progress_summary

router = APIRouter()


@router.post("/checkin")
async def api_checkin(
    checkin: DailyCheckIn,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Log a daily energy/mood/focus check-in."""
    return await log_checkin(checkin, db)


@router.get("/{user_id}/summary/{period}")
async def api_progress_summary(
    user_id: str,
    period: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get a productivity summary with AI insights and burnout risk score."""
    if period not in ("weekly", "monthly"):
        raise HTTPException(status_code=400, detail="Period must be 'weekly' or 'monthly'")
    try:
        summary = await get_progress_summary(user_id, period, db)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
