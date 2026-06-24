"""Pydantic schema for aggregated memory statistics."""

from pydantic import BaseModel


class MemoryStatsResponse(BaseModel):
    """Aggregated memory counts and average importance for an employee."""

    total_memories: int
    permanent_count: int
    working_count: int
    learned_count: int
    average_importance_score: float
