"""
DayPilot - Goals Service
"""

import json
import uuid
from datetime import datetime, date
from typing import List, Optional
import aiosqlite

from agentz.planner_agent import run_planner
from models.schemas import Goal, GoalCreate, GoalProgressUpdate


async def create_goal(
    user_id: str,
    goal_in: GoalCreate,
    db: aiosqlite.Connection,
) -> Goal:
    """Create a goal and generate an AI roadmap for it."""

    goal_id = str(uuid.uuid4())
    now_str = datetime.utcnow().isoformat()

    # Fetch user profile
    async with db.execute(
        "SELECT profile_json FROM users WHERE user_id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    profile_data = json.loads(row["profile_json"]) if row else {}

    # AI roadmap generation
    prompt = f"""
Create a detailed step-by-step roadmap to achieve this goal:

GOAL:
{json.dumps(goal_in.model_dump(), indent=2, default=str)}

USER PROFILE:
{json.dumps(profile_data, indent=2)}

Return a JSON array of weekly milestones:
[
  {{
    "week": 1,
    "theme": "<focus theme>",
    "target": "<specific measurable target>",
    "daily_actions": ["action1", "action2"],
    "success_metric": "<how to know this week is done>"
  }}
]

Be specific, realistic, and motivating.
If target_date is set, work backwards to fit the timeline.
Daily time budget: {goal_in.daily_time_budget_minutes} minutes/day.
""".strip()

    roadmap_raw = await run_planner(prompt)
    try:
        clean   = roadmap_raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        roadmap = json.loads(clean)
    except Exception:
        roadmap = []

    await db.execute(
        """
        INSERT INTO goals
        (goal_id, user_id, title, description, category, priority, target_date,
         daily_time_budget_min, milestones_json, roadmap_json, progress_percent, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 'active', ?)
        """,
        (
            goal_id,
            user_id,
            goal_in.title,
            goal_in.description,
            goal_in.category,
            goal_in.priority,
            goal_in.target_date.isoformat() if goal_in.target_date else None,
            goal_in.daily_time_budget_minutes,
            json.dumps(goal_in.milestones or []),
            json.dumps(roadmap),
            now_str,
        ),
    )
    await db.commit()

    return Goal(
        goal_id=goal_id,
        user_id=user_id,
        created_at=datetime.utcnow(),
        roadmap=roadmap,
        **goal_in.model_dump(),
    )


async def list_goals(user_id: str, db: aiosqlite.Connection) -> List[Goal]:
    async with db.execute(
        "SELECT * FROM goals WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_goal(r) for r in rows]


async def get_goal(goal_id: str, user_id: str, db: aiosqlite.Connection) -> Optional[Goal]:
    async with db.execute(
        "SELECT * FROM goals WHERE goal_id = ? AND user_id = ?", (goal_id, user_id)
    ) as cur:
        row = await cur.fetchone()
    return _row_to_goal(row) if row else None


async def update_progress(
    goal_id: str,
    user_id: str,
    update: GoalProgressUpdate,
    db: aiosqlite.Connection,
) -> Goal:
    await db.execute(
        "UPDATE goals SET progress_percent = ? WHERE goal_id = ? AND user_id = ?",
        (update.progress_percent, goal_id, user_id),
    )
    await db.commit()
    goal = await get_goal(goal_id, user_id, db)
    if not goal:
        raise ValueError("Goal not found")
    return goal


async def delete_goal(goal_id: str, user_id: str, db: aiosqlite.Connection):
    await db.execute(
        "DELETE FROM goals WHERE goal_id = ? AND user_id = ?", (goal_id, user_id)
    )
    await db.commit()


def _row_to_goal(row) -> Goal:
    return Goal(
        goal_id=row["goal_id"],
        user_id=row["user_id"],
        title=row["title"],
        description=row["description"],
        category=row["category"],
        priority=row["priority"],
        target_date=date.fromisoformat(row["target_date"]) if row["target_date"] else None,
        daily_time_budget_minutes=row["daily_time_budget_min"],
        milestones=json.loads(row["milestones_json"] or "[]"),
        roadmap=json.loads(row["roadmap_json"] or "[]"),
        progress_percent=row["progress_percent"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
