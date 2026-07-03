"""Unit tests for the Sprint 11.1 Tool Execution framework (abstraction only).

The provider is mocked, so no network, SDK, or concrete tool is touched. The
tests verify the provider abstraction, that ``ToolExecutionService`` delegates
to the injected provider exactly once (request forwarded and result returned
unchanged, exceptions propagated), that the service is a stateless,
constructor-injected pass-through, the request/result model contracts
(validation + immutability), and the composition-root wiring.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_tool_execution_service
"""

import unittest
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.services.tools import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionService,
    ToolProvider,
)
from app.services.tools.providers.base import ToolProvider as BaseToolProvider


# =====================================================================
# Provider abstraction
# =====================================================================
class ToolProviderAbstractionTests(unittest.TestCase):
    def test_provider_is_the_abstract_base(self):
        self.assertIs(ToolProvider, BaseToolProvider)

    def test_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            ToolProvider()  # abstract validate/execute not implemented

    def test_partial_implementation_still_abstract(self):
        # Implementing only execute (not validate) must remain abstract.
        class PartialProvider(ToolProvider):
            tool_name = "partial"
            description = "missing validate"

            def execute(self, request):  # noqa: D401 - test stub
                return ToolExecutionResult(success=True)

        with self.assertRaises(TypeError):
            PartialProvider()

    def test_concrete_subclass_is_instantiable(self):
        class OkProvider(ToolProvider):
            tool_name = "ok"
            description = "complete"

            def validate(self, request):
                return None

            def execute(self, request):
                return ToolExecutionResult(success=True)

        provider = OkProvider()
        self.assertIsInstance(provider, ToolProvider)


# =====================================================================
# ToolExecutionService (provider mocked)
# =====================================================================
class ToolExecutionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = ToolExecutionRequest(
            tool_name="noop", arguments={"x": 1}, metadata={"trace": "abc"}
        )
        self.result = ToolExecutionResult(
            success=True, output={"ok": True}, execution_time_ms=1.5
        )
        self.provider = MagicMock(name="ToolProvider")
        self.provider.execute.return_value = self.result
        self.service = ToolExecutionService(self.provider)

    def test_delegates_to_provider_exactly_once(self):
        self.service.execute(self.request)
        self.provider.execute.assert_called_once()

    def test_request_forwarded_unchanged(self):
        self.service.execute(self.request)
        self.provider.execute.assert_called_once_with(self.request)
        self.assertIs(self.provider.execute.call_args.args[0], self.request)

    def test_result_returned_unchanged(self):
        result = self.service.execute(self.request)
        self.assertIs(result, self.result)

    def test_provider_exception_propagates(self):
        self.provider.execute.side_effect = RuntimeError("tool boom")
        with self.assertRaises(RuntimeError):
            self.service.execute(self.request)

    def test_service_does_not_call_validate(self):
        # Sprint 11.1: the service only delegates execution (one delegation).
        self.service.execute(self.request)
        self.provider.validate.assert_not_called()

    def test_stateless_only_injected_provider(self):
        self.assertEqual(set(vars(self.service)), {"provider"})

    def test_constructor_uses_injected_provider(self):
        self.assertIs(self.service.provider, self.provider)


# =====================================================================
# Models: ToolExecutionRequest validation / ToolExecutionResult immutability
# =====================================================================
class ToolModelTests(unittest.TestCase):
    def test_request_defaults_empty_arguments_and_metadata(self):
        request = ToolExecutionRequest(tool_name="noop")
        self.assertEqual(request.arguments, {})
        self.assertEqual(request.metadata, {})

    def test_request_rejects_empty_tool_name(self):
        with self.assertRaises(ValidationError):
            ToolExecutionRequest(tool_name="")

    def test_request_rejects_whitespace_tool_name(self):
        with self.assertRaises(ValidationError):
            ToolExecutionRequest(tool_name="   ")

    def test_request_trims_tool_name(self):
        request = ToolExecutionRequest(tool_name="  noop  ")
        self.assertEqual(request.tool_name, "noop")

    def test_request_requires_tool_name(self):
        with self.assertRaises(ValidationError):
            ToolExecutionRequest()  # tool_name is required

    def test_result_is_immutable(self):
        result = ToolExecutionResult(success=True, output="done")
        with self.assertRaises(ValidationError):
            result.success = False

    def test_result_defaults(self):
        result = ToolExecutionResult(success=False, error="nope")
        self.assertFalse(result.success)
        self.assertIsNone(result.output)
        self.assertEqual(result.error, "nope")
        self.assertIsNone(result.execution_time_ms)


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class ToolDependencyTests(unittest.TestCase):
    def test_service_provider_resolves_with_injected_provider(self):
        from app.core.dependencies import get_tool_execution_service

        provider = MagicMock(name="ToolProvider")
        service = get_tool_execution_service(provider)
        self.assertIsInstance(service, ToolExecutionService)
        self.assertIs(service.provider, provider)

    def test_provider_seam_unfulfilled_until_later_sprint(self):
        # Sprint 11.1 ships only the framework: no concrete provider exists,
        # so the provider composition-root seam intentionally raises.
        from app.core.dependencies import get_tool_provider

        with self.assertRaises(NotImplementedError):
            get_tool_provider()


if __name__ == "__main__":
    unittest.main()
