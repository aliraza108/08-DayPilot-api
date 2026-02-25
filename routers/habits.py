"""DayPilot - Habits Router"""

import json
import uuid
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from db.database import get_db
from models.schemas import HabitCreate, Habit, HabitCheckIn
from agentz.planner_agent import run_planner

router = APIRouter()


@router.post("/{user_id}")
async def api_create_habit(
    user_id: str,
    habit_in: HabitCreate,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Create a new habit."""
    habit_id = str(uuid.uuid4())
    now_str  = datetime.utcnow().isoformat()

    await db.execute(
        """
        INSERT INTO habits
        (habit_id, user_id, title, description, goal_id, frequency, preferred_time,
         duration_minutes, reminder, cue, reward, streak_count, completion_rate, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0.0, ?)
        """,
        (
            habit_id, user_id, habit_in.title, habit_in.description,
            habit_in.goal_id, habit_in.frequency, habit_in.preferred_time,
            habit_in.duration_minutes, int(habit_in.reminder),
            habit_in.cue, habit_in.reward, now_str,
        ),
    )
    await db.commit()

    return Habit(
        habit_id=habit_id,
        user_id=user_id,
        created_at=datetime.utcnow(),
        **habit_in.model_dump(),
    )


@router.get("/{user_id}")
async def api_list_habits(
    user_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """List all habits for a user."""
    async with db.execute(
        "SELECT * FROM habits WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_habit(r) for r in rows]


@router.post("/{user_id}/checkin")
async def api_habit_checkin(
    user_id: str,
    checkin: HabitCheckIn,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Log a habit completion for a given date."""
    log_id  = str(uuid.uuid4())
    now_str = datetime.utcnow().isoformat()

    await db.execute(
        "INSERT INTO habit_logs (log_id, habit_id, user_id, date, completed, note, logged_at) VALUES (?,?,?,?,?,?,?)",
        (log_id, checkin.habit_id, user_id, checkin.date.isoformat(), int(checkin.completed), checkin.note, now_str),
    )

    if checkin.completed:
        await db.execute(
            "UPDATE habits SET streak_count = streak_count + 1, last_completed = ? WHERE habit_id = ?",
            (checkin.date.isoformat(), checkin.habit_id),
        )
    else:
        await db.execute(
            "UPDATE habits SET streak_count = 0 WHERE habit_id = ?",
            (checkin.habit_id,),
        )

    await db.commit()
    return {"log_id": log_id, "message": "Habit check-in recorded ✅"}


@router.post("/{user_id}/ai-suggest")
async def api_suggest_habits(
    user_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Ask the AI to suggest habits based on the user's goals."""
    async with db.execute(
        "SELECT title, category, priority FROM goals WHERE user_id = ? AND status = 'active'",
        (user_id,),
    ) as cur:
        goal_rows = await cur.fetchall()

    async with db.execute(
        "SELECT profile_json FROM users WHERE user_id = ?", (user_id,)
    ) as cur:
        urow = await cur.fetchone()

    goals   = [dict(g) for g in goal_rows]
    profile = json.loads(urow["profile_json"]) if urow else {}

    prompt = f"""
Suggest 5 atomic habits for this user based on their goals.

GOALS: {json.dumps(goals)}
PROFILE: {json.dumps(profile)}

Return a JSON array:
[
  {{
    "title": "...",
    "description": "...",
    "cue": "<trigger>",
    "routine": "<exact action>",
    "reward": "<immediate reward>",
    "duration_minutes": <int>,
    "best_time": "HH:MM",
    "linked_goal": "<goal title>"
  }}
]
""".strip()

    result = await run_planner(prompt)
    try:
        clean  = result.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json.loads(clean)
    except Exception:
        parsed = []
    return {"suggestions": parsed}


@router.delete("/{user_id}/{habit_id}")
async def api_delete_habit(
    user_id: str,
    habit_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Delete a habit."""
    await db.execute(
        "DELETE FROM habits WHERE habit_id = ? AND user_id = ?", (habit_id, user_id)
    )
    await db.commit()
    return {"message": "Habit deleted."}


def _row_to_habit(row) -> Habit:
    return Habit(
        habit_id=row["habit_id"],
        user_id=row["user_id"],
        title=row["title"],
        description=row["description"],
        goal_id=row["goal_id"],
        frequency=row["frequency"],
        preferred_time=row["preferred_time"],
        duration_minutes=row["duration_minutes"],
        reminder=bool(row["reminder"]),
        cue=row["cue"],
        reward=row["reward"],
        streak_count=row["streak_count"],
        completion_rate=row["completion_rate"],
        last_completed=date.fromisoformat(row["last_completed"]) if row["last_completed"] else None,
        created_at=datetime.fromisoformat(row["created_at"]),
    )
