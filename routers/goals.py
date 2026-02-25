"""DayPilot - Goals Router"""

import json
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from db.database import get_db
from models.schemas import GoalCreate, GoalProgressUpdate, ScenarioRequest
from services.goal_service import (
    create_goal, list_goals, get_goal, update_progress, delete_goal,
)
from agentz.planner_agent import run_planner

router = APIRouter()


@router.post("/{user_id}")
async def api_create_goal(
    user_id: str,
    goal_in: GoalCreate,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Create a new goal and auto-generate an AI roadmap."""
    try:
        goal = await create_goal(user_id, goal_in, db)
        return goal
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}")
async def api_list_goals(
    user_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """List all active goals for a user."""
    return await list_goals(user_id, db)


@router.get("/{user_id}/{goal_id}")
async def api_get_goal(
    user_id: str,
    goal_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get a single goal with its AI roadmap."""
    goal = await get_goal(goal_id, user_id, db)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return goal


@router.patch("/{user_id}/{goal_id}/progress")
async def api_update_progress(
    user_id: str,
    goal_id: str,
    update: GoalProgressUpdate,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Update the progress percentage of a goal."""
    try:
        goal = await update_progress(goal_id, user_id, update, db)
        return goal
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{user_id}/{goal_id}")
async def api_delete_goal(
    user_id: str,
    goal_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Delete a goal."""
    await delete_goal(goal_id, user_id, db)
    return {"message": "Goal deleted."}


@router.post("/{user_id}/simulate")
async def api_simulate_scenario(
    user_id: str,
    request: ScenarioRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Simulate a what-if schedule change and project outcomes."""
    goals = await list_goals(user_id, db)

    async with db.execute(
        "SELECT profile_json FROM users WHERE user_id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    profile = json.loads(row["profile_json"]) if row else {}

    prompt = f"""
Simulate this scenario for the user:

SCENARIO: {request.scenario_description}
TIMEFRAME: {request.timeframe_days} days

CURRENT GOALS:
{json.dumps([g.model_dump(mode="json") for g in goals], indent=2)}

USER PROFILE:
{json.dumps(profile, indent=2)}

Return JSON:
{{
  "scenario": "...",
  "projected_goal_completion": {{"goal_title": "projected_date"}},
  "time_reallocation": {{"category": "hours_per_week"}},
  "tradeoffs": ["tradeoff1", "tradeoff2"],
  "recommendation": "..."
}}
""".strip()

    result = await run_planner(prompt)
    try:
        clean  = result.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json.loads(clean)
    except Exception:
        parsed = {"scenario": request.scenario_description, "recommendation": result}
    return parsed
