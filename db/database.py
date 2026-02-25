"""
DayPilot - Database (SQLite + aiosqlite for async I/O)
"""

import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "daypilot.db")


async def get_db():
    """Dependency: yields a DB connection."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db():
    """Create tables on startup."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS users (
                user_id       TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                profile_json  TEXT NOT NULL,
                created_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS goals (
                goal_id               TEXT PRIMARY KEY,
                user_id               TEXT NOT NULL,
                title                 TEXT NOT NULL,
                description           TEXT,
                category              TEXT NOT NULL,
                priority              TEXT NOT NULL,
                target_date           TEXT,
                daily_time_budget_min INTEGER DEFAULT 60,
                milestones_json       TEXT DEFAULT '[]',
                roadmap_json          TEXT DEFAULT '[]',
                progress_percent      REAL  DEFAULT 0.0,
                status                TEXT  DEFAULT 'active',
                created_at            TEXT  NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS schedules (
                schedule_id    TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL,
                date           TEXT NOT NULL,
                time_blocks    TEXT NOT NULL,
                total_work_hrs REAL DEFAULT 0.0,
                ai_notes       TEXT,
                created_at     TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS habits (
                habit_id         TEXT PRIMARY KEY,
                user_id          TEXT NOT NULL,
                title            TEXT NOT NULL,
                description      TEXT,
                goal_id          TEXT,
                frequency        TEXT NOT NULL,
                preferred_time   TEXT,
                duration_minutes INTEGER DEFAULT 15,
                reminder         INTEGER DEFAULT 1,
                cue              TEXT,
                reward           TEXT,
                streak_count     INTEGER DEFAULT 0,
                completion_rate  REAL    DEFAULT 0.0,
                last_completed   TEXT,
                created_at       TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES habits(habit_id)
            );

            CREATE TABLE IF NOT EXISTS habit_logs (
                log_id     TEXT PRIMARY KEY,
                habit_id   TEXT NOT NULL,
                user_id    TEXT NOT NULL,
                date       TEXT NOT NULL,
                completed  INTEGER NOT NULL,
                note       TEXT,
                logged_at  TEXT NOT NULL,
                FOREIGN KEY (habit_id) REFERENCES habits(habit_id)
            );

            CREATE TABLE IF NOT EXISTS daily_checkins (
                checkin_id    TEXT PRIMARY KEY,
                user_id       TEXT NOT NULL,
                date          TEXT NOT NULL,
                energy_level  TEXT NOT NULL,
                mood_score    INTEGER NOT NULL,
                focus_score   INTEGER NOT NULL,
                notes         TEXT,
                created_at    TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                history    TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)
        await db.commit()
        print("[DB] Tables initialized ✅")
