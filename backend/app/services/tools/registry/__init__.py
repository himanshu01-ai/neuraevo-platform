"""Tool registry package (Sprint 11.2 — tool catalogue).

Exposes :class:`ToolRegistry`, which maintains the list of registered
:class:`~app.services.tools.providers.base.ToolProvider` instances so future
orchestrators can discover available tools. It stores providers only — no
execution, validation, permissions, planning, or dependency injection.
"""

from app.services.tools.registry.tool_registry import ToolRegistry

__all__ = ["ToolRegistry"]
