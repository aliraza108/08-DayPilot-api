"""
DayPilot - Data Models (Pydantic)
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime, date


# ─── Enums ────────────────────────────────────────────────────────────────────

class EnergyLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class GoalCategory(str, Enum):
    CAREER   = "career"
    FITNESS  = "fitness"
    LEARNING = "learning"
    FINANCE  = "finance"
    HEALTH   = "health"
    CREATIVE = "creative"
    SOCIAL   = "social"
    OTHER    = "other"


class Priority(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    SKIPPED     = "skipped"
    RESCHEDULED = "rescheduled"


class HabitFrequency(str, Enum):
    DAILY    = "daily"
    WEEKLY   = "weekly"
    WEEKDAYS = "weekdays"
    CUSTOM   = "custom"


# ─── User Profile ─────────────────────────────────────────────────────────────

class UserProfileCreate(BaseModel):
    name: str
    wake_time: str = "06:30"
    sleep_time: str = "22:30"
    peak_energy_period: str = "morning"
    available_hours_per_day: float = 8.0
    work_start: str = "09:00"
    work_end: str = "17:00"
    timezone: str = "UTC"
    deep_work_preference: bool = True
    break_frequency_minutes: int = 90


class UserProfile(UserProfileCreate):
    user_id: str


# ─── Goals ────────────────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: GoalCategory
    priority: Priority = Priority.MEDIUM
    target_date: Optional[date] = None
    daily_time_budget_minutes: int = 60
    milestones: Optional[List[str]] = []


class Goal(GoalCreate):
    goal_id: str
    user_id: str
    created_at: datetime
    progress_percent: float = 0.0
    status: str = "active"
    roadmap: Optional[List[dict]] = []


class GoalProgressUpdate(BaseModel):
    progress_percent: float
    note: Optional[str] = None


# ─── Daily Schedule ───────────────────────────────────────────────────────────

class TimeBlock(BaseModel):
    block_id: str
    title: str
    description: Optional[str] = None
    start_time: str
    end_time: str
    category: str
    goal_id: Optional[str] = None
    priority: Priority = Priority.MEDIUM
    energy_required: EnergyLevel = EnergyLevel.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    is_flexible: bool = True


class DailySchedule(BaseModel):
    schedule_id: str
    user_id: str
    date: date
    time_blocks: List[TimeBlock]
    total_work_hours: float
    productivity_score: Optional[float] = None
    ai_notes: Optional[str] = None
    created_at: datetime


class ScheduleGenerateRequest(BaseModel):
    user_id: str
    date: date
    goals: List[str] = []
    force_regenerate: bool = False
    context: Optional[str] = None


class TaskStatusUpdate(BaseModel):
    block_id: str
    status: TaskStatus
    completion_note: Optional[str] = None
    actual_duration_minutes: Optional[int] = None


# ─── Habits ───────────────────────────────────────────────────────────────────

class HabitCreate(BaseModel):
    title: str
    description: Optional[str] = None
    goal_id: Optional[str] = None
    frequency: HabitFrequency = HabitFrequency.DAILY
    preferred_time: Optional[str] = None
    duration_minutes: int = 15
    reminder: bool = True
    cue: Optional[str] = None
    reward: Optional[str] = None


class Habit(HabitCreate):
    habit_id: str
    user_id: str
    created_at: datetime
    streak_count: int = 0
    completion_rate: float = 0.0
    last_completed: Optional[date] = None


class HabitCheckIn(BaseModel):
    habit_id: str
    completed: bool
    date: date
    note: Optional[str] = None


# ─── Progress & Analytics ─────────────────────────────────────────────────────

class DailyCheckIn(BaseModel):
    user_id: str
    date: date
    energy_level: EnergyLevel
    mood_score: int = Field(ge=1, le=10)
    focus_score: int = Field(ge=1, le=10)
    notes: Optional[str] = None


class ProgressSummary(BaseModel):
    user_id: str
    period: str
    completion_rate: float
    goals_on_track: List[str]
    goals_at_risk: List[str]
    habit_streaks: dict
    time_allocation: dict
    productivity_trend: List[float]
    burnout_risk_score: float
    ai_insights: Optional[str] = None


# ─── AI Chat / Coach ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    user_id: str
    message: str
    conversation_history: Optional[List[ChatMessage]] = []
    context_date: Optional[date] = None


class ChatResponse(BaseModel):
    reply: str
    suggested_actions: Optional[List[str]] = []


# ─── Scenario Simulation ──────────────────────────────────────────────────────

class ScenarioRequest(BaseModel):
    user_id: str
    scenario_description: str
    timeframe_days: int = 30


class ScenarioResult(BaseModel):
    scenario: str
    projected_goal_completion: dict
    time_reallocation: dict
    tradeoffs: List[str]
    recommendation: str
