"""Unit tests for the Sprint 11.3 Permission framework (abstraction only).

The provider is mocked, so no network, SDK, planner, execution, registry, or
runtime is touched. The tests verify the provider abstraction, that
``PermissionService`` delegates to the injected provider exactly once (request
forwarded, result returned unchanged, exceptions propagated), that the service
is a stateless, constructor-injected pass-through, the request/result model
contracts (validation + immutability), and the composition-root wiring.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_permission_service
"""

import unittest
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.services.permissions import (
    PermissionProvider,
    PermissionRequest,
    PermissionResult,
    PermissionService,
)
from app.services.permissions.providers.base import (
    PermissionProvider as BasePermissionProvider,
)


# =====================================================================
# Provider abstraction
# =====================================================================
class PermissionProviderAbstractionTests(unittest.TestCase):
    def test_provider_is_the_abstract_base(self):
        self.assertIs(PermissionProvider, BasePermissionProvider)

    def test_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            PermissionProvider()  # abstract check_permission not implemented

    def test_concrete_subclass_is_instantiable(self):
        class OkProvider(PermissionProvider):
            name = "ok"

            def check_permission(self, request):
                return PermissionResult(approved=True)

        provider = OkProvider()
        self.assertIsInstance(provider, PermissionProvider)


# =====================================================================
# PermissionService (provider mocked)
# =====================================================================
class PermissionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = PermissionRequest(
            tool_name="send_email",
            arguments={"to": "x@example.com"},
            metadata={"trace": "abc"},
        )
        self.result = PermissionResult(
            approved=False,
            reason="needs confirmation",
            requires_user_confirmation=True,
        )
        self.provider = MagicMock(name="PermissionProvider")
        self.provider.check_permission.return_value = self.result
        self.service = PermissionService(self.provider)

    def test_delegates_to_provider_exactly_once(self):
        self.service.check_permission(self.request)
        self.provider.check_permission.assert_called_once()

    def test_request_forwarded_unchanged(self):
        self.service.check_permission(self.request)
        self.provider.check_permission.assert_called_once_with(self.request)
        self.assertIs(
            self.provider.check_permission.call_args.args[0], self.request
        )

    def test_result_returned_unchanged(self):
        result = self.service.check_permission(self.request)
        self.assertIs(result, self.result)

    def test_provider_exception_propagates(self):
        self.provider.check_permission.side_effect = RuntimeError("policy boom")
        with self.assertRaises(RuntimeError):
            self.service.check_permission(self.request)

    def test_stateless_only_injected_provider(self):
        self.assertEqual(set(vars(self.service)), {"provider"})

    def test_constructor_uses_injected_provider(self):
        self.assertIs(self.service.provider, self.provider)


# =====================================================================
# Models: PermissionRequest validation / PermissionResult immutability
# =====================================================================
class PermissionModelTests(unittest.TestCase):
    def test_request_defaults_empty_arguments_and_metadata(self):
        request = PermissionRequest(tool_name="noop")
        self.assertEqual(request.arguments, {})
        self.assertEqual(request.metadata, {})

    def test_request_rejects_empty_tool_name(self):
        with self.assertRaises(ValidationError):
            PermissionRequest(tool_name="")

    def test_request_rejects_whitespace_tool_name(self):
        with self.assertRaises(ValidationError):
            PermissionRequest(tool_name="   ")

    def test_request_trims_tool_name(self):
        request = PermissionRequest(tool_name="  send_email  ")
        self.assertEqual(request.tool_name, "send_email")

    def test_request_requires_tool_name(self):
        with self.assertRaises(ValidationError):
            PermissionRequest()  # tool_name is required

    def test_result_is_immutable(self):
        result = PermissionResult(approved=True)
        with self.assertRaises(ValidationError):
            result.approved = False

    def test_result_defaults(self):
        result = PermissionResult(approved=True)
        self.assertTrue(result.approved)
        self.assertIsNone(result.reason)
        self.assertFalse(result.requires_user_confirmation)


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class PermissionDependencyTests(unittest.TestCase):
    def test_service_provider_resolves_with_injected_provider(self):
        from app.core.dependencies import get_permission_service

        provider = MagicMock(name="PermissionProvider")
        service = get_permission_service(provider)
        self.assertIsInstance(service, PermissionService)
        self.assertIs(service.provider, provider)

    def test_provider_seam_unfulfilled_until_later_sprint(self):
        # Sprint 11.3 ships only the framework: no concrete provider exists,
        # so the provider composition-root seam intentionally raises.
        from app.core.dependencies import get_permission_provider

        with self.assertRaises(NotImplementedError):
            get_permission_provider()


if __name__ == "__main__":
    unittest.main()
