"""Unit tests for the Sprint 11.2 Tool Registry (catalogue only).

Providers are lightweight stubs, so nothing is executed and no network/SDK is
touched. The tests verify registration (including duplicate rejection), the
plain-dict listing, lookup by name (and KeyError for unknown), membership,
that providers are never modified or executed/validated, constructor injection,
statelessness, and the composition-root DI wiring.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_tool_registry
"""

import unittest
from unittest.mock import MagicMock

from app.services.tools import ToolExecutionResult, ToolProvider
from app.services.tools.registry import ToolRegistry


class _StubProvider(ToolProvider):
    """Minimal concrete ToolProvider that records if it is ever called."""

    def __init__(self, tool_name: str, description: str = "") -> None:
        self.tool_name = tool_name
        self.description = description
        self.executed = False
        self.validated = False

    def validate(self, request) -> None:
        self.validated = True

    def execute(self, request) -> ToolExecutionResult:
        self.executed = True
        return ToolExecutionResult(success=True)


class ToolRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gmail = _StubProvider("gmail_stub", "stub A")
        self.calendar = _StubProvider("calendar_stub", "stub B")

    # --- empty registry --------------------------------------------------
    def test_empty_registry_has_no_tools(self):
        registry = ToolRegistry([])
        self.assertEqual(registry.list_tools(), [])
        self.assertEqual(registry.providers, [])
        self.assertFalse(registry.has_tool("anything"))

    # --- construction / registration ------------------------------------
    def test_constructor_registers_providers(self):
        registry = ToolRegistry([self.gmail, self.calendar])
        self.assertTrue(registry.has_tool("gmail_stub"))
        self.assertTrue(registry.has_tool("calendar_stub"))

    def test_register_adds_provider(self):
        registry = ToolRegistry([])
        registry.register(self.gmail)
        self.assertTrue(registry.has_tool("gmail_stub"))
        self.assertIs(registry.get_tool("gmail_stub"), self.gmail)

    def test_duplicate_registration_raises_value_error(self):
        registry = ToolRegistry([self.gmail])
        with self.assertRaises(ValueError):
            registry.register(_StubProvider("gmail_stub", "another"))

    def test_duplicate_in_constructor_raises_value_error(self):
        with self.assertRaises(ValueError):
            ToolRegistry([self.gmail, _StubProvider("gmail_stub")])

    # --- list_tools returns plain data ----------------------------------
    def test_list_tools_returns_plain_dicts(self):
        registry = ToolRegistry([self.gmail, self.calendar])
        tools = registry.list_tools()
        self.assertEqual(
            tools,
            [
                {"tool_name": "gmail_stub", "description": "stub A"},
                {"tool_name": "calendar_stub", "description": "stub B"},
            ],
        )
        for entry in tools:
            self.assertIsInstance(entry, dict)
            self.assertEqual(set(entry), {"tool_name", "description"})
            self.assertNotIsInstance(entry, ToolProvider)

    def test_list_tools_never_exposes_provider_objects(self):
        registry = ToolRegistry([self.gmail])
        for entry in registry.list_tools():
            self.assertNotIn(self.gmail, entry.values())

    # --- get_tool --------------------------------------------------------
    def test_get_tool_returns_provider(self):
        registry = ToolRegistry([self.gmail])
        self.assertIs(registry.get_tool("gmail_stub"), self.gmail)

    def test_get_tool_unknown_raises_key_error(self):
        registry = ToolRegistry([self.gmail])
        with self.assertRaises(KeyError):
            registry.get_tool("nope")

    # --- has_tool --------------------------------------------------------
    def test_has_tool_true(self):
        registry = ToolRegistry([self.gmail])
        self.assertTrue(registry.has_tool("gmail_stub"))

    def test_has_tool_false(self):
        registry = ToolRegistry([self.gmail])
        self.assertFalse(registry.has_tool("calendar_stub"))

    # --- providers not modified / no execution --------------------------
    def test_providers_not_modified(self):
        registry = ToolRegistry([self.gmail, self.calendar])
        # The stored provider objects are the same instances, untouched.
        self.assertIs(registry.get_tool("gmail_stub"), self.gmail)
        self.assertEqual(self.gmail.tool_name, "gmail_stub")
        self.assertEqual(self.gmail.description, "stub A")

    def test_input_list_not_mutated(self):
        original = [self.gmail, self.calendar]
        snapshot = list(original)
        registry = ToolRegistry(original)
        registry.register(_StubProvider("third"))
        # The caller's list is untouched; the registry uses its own list.
        self.assertEqual(original, snapshot)
        self.assertEqual(len(registry.providers), 3)

    def test_registry_never_executes_or_validates_providers(self):
        registry = ToolRegistry([self.gmail, self.calendar])
        registry.list_tools()
        registry.get_tool("gmail_stub")
        registry.has_tool("calendar_stub")
        for provider in (self.gmail, self.calendar):
            self.assertFalse(provider.executed)
            self.assertFalse(provider.validated)

    def test_registry_does_not_call_execute_or_validate_on_mock(self):
        provider = MagicMock(spec=ToolProvider)
        provider.tool_name = "mock_tool"
        provider.description = "mock"
        registry = ToolRegistry([provider])
        registry.list_tools()
        registry.get_tool("mock_tool")
        registry.has_tool("mock_tool")
        provider.execute.assert_not_called()
        provider.validate.assert_not_called()

    # --- statelessness ---------------------------------------------------
    def test_stores_only_providers_attribute(self):
        registry = ToolRegistry([self.gmail])
        self.assertEqual(set(vars(registry)), {"providers"})

    # --- dependency injection -------------------------------------------
    def test_di_wiring_default_empty_registry(self):
        from app.core.dependencies import get_tool_registry

        registry = get_tool_registry()
        self.assertIsInstance(registry, ToolRegistry)
        self.assertEqual(registry.list_tools(), [])

    def test_di_wiring_with_injected_providers(self):
        from app.core.dependencies import get_tool_registry

        registry = get_tool_registry([self.gmail, self.calendar])
        self.assertIsInstance(registry, ToolRegistry)
        self.assertTrue(registry.has_tool("gmail_stub"))
        self.assertTrue(registry.has_tool("calendar_stub"))


if __name__ == "__main__":
    unittest.main()
