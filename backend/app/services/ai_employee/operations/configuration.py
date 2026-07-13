"""Configuration manager (Sprint 16.11 — validate platform configuration).

Defines :class:`ConfigurationManager`, which loads, validates, and exports the
platform's operational configuration deterministically. ``load`` merges caller
overrides over the configured defaults; ``validate`` checks that every required key
is present and non-empty and flags unknown keys as warnings, returning an immutable
:class:`ConfigurationReport`; and ``export`` returns a deterministically ordered
copy.

It is deterministic and stateless (beyond its immutable defaults/required-key
config): it validates only and decides, delegates, and executes nothing. It never
touches the Workflow Coordinator, a capability, a repository, a database, an LLM
provider, a thread, or the network. Strictly additive to Sprints 1.x–16.10, whose
modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.operations.models import ConfigurationReport


class ConfigurationManager:
    """Loads, validates, and exports platform configuration (deterministic).

    Constructed with ``defaults`` (the base configuration) and ``required_keys`` (keys
    that must be present and non-empty). ``load`` merges overrides over the defaults;
    ``validate`` returns a :class:`ConfigurationReport` (invalid when a required key is
    missing/empty, with unknown keys as warnings); and ``export`` returns a
    key-sorted copy. Stateless beyond its immutable configuration; it runs nothing.
    """

    def __init__(
        self,
        defaults: Optional[Dict[str, Any]] = None,
        required_keys: Optional[List[str]] = None,
    ) -> None:
        self._defaults = dict(defaults or {})
        self._required = list(required_keys or [])

    def load(
        self, overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Return the effective configuration (defaults merged with ``overrides``)."""
        config = dict(self._defaults)
        config.update(overrides or {})
        return config

    def validate(self, config: Dict[str, Any]) -> ConfigurationReport:
        """Return a :class:`ConfigurationReport` for ``config`` (deterministic issues)."""
        if not isinstance(config, dict):
            return ConfigurationReport(
                valid=False,
                issues=["configuration must be a mapping"],
                settings={},
            )
        issues: List[str] = []
        for key in self._required:
            if key not in config:
                issues.append(f"missing required key: {key}")
            elif config[key] in (None, ""):
                issues.append(f"empty required key: {key}")
        known = set(self._defaults) | set(self._required)
        warnings = [
            f"unknown key: {key}"
            for key in config
            if known and key not in known
        ]
        return ConfigurationReport(
            valid=not issues,
            issues=issues,
            warnings=warnings,
            settings=dict(config),
        )

    def export(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return a deterministically key-ordered copy of ``config``."""
        return {key: config[key] for key in sorted(config)}
