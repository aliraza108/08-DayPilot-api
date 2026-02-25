"""
DayPilot - AI Personalized Life & Productivity Planner
FastAPI Backend with OpenAI Agents SDK (Gemini compatible)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routers import schedule, goals, habits, progress, chat, users
from db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="DayPilot AI Planner API",
    description="AI-powered personalized life & productivity planner",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(users.router,    prefix="/api/users",    tags=["Users"])
app.include_router(schedule.router, prefix="/api/schedule", tags=["Schedule"])
app.include_router(goals.router,    prefix="/api/goals",    tags=["Goals"])
app.include_router(habits.router,   prefix="/api/habits",   tags=["Habits"])
app.include_router(progress.router, prefix="/api/progress", tags=["Progress"])
app.include_router(chat.router,     prefix="/api/chat",     tags=["AI Coach"])


@app.get("/")
async def root():
    return {"message": "DayPilot AI Planner API is running 🚀"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
