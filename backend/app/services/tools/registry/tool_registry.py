"""Tool Registry (Sprint 11.2 — catalogue of registered ToolProviders).

Maintains the set of registered :class:`ToolProvider` instances so a future
orchestrator can ask "what tools exist?". It stores providers and nothing else:
it never executes, validates, plans, permissions, injects, creates, modifies,
retries, logs, caches, or imports SDKs. Purely a read/lookup catalogue over the
providers it is given.
"""

from typing import Dict, List

from app.services.tools.providers.base import ToolProvider


class ToolRegistry:
    """A catalogue of registered tool providers, keyed by ``tool_name``.

    Holds only ``self.providers`` — no globals, no singleton, no cache. Each
    provider's ``tool_name`` is unique; registering a duplicate raises
    ``ValueError``. Provider objects are stored as given and never modified.
    """

    def __init__(self, providers: List[ToolProvider]) -> None:
        # Build a fresh internal list so the caller's list is never mutated;
        # register() enforces the unique-tool_name invariant on every entry.
        self.providers: List[ToolProvider] = []
        for provider in providers:
            self.register(provider)

    def register(self, provider: ToolProvider) -> None:
        """Add ``provider``; raise ``ValueError`` if its ``tool_name`` exists.

        The provider object is stored unchanged. This is the only mutation the
        registry performs — it never touches the provider itself.
        """
        if self.has_tool(provider.tool_name):
            raise ValueError(
                f"Tool already registered: {provider.tool_name}"
            )
        self.providers.append(provider)

    def list_tools(self) -> List[Dict[str, str]]:
        """Return plain metadata for every registered tool.

        Each entry is a plain ``{"tool_name": ..., "description": ...}`` dict —
        provider objects are never exposed.
        """
        return [
            {
                "tool_name": provider.tool_name,
                "description": provider.description,
            }
            for provider in self.providers
        ]

    def get_tool(self, tool_name: str) -> ToolProvider:
        """Return the provider registered under ``tool_name``.

        Raises ``KeyError`` if no provider is registered under that name.
        """
        for provider in self.providers:
            if provider.tool_name == tool_name:
                return provider
        raise KeyError(tool_name)

    def has_tool(self, tool_name: str) -> bool:
        """Return whether a provider with ``tool_name`` is registered."""
        return any(
            provider.tool_name == tool_name for provider in self.providers
        )
