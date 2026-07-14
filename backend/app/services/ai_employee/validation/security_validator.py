"""Security validator (Sprint 16.13 — validate boundaries and isolation statically).

Defines :class:`SecurityValidator`, which validates the platform's security posture by
*statically inspecting* the AI Employee platform packages — never by scanning a network
or running a penetration test. It checks provider isolation (no LLM/provider SDK
imported), DTO immutability (every DTO is frozen), dependency boundaries and forbidden
imports (no Workflow Coordinator, capability, repository, database, web, or SDK import),
and service boundaries (no FastAPI/REST leakage).

It reads the packages' source with the :mod:`ast` module and inspects the DTO classes'
frozen config — it imports no scanner, contacts no host, and executes nothing. It
observes only: it validates and executes, delegates, and stores nothing. Strictly
additive to Sprints 1.x–16.12, whose modules are left untouched.
"""

import ast
import os
from typing import List, Tuple

from pydantic import BaseModel

from app.services.ai_employee.experience import models as experience_models
from app.services.ai_employee.operations import models as operations_models
from app.services.ai_employee.service import models as service_models
from app.services.ai_employee.validation import common
from app.services.ai_employee.validation import models as validation_models
from app.services.ai_employee.validation.models import (
    ValidationResult,
    ValidationScope,
    ValidationSeverity,
)

# Imports no platform package may make (dependency + service + provider boundaries).
_FORBIDDEN_MODULES = {
    "workflow_coordinator",
    "browser_capability",
    "python_capability",
    "filesystem_capability",
    "email_capability",
    "calendar_capability",
    "github_capability",
    "repository",
    "fastapi",
    "starlette",
    "sqlalchemy",
    "database",
    "threading",
    "asyncio",
    "socket",
    "requests",
    "httpx",
    "anthropic",
    "openai",
    "boto3",
    "prometheus_client",
}

# The subset that specifically breaks provider isolation (an LLM/provider SDK).
_PROVIDER_MODULES = {"anthropic", "openai", "boto3", "cohere", "google"}

# The DTO model modules whose classes must all be frozen (immutable).
_MODEL_MODULES = (
    validation_models,
    operations_models,
    experience_models,
    service_models,
)


class SecurityValidator:
    """Validates boundaries and isolation by static inspection (no execution).

    Stateless. ``forbidden_import_offenders`` scans the platform packages for a
    forbidden import; ``mutable_dto_offenders`` finds any non-frozen DTO;
    ``provider_isolation_ok`` reports whether any provider SDK is imported; and
    ``validate`` folds them into the security :class:`ValidationResult`. It reads source
    and class config only — it contacts no host and runs nothing.
    """

    def __init__(self) -> None:
        # Resolve each package directory once from its imported module object.
        import app.services.ai_employee.experience as experience_pkg
        import app.services.ai_employee.operations as operations_pkg
        import app.services.ai_employee.service as service_pkg
        import app.services.ai_employee.validation as validation_pkg

        self._package_dirs = {
            "validation": os.path.dirname(validation_pkg.__file__),
            "operations": os.path.dirname(operations_pkg.__file__),
            "experience": os.path.dirname(experience_pkg.__file__),
            "service": os.path.dirname(service_pkg.__file__),
        }

    # --- checks ----------------------------------------------------------
    def forbidden_import_offenders(self) -> List[Tuple[str, str]]:
        """Return every ``(file, module)`` forbidden import across the packages."""
        offenders: List[Tuple[str, str]] = []
        for package_dir in self._package_dirs.values():
            for filename in sorted(os.listdir(package_dir)):
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(package_dir, filename)
                for name in self._imported_modules(path):
                    tail = name.rsplit(".", 1)[-1]
                    if tail in _FORBIDDEN_MODULES:
                        offenders.append((filename, name))
        return offenders

    def provider_isolation_ok(self) -> bool:
        """Return whether no provider SDK is imported by any platform package."""
        for _, module in self.forbidden_import_offenders():
            tail = module.rsplit(".", 1)[-1]
            if tail in _PROVIDER_MODULES:
                return False
        return True

    def mutable_dto_offenders(self) -> List[str]:
        """Return the qualified names of any DTO class that is not frozen."""
        offenders: List[str] = []
        for module in _MODEL_MODULES:
            for name in sorted(dir(module)):
                obj = getattr(module, name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BaseModel)
                    and obj is not BaseModel
                    and obj.__module__ == module.__name__
                ):
                    if not obj.model_config.get("frozen", False):
                        offenders.append(f"{module.__name__}.{name}")
        return offenders

    def validate(self) -> ValidationResult:
        """Return the aggregate security :class:`ValidationResult`."""
        issues = []
        for filename, module in self.forbidden_import_offenders():
            # A provider SDK is an isolation break; any other forbidden import is a
            # dependency/service-boundary break. Both block readiness (ERROR).
            provider = module.rsplit(".", 1)[-1] in _PROVIDER_MODULES
            issues.append(
                common.issue(
                    issue_id=f"security-import-{filename}-{module}",
                    message=f"forbidden import {module} in {filename}",
                    severity=ValidationSeverity.ERROR,
                    component=(
                        "provider-isolation"
                        if provider
                        else "dependency-boundary"
                    ),
                )
            )
        for offender in self.mutable_dto_offenders():
            issues.append(
                common.issue(
                    issue_id=f"security-mutable-{offender}",
                    message=f"DTO is not immutable: {offender}",
                    severity=ValidationSeverity.ERROR,
                    component="dto-immutability",
                )
            )
        return common.result(
            name="security boundaries",
            scope=ValidationScope.SECURITY,
            issues=issues,
            detail=(
                "boundaries and isolation intact"
                if not issues
                else f"{len(issues)} security concern(s)"
            ),
            metadata={
                "provider_isolation": self.provider_isolation_ok(),
                "scanned_packages": sorted(self._package_dirs),
            },
        )

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _imported_modules(path: str) -> List[str]:
        """Return the module names imported by the Python file at ``path``."""
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        names: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            elif isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
        return names
