"""Validation helpers (Sprint 16.13 — deterministic result/issue construction).

Small, pure factory helpers shared by the validators to build immutable
:class:`ValidationIssue` s and to fold a list of issues into a single
:class:`ValidationResult` with the correct :class:`ValidationStatus`. Centralising the
status rule keeps every validator's verdict consistent: any ``ERROR`` issue fails the
result (blocking), any ``WARNING`` (without an error) downgrades it to a warning, and
otherwise it passes.

These are pure functions: they build DTOs only and decide, delegate, and execute
nothing. Strictly additive to Sprints 1.x–16.12, whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.validation.models import (
    ValidationIssue,
    ValidationResult,
    ValidationScope,
    ValidationSeverity,
    ValidationStatus,
)


def issue(
    issue_id: str,
    message: str,
    severity: ValidationSeverity = ValidationSeverity.ERROR,
    component: str = "",
    detail: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> ValidationIssue:
    """Build an immutable :class:`ValidationIssue` (defaults to ``ERROR`` severity)."""
    return ValidationIssue(
        issue_id=issue_id,
        severity=severity,
        component=component,
        message=message,
        detail=detail,
        issue_metadata=dict(metadata or {}),
    )


def result(
    name: str,
    scope: ValidationScope,
    issues: List[ValidationIssue],
    detail: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> ValidationResult:
    """Fold ``issues`` into a :class:`ValidationResult` with the derived status.

    Any ``ERROR`` issue makes the result ``FAILED`` (not passed); otherwise any
    ``WARNING`` makes it ``WARNING`` (passed); otherwise it is ``PASSED``. Deterministic.
    """
    errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
    warnings = [
        i for i in issues if i.severity == ValidationSeverity.WARNING
    ]
    if errors:
        status = ValidationStatus.FAILED
    elif warnings:
        status = ValidationStatus.WARNING
    else:
        status = ValidationStatus.PASSED
    return ValidationResult(
        name=name,
        scope=scope,
        status=status,
        passed=not errors,
        issues=list(issues),
        detail=detail or status.value,
        result_metadata=dict(metadata or {}),
    )


def blocking_issues(results: List[ValidationResult]) -> List[ValidationIssue]:
    """Return every ``ERROR``-severity issue across ``results`` (the blockers)."""
    blockers: List[ValidationIssue] = []
    for res in results:
        blockers.extend(
            i for i in res.issues if i.severity == ValidationSeverity.ERROR
        )
    return blockers
