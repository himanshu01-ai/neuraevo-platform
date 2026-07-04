"""Planner providers package (Sprint 11.4 — abstraction only).

Exposes the abstract :class:`PlannerProvider` contract. No concrete planner
provider is implemented in this sprint — only the interface future sprints will
implement.
"""

from app.services.planner.providers.base import PlannerProvider

__all__ = ["PlannerProvider"]
