"""
DayPilot - Schedule Service
"""

import json
import uuid
from datetime import date, datetime
from typing import Optional
import aiosqlite

from agentz.planner_agent import run_planner
from models.schemas import (
    DailySchedule, TimeBlock, ScheduleGenerateRequest,
    TaskStatusUpdate,
)


async def generate_schedule(
    request: ScheduleGenerateRequest,
    db: aiosqlite.Connection,
) -> DailySchedule:
    """Generate an AI-optimized daily schedule, persist it, and return it."""

    # 1. Fetch user profile
    async with db.execute(
        "SELECT profile_json FROM users WHERE user_id = ?", (request.user_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise ValueError(f"User {request.user_id} not found")
    profile_data = json.loads(row["profile_json"])

    # 2. Fetch active goals
    query  = "SELECT * FROM goals WHERE user_id = ? AND status = 'active'"
    params = [request.user_id]
    if request.goals:
        placeholders = ",".join("?" * len(request.goals))
        query  += f" AND goal_id IN ({placeholders})"
        params.extend(request.goals)

    async with db.execute(query, params) as cur:
        goal_rows = await cur.fetchall()

    goals_data = [
        {
            "goal_id":               r["goal_id"],
            "title":                 r["title"],
            "category":              r["category"],
            "priority":              r["priority"],
            "target_date":           r["target_date"],
            "daily_time_budget_min": r["daily_time_budget_min"],
            "progress_percent":      r["progress_percent"],
        }
        for r in goal_rows
    ]

    # 3. Build prompt
    prompt = f"""
Generate a complete time-blocked daily schedule for {request.date.isoformat()}.

USER PROFILE:
{json.dumps(profile_data, indent=2)}

ACTIVE GOALS:
{json.dumps(goals_data, indent=2)}

EXTRA CONTEXT:
{request.context or "None"}

Return a JSON object with this exact schema:
{{
  "time_blocks": [
    {{
      "block_id": "<uuid>",
      "title": "<task name>",
      "description": "<brief description>",
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "category": "<work|study|fitness|meal|break|personal>",
      "goal_id": "<goal_id or null>",
      "priority": "<low|medium|high|urgent>",
      "energy_required": "<low|medium|high>",
      "status": "pending",
      "is_flexible": true
    }}
  ],
  "total_work_hours": <float>,
  "ai_notes": "<scheduling rationale>"
}}

Rules:
- Sort blocks chronologically
- Start from wake_time, end by sleep_time
- Include meals and breaks
- Cluster high-energy tasks in peak_energy_period
- Never schedule back-to-back focus blocks over 90 minutes without a break
- Assign block_id as a new UUID for each block
""".strip()

    # 4. Call AI agent
    ai_response = await run_planner(prompt)

    # 5. Parse response
    try:
        clean  = ai_response.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json.loads(clean)
    except Exception:
        parsed = {"time_blocks": [], "total_work_hours": 0.0, "ai_notes": "Parsing failed."}

    schedule_id = str(uuid.uuid4())
    now_str     = datetime.utcnow().isoformat()

    for block in parsed.get("time_blocks", []):
        if not block.get("block_id"):
            block["block_id"] = str(uuid.uuid4())

    # 6. Persist
    await db.execute(
        """
        INSERT OR REPLACE INTO schedules
        (schedule_id, user_id, date, time_blocks, total_work_hrs, ai_notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            schedule_id,
            request.user_id,
            request.date.isoformat(),
            json.dumps(parsed.get("time_blocks", [])),
            parsed.get("total_work_hours", 0.0),
            parsed.get("ai_notes"),
            now_str,
        ),
    )
    await db.commit()

    blocks = [TimeBlock(**b) for b in parsed.get("time_blocks", [])]
    return DailySchedule(
        schedule_id=schedule_id,
        user_id=request.user_id,
        date=request.date,
        time_blocks=blocks,
        total_work_hours=parsed.get("total_work_hours", 0.0),
        ai_notes=parsed.get("ai_notes"),
        created_at=datetime.utcnow(),
    )


async def get_schedule(
    user_id: str,
    target_date: date,
    db: aiosqlite.Connection,
) -> Optional[DailySchedule]:
    """Retrieve an existing schedule from the DB."""
    async with db.execute(
        "SELECT * FROM schedules WHERE user_id = ? AND date = ?",
        (user_id, target_date.isoformat()),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    blocks = [TimeBlock(**b) for b in json.loads(row["time_blocks"])]
    return DailySchedule(
        schedule_id=row["schedule_id"],
        user_id=row["user_id"],
        date=date.fromisoformat(row["date"]),
        time_blocks=blocks,
        total_work_hours=row["total_work_hrs"],
        ai_notes=row["ai_notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


async def update_task_status(
    user_id: str,
    update: TaskStatusUpdate,
    db: aiosqlite.Connection,
) -> dict:
    """Update a single time block's status within today's schedule."""
    today = date.today().isoformat()
    async with db.execute(
        "SELECT schedule_id, time_blocks FROM schedules WHERE user_id = ? AND date = ?",
        (user_id, today),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise ValueError("No schedule found for today.")

    blocks  = json.loads(row["time_blocks"])
    updated = False
    for b in blocks:
        if b["block_id"] == update.block_id:
            b["status"] = update.status
            if update.completion_note:
                b["completion_note"] = update.completion_note
            if update.actual_duration_minutes:
                b["actual_duration_minutes"] = update.actual_duration_minutes
            updated = True
            break

    if not updated:
        raise ValueError(f"Block {update.block_id} not found in today's schedule.")

    await db.execute(
        "UPDATE schedules SET time_blocks = ? WHERE schedule_id = ?",
        (json.dumps(blocks), row["schedule_id"]),
    )
    await db.commit()
    return {"block_id": update.block_id, "new_status": update.status}


async def adaptive_reschedule_today(
    user_id: str,
    db: aiosqlite.Connection,
) -> DailySchedule:
    """Detect missed blocks and reschedule the rest of the day."""
    today    = date.today()
    schedule = await get_schedule(user_id, today, db)
    if not schedule:
        raise ValueError("No schedule found for today.")

    now_str  = datetime.now().strftime("%H:%M")
    missed   = [
        b for b in schedule.time_blocks
        if b.status in ("pending", "skipped") and b.end_time < now_str
    ]
    remaining = [
        b for b in schedule.time_blocks
        if b.end_time >= now_str and b.status == "pending"
    ]

    if not missed:
        return schedule

    prompt = f"""
The user has missed {len(missed)} scheduled blocks today.
Current time: {now_str}

MISSED BLOCKS:
{json.dumps([b.model_dump() for b in missed], indent=2)}

REMAINING PENDING BLOCKS:
{json.dumps([b.model_dump() for b in remaining], indent=2)}

Reorganize the remaining blocks into the rest of the day.
Keep high-priority items. Drop or defer low-priority ones if time is tight.
Return JSON: {{"time_blocks": [...], "total_work_hours": float, "ai_notes": "..."}}
Each block must keep its original block_id.
""".strip()

    ai_response = await run_planner(prompt)
    try:
        clean  = ai_response.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json.loads(clean)
    except Exception:
        parsed = {"time_blocks": [b.model_dump() for b in remaining], "ai_notes": "No change."}

    completed_blocks = [b for b in schedule.time_blocks if b.status == "completed"]
    new_blocks       = completed_blocks + [TimeBlock(**b) for b in parsed.get("time_blocks", [])]

    await db.execute(
        "UPDATE schedules SET time_blocks = ?, ai_notes = ? WHERE user_id = ? AND date = ?",
        (
            json.dumps([b.model_dump() for b in new_blocks]),
            parsed.get("ai_notes"),
            user_id,
            today.isoformat(),
        ),
    )
    await db.commit()

    schedule.time_blocks = new_blocks
    schedule.ai_notes    = parsed.get("ai_notes")
    return schedule
