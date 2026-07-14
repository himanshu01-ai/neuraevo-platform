"""Configuration auditor (Sprint 16.15 — audit configuration for release).

Defines :class:`ConfigurationAuditor`, which audits the backend's operational
configuration for release — completeness, default values, required configuration, and
environment compatibility — by *reading* the frozen Sprint 16.11
:class:`EnterpriseOperationsManager`'s configuration surface. It never executes a
workflow, changes behaviour, or modifies state.

The effective configuration is loaded (a pure read of the defaults) and validated
through the operations manager's own configuration validator; the audit adds an
environment-compatibility check. It observes only: it audits and executes, delegates,
and stores nothing. Strictly additive to Sprints 1.x–16.14, whose modules are left
untouched.
"""

from typing import List

from app.services.ai_employee.release import common
from app.services.ai_employee.release.models import (
    ConfigurationAudit,
    ReleaseIssue,
    ReleaseSeverity,
)

# The configuration key that must name the deployment environment.
_ENVIRONMENT_KEY = "environment"


class ConfigurationAuditor:
    """Audits operational configuration completeness for release (read-only).

    Constructed with an injected :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). ``validate`` loads the effective configuration,
    validates it, and checks environment compatibility, returning a
    :class:`ConfigurationAudit`. It reads the configuration surface only — it changes no
    configuration and runs nothing.
    """

    def __init__(self, operations) -> None:
        self.operations = operations

    def validate(self) -> ConfigurationAudit:
        """Return the :class:`ConfigurationAudit` for the operational configuration."""
        config = self.operations.configuration.load()
        report = self.operations.validate_configuration()
        required_present = not any(
            "required key" in problem for problem in report.issues
        )
        environment_compatible = bool(config.get(_ENVIRONMENT_KEY))

        issues: List[ReleaseIssue] = [
            common.issue(
                issue_id=f"configuration-issue-{index}",
                message=f"configuration issue: {problem}",
                area="configuration",
            )
            for index, problem in enumerate(report.issues)
        ]
        issues.extend(
            common.issue(
                issue_id=f"configuration-warning-{index}",
                message=f"configuration warning: {warning}",
                severity=ReleaseSeverity.WARNING,
                area="configuration",
            )
            for index, warning in enumerate(report.warnings)
        )
        if not environment_compatible:
            issues.append(
                common.issue(
                    issue_id="configuration-environment",
                    message="deployment environment is not configured",
                    area="configuration",
                )
            )

        return ConfigurationAudit(
            ok=not common.blockers(issues),
            complete=report.valid,
            required_present=required_present,
            environment_compatible=environment_compatible,
            defaults=dict(config),
            issues=issues,
            audit_metadata={"validated_keys": len(config)},
        )
