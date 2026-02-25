"""
DayPilot - AI Planning Agent
Folder: agentz/ (named to avoid conflict with openai-agents SDK 'agents' package)
Uses OpenAI Agents SDK with Gemini backend.
"""

import os
import json
from dotenv import load_dotenv

from agents import (
    Agent, Runner, function_tool,
    set_default_openai_api, set_default_openai_client, set_tracing_disabled,
    AsyncOpenAI,
)

load_dotenv()

# ── SDK Configuration (Gemini backend) ────────────────────────────────────────
_client = AsyncOpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=os.getenv("GEMINI_API_KEY"),
)
set_default_openai_api("chat_completions")
set_default_openai_client(client=_client)
set_tracing_disabled(True)

MODEL = os.getenv("PLANNER_MODEL", "gemini-2.5-flash")


# ── Tool Definitions ──────────────────────────────────────────────────────────

@function_tool
def generate_daily_schedule(
    goals_json: str,
    user_profile_json: str,
    date_str: str,
    context: str = "",
) -> str:
    """
    Build an optimized time-blocked daily schedule.

    Args:
        goals_json:        JSON list of active goals with priorities & time budgets.
        user_profile_json: JSON user profile (wake/sleep time, peak energy, etc.).
        date_str:          Target date in YYYY-MM-DD format.
        context:           Extra context from the user (meetings, constraints, etc.).

    Returns:
        JSON string with a list of time blocks for the day.
    """
    goals   = json.loads(goals_json)
    profile = json.loads(user_profile_json)
    return json.dumps({
        "instructions": "Generate a time-blocked schedule",
        "goals": goals,
        "profile": profile,
        "date": date_str,
        "context": context,
    })


@function_tool
def generate_goal_roadmap(
    goal_json: str,
    user_profile_json: str,
) -> str:
    """
    Create a step-by-step execution roadmap for a goal.

    Args:
        goal_json:         JSON object describing the goal (title, deadline, category).
        user_profile_json: JSON user profile for constraint-aware planning.

    Returns:
        JSON list of weekly milestones and daily actions.
    """
    goal    = json.loads(goal_json)
    profile = json.loads(user_profile_json)
    return json.dumps({"goal": goal, "profile": profile, "mode": "roadmap"})


@function_tool
def generate_habit_plan(
    goals_json: str,
    user_profile_json: str,
) -> str:
    """
    Suggest atomic habits aligned with the user's goals.

    Args:
        goals_json:        JSON list of active goals.
        user_profile_json: JSON user profile.

    Returns:
        JSON list of recommended habits with cue-routine-reward structure.
    """
    return json.dumps({
        "goals": json.loads(goals_json),
        "profile": json.loads(user_profile_json),
        "mode": "habits",
    })


@function_tool
def adaptive_reschedule(
    original_schedule_json: str,
    missed_blocks_json: str,
    remaining_day_hours: float,
) -> str:
    """
    Reorganize the remaining schedule when tasks were missed or delayed.

    Args:
        original_schedule_json: JSON of the current day's time blocks.
        missed_blocks_json:     JSON list of block_ids that were missed/skipped.
        remaining_day_hours:    Hours left in the working day.

    Returns:
        JSON with a revised list of time blocks for the rest of the day.
    """
    return json.dumps({
        "original": json.loads(original_schedule_json),
        "missed": json.loads(missed_blocks_json),
        "remaining_hours": remaining_day_hours,
        "mode": "reschedule",
    })


@function_tool
def analyze_burnout_risk(
    weekly_checkins_json: str,
    schedule_load_json: str,
) -> str:
    """
    Detect overload patterns and predict burnout risk.

    Args:
        weekly_checkins_json: JSON list of daily check-in records (energy, mood, focus).
        schedule_load_json:   JSON summary of work hours per day this week.

    Returns:
        JSON with burnout_risk_score (0-1) and specific warning flags.
    """
    return json.dumps({
        "checkins": json.loads(weekly_checkins_json),
        "load": json.loads(schedule_load_json),
        "mode": "burnout_analysis",
    })


