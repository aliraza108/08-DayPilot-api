"""DayPilot - User Router"""

import json
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from db.database import get_db
from models.schemas import UserProfileCreate

router = APIRouter()


@router.post("/register")
async def api_register_user(
    profile: UserProfileCreate,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Register a new user and store their profile."""
    user_id = str(uuid.uuid4())
    now_str = datetime.utcnow().isoformat()

    profile_data           = profile.model_dump()
    profile_data["user_id"] = user_id

    await db.execute(
        "INSERT INTO users (user_id, name, profile_json, created_at) VALUES (?, ?, ?, ?)",
        (user_id, profile.name, json.dumps(profile_data), now_str),
    )
    await db.commit()
    return {"user_id": user_id, "message": f"Welcome to DayPilot, {profile.name}! 🚀"}


@router.get("/{user_id}")
async def api_get_user(
    user_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get user profile."""
    async with db.execute(
        "SELECT profile_json FROM users WHERE user_id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
    return json.loads(row["profile_json"])


@router.patch("/{user_id}")
async def api_update_user(
    user_id: str,
    profile: UserProfileCreate,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Update user profile."""
    async with db.execute(
        "SELECT profile_json FROM users WHERE user_id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")

    existing = json.loads(row["profile_json"])
    updated  = {**existing, **profile.model_dump()}

    await db.execute(
        "UPDATE users SET name = ?, profile_json = ? WHERE user_id = ?",
        (profile.name, json.dumps(updated), user_id),
    )
    await db.commit()
    return {"message": "Profile updated ✅", "profile": updated}
