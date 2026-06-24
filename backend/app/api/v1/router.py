"""Aggregate router for API v1.

Sub-routers are registered here so that ``main`` only needs to mount a single
``api_router``. New feature routers should be included in this module as they
are implemented.
"""

from fastapi import APIRouter

from app.api.v1 import auth, employees, health

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(employees.router)
