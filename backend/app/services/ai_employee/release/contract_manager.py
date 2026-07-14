"""Contract manager (Sprint 16.15 — validate the stable public backend contracts).

Defines :class:`ContractManager`, which validates that the backend's stable public
contracts are intact and ready to freeze — the public API method surface, the immutable
DTO contract, and the architecture dependency contract — by *reading* the frozen Sprint
16.13 :class:`ProductionValidationManager` (and the service/operations it wraps). It
never executes a workflow, changes behaviour, or modifies state.

The API contract is verified by introspection (each stable class still exposes its
public methods); the DTO and dependency contracts reuse the frozen platform's own
security and compatibility validators. It observes only: it validates and executes,
delegates, and stores nothing. Strictly additive to Sprints 1.x–16.14, whose modules
are left untouched.
"""

from app.services.ai_employee.release import common
from app.services.ai_employee.release.models import (
    ReleaseSeverity,
    ReleaseStatus,
)

# The stable public API contract: each class -> the methods it must keep exposing.
_SERVICE_METHODS = (
    "submit_task",
    "get_task",
    "list_tasks",
    "cancel_task",
    "pause_task",
    "resume_task",
    "health",
    "readiness",
)
_OPERATIONS_METHODS = (
    "authorize",
    "audit",
    "validate_environment",
    "diagnostics",
    "system_status",
    "submit_task",
)
_PRODUCTION_METHODS = (
    "validate",
    "full_validation",
    "readiness",
    "summary",
    "report",
)


class ContractManager:
    """Validates the stable public backend contracts (read-only, no execution).

    Constructed with an injected :class:`ProductionValidationManager` (constructor
    injection; it instantiates none). ``validate_api`` introspects the public method
    surface, ``validate_dtos`` checks DTO immutability, ``validate_dependencies`` checks
    the architecture dependency contract, and ``freeze_summary`` aggregates them into the
    contract-freeze verdict. It reads the platform surface only — it runs nothing.
    """

    def __init__(self, production) -> None:
        self.production = production

    def validate_api(self) -> ReleaseStatus:
        """Validate the stable public API method surface is intact."""
        operations = self.production.operations
        service = operations.service
        contracts = (
            ("AIEmployeeService", service, _SERVICE_METHODS),
            ("EnterpriseOperationsManager", operations, _OPERATIONS_METHODS),
            ("ProductionValidationManager", self.production, _PRODUCTION_METHODS),
        )
        issues = []
        checked = 0
        for class_name, obj, methods in contracts:
            for method in methods:
                checked += 1
                if not callable(getattr(obj, method, None)):
                    issues.append(
                        common.issue(
                            issue_id=f"contract-api-{class_name}-{method}",
                            message=(
                                f"missing public API method "
                                f"{class_name}.{method}"
                            ),
                            area="api",
                        )
                    )
        return common.status(
            "api_contract",
            issues,
            detail=f"{checked} public API method(s) validated",
            metadata={"methods_checked": checked},
        )

    def validate_dtos(self) -> ReleaseStatus:
        """Validate every platform DTO is immutable (frozen)."""
        offenders = self.production.security.mutable_dto_offenders()
        issues = [
            common.issue(
                issue_id=f"contract-dto-{offender}",
                message=f"DTO is not immutable: {offender}",
                area="dto",
            )
            for offender in offenders
        ]
        return common.status(
            "dto_contract",
            issues,
            detail=(
                "all DTOs frozen"
                if not offenders
                else f"{len(offenders)} mutable DTO(s)"
            ),
        )

    def validate_dependencies(self) -> ReleaseStatus:
        """Validate the architecture dependency contract (DI graph, modules, providers)."""
        result = self.production.compatibility.validate()
        issues = [
            common.issue(
                issue_id=f"contract-dep-{finding.issue_id}",
                message=finding.message,
                severity=(
                    ReleaseSeverity.BLOCKER
                    if finding.severity.value == "ERROR"
                    else ReleaseSeverity.WARNING
                ),
                area="dependency",
            )
            for finding in result.issues
        ]
        return common.status(
            "dependency_contract", issues, detail=result.detail
        )

    def freeze_summary(self) -> ReleaseStatus:
        """Aggregate the API, DTO, and dependency contracts into the freeze verdict."""
        api = self.validate_api()
        dtos = self.validate_dtos()
        dependencies = self.validate_dependencies()
        issues = [*api.issues, *dtos.issues, *dependencies.issues]
        return common.status(
            "contracts",
            issues,
            detail=(
                "contracts frozen"
                if not common.blockers(issues)
                else "contracts not freezable"
            ),
            metadata={
                "api_passed": api.passed,
                "dtos_passed": dtos.passed,
                "dependencies_passed": dependencies.passed,
            },
        )
