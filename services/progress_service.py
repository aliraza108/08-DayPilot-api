"""
DayPilot - Progress & Analytics Service
"""

import json
import uuid
from datetime import date, datetime, timedelta
from typing import List
import aiosqlite

from agentz.planner_agent import run_planner
from models.schemas import DailyCheckIn, ProgressSummary


async def log_checkin(checkin: DailyCheckIn, db: aiosqlite.Connection) -> dict:
    """Save a daily check-in for mood/energy/focus tracking."""
    checkin_id = str(uuid.uuid4())
    now_str    = datetime.utcnow().isoformat()

    await db.execute(
        """
        INSERT OR REPLACE INTO daily_checkins
        (checkin_id, user_id, date, energy_level, mood_score, focus_score, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            checkin_id,
            checkin.user_id,
            checkin.date.isoformat(),
            checkin.energy_level,
            checkin.mood_score,
            checkin.focus_score,
            checkin.notes,
            now_str,
        ),
    )
    await db.commit()
    return {"checkin_id": checkin_id, "message": "Check-in logged ✅"}


async def get_progress_summary(
    user_id: str,
    period: str,
    db: aiosqlite.Connection,
) -> ProgressSummary:
    """Calculate completion rate, goal status, burnout risk, and AI insights."""

    today   = date.today()
    days    = 7 if period == "weekly" else 30
    from_dt = (today - timedelta(days=days)).isoformat()

    # Schedule completion rate
    async with db.execute(
        "SELECT time_blocks FROM schedules WHERE user_id = ? AND date >= ?",
        (user_id, from_dt),
    ) as cur:
        sched_rows = await cur.fetchall()

    total_blocks     = 0
    completed_blocks = 0
    category_hours: dict = {}

    for srow in sched_rows:
        blocks = json.loads(srow["time_blocks"] or "[]")
        for b in blocks:
            total_blocks += 1
            if b.get("status") == "completed":
                completed_blocks += 1
            start_h, start_m = map(int, b.get("start_time", "00:00").split(":"))
            end_h,   end_m   = map(int, b.get("end_time",   "00:00").split(":"))
            duration_hrs     = ((end_h * 60 + end_m) - (start_h * 60 + start_m)) / 60
            cat = b.get("category", "other")
            category_hours[cat] = category_hours.get(cat, 0.0) + max(0, duration_hrs)

    completion_rate = (completed_blocks / total_blocks) if total_blocks else 0.0

    # Goals on/off track
    async with db.execute(
        "SELECT goal_id, title, progress_percent, target_date FROM goals WHERE user_id = ? AND status = 'active'",
        (user_id,),
    ) as cur:
        goal_rows = await cur.fetchall()

    goals_on_track: List[str] = []
    goals_at_risk:  List[str] = []

    for g in goal_rows:
        pct         = g["progress_percent"]
        target_date = date.fromisoformat(g["target_date"]) if g["target_date"] else None
        days_left   = (target_date - today).days if target_date else 999
        required    = (days / (days + days_left)) * 100 if days_left > 0 else 100
        if pct >= required * 0.85:
            goals_on_track.append(g["title"])
        else:
            goals_at_risk.append(g["title"])

    # Habit streaks
    async with db.execute(
        "SELECT title, streak_count FROM habits WHERE user_id = ?", (user_id,)
    ) as cur:
        habit_rows = await cur.fetchall()
    habit_streaks = {h["title"]: h["streak_count"] for h in habit_rows}

    # Check-ins for burnout
    async with db.execute(
        "SELECT energy_level, mood_score, focus_score FROM daily_checkins WHERE user_id = ? AND date >= ?",
        (user_id, from_dt),
    ) as cur:
        checkin_rows = await cur.fetchall()

    checkins_data = [dict(c) for c in checkin_rows]
    burnout_risk  = 0.0

    if checkins_data:
        avg_mood      = sum(c["mood_score"]  for c in checkins_data) / len(checkins_data)
        avg_focus     = sum(c["focus_score"] for c in checkins_data) / len(checkins_data)
        energy_penalty = sum(1 for c in checkins_data if c["energy_level"] == "low") / len(checkins_data)
        work_hrs_avg  = sum(category_hours.get(cat, 0) for cat in ("work", "study")) / max(days, 1)
        burnout_risk  = round(
            min(1.0,
                (1 - avg_mood / 10)  * 0.35 +
                (1 - avg_focus / 10) * 0.25 +
                energy_penalty       * 0.20 +
                min(work_hrs_avg / 10, 1.0) * 0.20
            ), 3,
        )

    # AI insights
    insights_prompt = f"""
Analyze this user's {period} productivity data and provide 3 concise, actionable insights:

COMPLETION RATE: {completion_rate:.0%}
GOALS ON TRACK: {goals_on_track}
GOALS AT RISK: {goals_at_risk}
BURNOUT RISK SCORE: {burnout_risk:.2f} (0=none, 1=high)
TIME ALLOCATION: {json.dumps(category_hours)}
HABIT STREAKS: {json.dumps(habit_streaks)}

Be specific and encouraging. Under 150 words. Plain text only.
""".strip()

    ai_insights = await run_planner(insights_prompt)

    return ProgressSummary(
        user_id=user_id,
        period=period,
        completion_rate=round(completion_rate, 3),
        goals_on_track=goals_on_track,
        goals_at_risk=goals_at_risk,
        habit_streaks=habit_streaks,
        time_allocation=category_hours,
        productivity_trend=[],
        burnout_risk_score=burnout_risk,
        ai_insights=ai_insights,
    )