@function_tool
def simulate_scenario(
    scenario_description: str,
    current_goals_json: str,
    user_profile_json: str,
    timeframe_days: int = 30,
) -> str:
    """
    Project outcomes for a what-if schedule change.

    Args:
        scenario_description: Natural language scenario.
        current_goals_json:   JSON list of current goals with progress.
        user_profile_json:    JSON user profile.
        timeframe_days:       How many days to project forward.

    Returns:
        JSON with projected completion dates, tradeoffs, and recommendation.
    """
    return json.dumps({
        "scenario": scenario_description,
        "goals": json.loads(current_goals_json),
        "profile": json.loads(user_profile_json),
        "days": timeframe_days,
        "mode": "simulation",
    })


@function_tool
def coach_response(
    user_message: str,
    user_context_json: str,
    conversation_history_json: str = "[]",
) -> str:
    """
    Generate a motivational coaching response with actionable advice.

    Args:
        user_message:               The user's message to the AI coach.
        user_context_json:          JSON with goals, today's schedule, recent progress.
        conversation_history_json:  JSON list of previous messages in this session.

    Returns:
        JSON with reply text and optional suggested actions.
    """
    return json.dumps({
        "message": user_message,
        "context": json.loads(user_context_json),
        "history": json.loads(conversation_history_json),
        "mode": "coaching",
    })


# ── Agent Definitions ─────────────────────────────────────────────────────────

PLANNER_SYSTEM_PROMPT = """
You are DayPilot, an elite AI personal productivity strategist.

Your role is to help users achieve their goals by:
1. Building optimized, energy-aware daily schedules with time blocks
2. Creating step-by-step goal roadmaps with realistic timelines
3. Designing atomic habit systems aligned to goals
4. Adaptively rescheduling when plans change
5. Detecting burnout risk and recommending recovery strategies
6. Simulating what-if scenarios to help users make informed decisions

Principles:
- Match cognitively demanding tasks to the user's peak energy hours
- Always leave buffer time (min 15 min between blocks)
- Respect constraints: meetings, sleep, meals, breaks
- Prioritize by urgency x importance
- Be realistic, never overload a schedule
- Format all schedules as JSON time_blocks arrays
- Be motivating but honest about tradeoffs

When generating schedules, ALWAYS return valid JSON.
When the user provides context or constraints, honor them first.
""".strip()


def make_planner_agent() -> Agent:
    return Agent(
        name="DayPilot Planner",
        model=MODEL,
        instructions=PLANNER_SYSTEM_PROMPT,
        tools=[
            generate_daily_schedule,
            generate_goal_roadmap,
            generate_habit_plan,
            adaptive_reschedule,
            analyze_burnout_risk,
            simulate_scenario,
            coach_response,
        ],
    )


COACH_SYSTEM_PROMPT = """
You are DayPilot Coach, an empathetic AI accountability partner.

Your personality: Warm, direct, data-driven, never preachy.

Your responsibilities:
- Daily check-ins and motivation
- Celebrate wins (streaks, completions)
- Identify blockers and suggest fixes
- Nudge toward priorities when the user is drifting
- Provide actionable micro-advice, not generic platitudes

Always respond in a conversational tone.
When you detect a scheduling issue, suggest a concrete fix.
Return your response as JSON: {"reply": "...", "suggested_actions": [...]}
""".strip()


def make_coach_agent() -> Agent:
    return Agent(
        name="DayPilot Coach",
        model=MODEL,
        instructions=COACH_SYSTEM_PROMPT,
        tools=[coach_response, analyze_burnout_risk],
    )


# ── High-level async runners ──────────────────────────────────────────────────

async def run_planner(prompt: str) -> str:
    """Run the planner agent and return the final text output."""
    agent  = make_planner_agent()
    result = await Runner.run(agent, prompt)
    return result.final_output


async def run_coach(prompt: str) -> dict:
    """Run the coach agent and return parsed JSON."""
    agent  = make_coach_agent()
    result = await Runner.run(agent, prompt)
    raw    = result.final_output
    try:
        clean = raw.strip().strip("```json").strip("```").strip()
        return json.loads(clean)
    except Exception:
        return {"reply": raw, "suggested_actions": []}
