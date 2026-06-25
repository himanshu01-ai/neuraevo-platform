"""Aggregate router for API v1.

Sub-routers are registered here so that ``main`` only needs to mount a single
``api_router``. New feature routers should be included in this module as they
are implemented.
"""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    blueprints,
    employees,
    health,
    interview_answers,
    interview_questions,
    interview_sessions,
    memory,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(employees.router)
api_router.include_router(memory.router)
api_router.include_router(blueprints.router)
api_router.include_router(interview_questions.router)
api_router.include_router(interview_answers.router)
api_router.include_router(interview_sessions.router)
