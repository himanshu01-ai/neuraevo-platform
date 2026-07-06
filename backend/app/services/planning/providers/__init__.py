"""Planning providers package (Sprint 13.1).

Exposes the abstract :class:`PlanningProvider` contract and the deterministic,
provider-independent :class:`HeuristicPlanningProvider` default. An LLM-backed
provider can be added here later and swapped in at the composition root with no
change to the engine or its consumers.
"""

from app.services.planning.providers.base import PlanningProvider
from app.services.planning.providers.heuristic_planning_provider import (
    HeuristicPlanningProvider,
)

__all__ = ["PlanningProvider", "HeuristicPlanningProvider"]
