"""Dependency auditor (Sprint 16.15 — audit dependencies and module integrity).

Defines :class:`DependencyAuditor`, which audits the backend's dependencies for release
— core dependency versions, duplicate installed packages, the architecture dependency
boundaries, and module integrity — by *reading* the environment metadata and the frozen
Sprint 16.13 :class:`ProductionValidationManager`. It never executes a workflow, changes
behaviour, or modifies state.

Versions are read from :mod:`importlib.metadata` (stdlib — no external package manager),
architecture boundaries reuse the platform's security validator (no forbidden import),
and module integrity reuses the compatibility validator. It observes only: it audits and
executes, delegates, and stores nothing. Strictly additive to Sprints 1.x–16.14, whose
modules are left untouched.
"""

import sys
from typing import Dict, List

from app.services.ai_employee.release import common
from app.services.ai_employee.release.models import (
    DependencyReport,
    ReleaseIssue,
    ReleaseSeverity,
)

# The core runtime dependency the DTO contract relies on, and its minimum major.
_PYDANTIC = "pydantic"
_PYDANTIC_MIN_MAJOR = 2


class DependencyAuditor:
    """Audits dependency versions, duplicates, and module integrity (read-only).

    Constructed with an injected :class:`ProductionValidationManager` (constructor
    injection; it instantiates none). ``dependency_versions`` reads the core versions;
    ``validate`` audits versions, duplicate packages, architecture boundaries, and module
    integrity into a :class:`DependencyReport`. It reads environment metadata and the
    platform validators only — it installs nothing and runs nothing.
    """

    def __init__(self, production) -> None:
        self.production = production

    def dependency_versions(self) -> Dict[str, str]:
        """Return the core dependency versions (Python and pydantic)."""
        return {
            "python": "%d.%d.%d" % sys.version_info[:3],
            _PYDANTIC: self._version(_PYDANTIC),
        }

    def duplicate_packages(self) -> List[str]:
        """Return any duplicated installed distribution names (empty when clean)."""
        try:
            import importlib.metadata as metadata

            seen: Dict[str, int] = {}
            for distribution in metadata.distributions():
                name = (distribution.metadata.get("Name") or "").lower()
                if name:
                    seen[name] = seen.get(name, 0) + 1
            return sorted(name for name, count in seen.items() if count > 1)
        except Exception:  # noqa: BLE001 - a metadata read failure is non-fatal
            return []

    def validate(self) -> DependencyReport:
        """Return the :class:`DependencyReport` for the backend dependencies."""
        versions = self.dependency_versions()
        duplicates = self.duplicate_packages()
        module_ok = self.production.compatibility.validate().passed
        issues: List[ReleaseIssue] = []

        issues.extend(self._version_issues(versions))
        if not module_ok:
            issues.append(
                common.issue(
                    issue_id="dependency-module-integrity",
                    message="module integrity check failed",
                    area="dependency",
                )
            )
        for filename, module in self.production.security.forbidden_import_offenders():
            issues.append(
                common.issue(
                    issue_id=f"dependency-arch-{filename}-{module}",
                    message=(
                        f"architecture dependency violation: {module} "
                        f"in {filename}"
                    ),
                    area="dependency",
                )
            )
        for duplicate in duplicates:
            issues.append(
                common.issue(
                    issue_id=f"dependency-duplicate-{duplicate}",
                    message=f"duplicate installed package: {duplicate}",
                    severity=ReleaseSeverity.WARNING,
                    area="dependency",
                )
            )

        return DependencyReport(
            ok=not common.blockers(issues),
            versions=versions,
            duplicates=duplicates,
            module_integrity=module_ok,
            issues=issues,
            report_metadata={"provider_isolation": (
                self.production.security.provider_isolation_ok()
            )},
        )

    # --- helpers ---------------------------------------------------------
    def _version_issues(
        self, versions: Dict[str, str]
    ) -> List[ReleaseIssue]:
        """Return an issue when the core pydantic dependency is missing or too old."""
        raw = versions.get(_PYDANTIC, "")
        if not raw:
            return [
                common.issue(
                    issue_id="dependency-pydantic-missing",
                    message="core dependency pydantic is not installed",
                    area="dependency",
                )
            ]
        try:
            major = int(raw.split(".")[0])
        except (ValueError, IndexError):
            major = 0
        if major < _PYDANTIC_MIN_MAJOR:
            return [
                common.issue(
                    issue_id="dependency-pydantic-version",
                    message=(
                        f"pydantic {raw} is below the required major "
                        f"{_PYDANTIC_MIN_MAJOR}"
                    ),
                    area="dependency",
                )
            ]
        return []

    @staticmethod
    def _version(package: str) -> str:
        """Return the installed version of ``package`` (empty when absent)."""
        try:
            import importlib.metadata as metadata

            return metadata.version(package)
        except Exception:  # noqa: BLE001 - absence is reported by the caller
            return ""
