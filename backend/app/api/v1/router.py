"""Aggregate router for API v1.

Sub-routers are registered here so that ``main`` only needs to mount a single
``api_router``. New feature routers should be included in this module as they
are implemented.
"""

from fastapi import APIRouter

from app.api.v1 import (
    ai_context,
    auth,
    blueprint_generation,
    blueprint_versions,
    blueprints,
    conversation_context,
    conversation_generation,
    conversation_hub,
    conversation_runtime,
    conversations,
    employees,
    health,
    interview_answers,
    interview_questions,
    interview_session_questions,
    interview_sessions,
    memory,
    memory_context,
    memory_links,
    messages,
    tasks,
    workflow_executions,
    workflows,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(employees.router)
api_router.include_router(workflows.router)
api_router.include_router(workflow_executions.router)
api_router.include_router(tasks.router)
api_router.include_router(memory.router)
api_router.include_router(memory_context.router)
api_router.include_router(memory_links.router)
api_router.include_router(conversations.router)
api_router.include_router(conversation_hub.router)
api_router.include_router(messages.router)
api_router.include_router(conversation_context.router)
api_router.include_router(conversation_generation.router)
api_router.include_router(conversation_runtime.router)
api_router.include_router(ai_context.router)
api_router.include_router(blueprints.router)
api_router.include_router(blueprint_generation.router)
api_router.include_router(blueprint_versions.router)
api_router.include_router(interview_questions.router)
api_router.include_router(interview_answers.router)
api_router.include_router(interview_sessions.router)
api_router.include_router(interview_session_questions.router)
