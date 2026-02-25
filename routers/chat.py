"""DayPilot - AI Coach Chat Router"""

import json
import uuid
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from db.database import get_db
from models.schemas import ChatRequest, ChatResponse
from agentz.planner_agent import run_coach

router = APIRouter()


@router.post("/message")
async def api_chat(
    request: ChatRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Send a message to the DayPilot AI coach."""

    # Fetch context
    async with db.execute(
        "SELECT title, progress_percent, priority FROM goals WHERE user_id = ? AND status = 'active'",
        (request.user_id,),
    ) as cur:
        goal_rows = await cur.fetchall()

    target_date = request.context_date or date.today()
    async with db.execute(
        "SELECT time_blocks FROM schedules WHERE user_id = ? AND date = ?",
        (request.user_id, target_date.isoformat()),
    ) as cur:
        srow = await cur.fetchone()

    async with db.execute(
        "SELECT energy_level, mood_score, focus_score FROM daily_checkins WHERE user_id = ? ORDER BY date DESC LIMIT 3",
        (request.user_id,),
    ) as cur:
        checkin_rows = await cur.fetchall()

    context = {
        "goals":           [dict(g) for g in goal_rows],
        "today_schedule":  json.loads(srow["time_blocks"]) if srow else [],
        "recent_checkins": [dict(c) for c in checkin_rows],
        "date":            target_date.isoformat(),
    }

    history = [m.model_dump() for m in (request.conversation_history or [])]

    prompt = f"""
USER MESSAGE: {request.message}

USER CONTEXT:
{json.dumps(context, indent=2)}

CONVERSATION HISTORY:
{json.dumps(history, indent=2)}

Respond as DayPilot Coach. Be concise, actionable, and empathetic.
Return JSON: {{"reply": "...", "suggested_actions": ["action1", "action2"]}}
""".strip()

    result = await run_coach(prompt)

    # Persist conversation
    session_id = f"{request.user_id}_main"
    now_str    = datetime.utcnow().isoformat()
    new_history = history + [
        {"role": "user",      "content": request.message,        "timestamp": now_str},
        {"role": "assistant", "content": result.get("reply", ""), "timestamp": now_str},
    ]

    await db.execute(
        """
        INSERT INTO chat_sessions (session_id, user_id, history, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET history = excluded.history, updated_at = excluded.updated_at
        """,
        (session_id, request.user_id, json.dumps(new_history), now_str, now_str),
    )
    await db.commit()

    return ChatResponse(
        reply=result.get("reply", ""),
        suggested_actions=result.get("suggested_actions", []),
    )


@router.get("/{user_id}/history")
async def api_chat_history(
    user_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Retrieve conversation history."""
    session_id = f"{user_id}_main"
    async with db.execute(
        "SELECT history FROM chat_sessions WHERE session_id = ?", (session_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return {"history": []}
    return {"history": json.loads(row["history"])}


@router.delete("/{user_id}/history")
async def api_clear_history(
    user_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Clear the conversation history."""
    await db.execute("DELETE FROM chat_sessions WHERE user_id = ?", (user_id,))
    await db.commit()
    return {"message": "Chat history cleared."}
