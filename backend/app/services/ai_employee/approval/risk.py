"""Approval risk model (Sprint 16.3 — configurable action → risk mapping).

Defines :class:`RiskModel`, the deterministic, *configurable* component that
assesses the :class:`ApprovalRiskLevel` of a requested action. It ships a default
mapping drawn from the sprint's examples (read/search/list are ``LOW``; create/
draft/branch are ``MEDIUM``; delete/commit/move are ``HIGH``; send/delete-repo/
payment are ``CRITICAL``) and lets a caller override or extend the mapping and the
fallback level at construction — the risk model is never hard-coded.

It holds no workflow state, executes nothing, and is deterministic: the same
action always assesses to the same level. Strictly additive to Sprints 1.x–16.2.
"""

from typing import Dict, Optional

from app.services.ai_employee.approval.models import ApprovalRiskLevel

# The default, override-able action → risk mapping (the sprint's examples). A
# caller may replace or extend it via :class:`RiskModel`'s constructor, so the
# risk model stays configurable rather than hard-coded.
DEFAULT_ACTION_RISK: Dict[str, ApprovalRiskLevel] = {
    # LOW — read-only, non-mutating
    "read_file": ApprovalRiskLevel.LOW,
    "search_email": ApprovalRiskLevel.LOW,
    "list_calendar": ApprovalRiskLevel.LOW,
    # MEDIUM — creates a draft/branch, reversible
    "create_event": ApprovalRiskLevel.MEDIUM,
    "draft_email": ApprovalRiskLevel.MEDIUM,
    "git_branch": ApprovalRiskLevel.MEDIUM,
    # HIGH — destructive or hard to reverse
    "delete_files": ApprovalRiskLevel.HIGH,
    "commit_code": ApprovalRiskLevel.HIGH,
    "move_repositories": ApprovalRiskLevel.HIGH,
    # CRITICAL — outward-facing or irreversible
    "send_email": ApprovalRiskLevel.CRITICAL,
    "delete_repository": ApprovalRiskLevel.CRITICAL,
    "payment": ApprovalRiskLevel.CRITICAL,
}


class RiskModel:
    """Assesses the deterministic risk level of a requested action (configurable).

    Constructed with an optional ``action_risk`` override map (merged over the
    default mapping) and an optional ``default_risk`` fallback for unknown actions
    (defaults to ``MEDIUM`` — unknown actions are treated cautiously). Stateless
    beyond its immutable mapping; ``assess`` is a pure lookup that executes
    nothing. Swapping the whole risk policy is a construction-time change with no
    impact on the policies or the engine.
    """

    def __init__(
        self,
        action_risk: Optional[Dict[str, ApprovalRiskLevel]] = None,
        default_risk: ApprovalRiskLevel = ApprovalRiskLevel.MEDIUM,
    ) -> None:
        self._action_risk: Dict[str, ApprovalRiskLevel] = {
            **DEFAULT_ACTION_RISK,
            **(action_risk or {}),
        }
        self._default_risk = default_risk

    def assess(self, requested_action: str) -> ApprovalRiskLevel:
        """Return the risk level of ``requested_action`` (fallback for unknowns)."""
        return self._action_risk.get(requested_action, self._default_risk)
