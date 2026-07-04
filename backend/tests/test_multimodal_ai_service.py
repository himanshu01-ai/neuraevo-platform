"""Unit tests for the Sprint 12.2 Multimodal AI framework (abstraction only).

The provider is mocked, so no network, SDK, model call, streaming, prompt
building, planner, permission check, registry, tool execution, or runtime is
touched. The tests verify the provider abstraction, that ``MultimodalAIService``
delegates to the injected provider exactly once (request forwarded, response
returned unchanged, exceptions propagated), that the service is a stateless,
constructor-injected pass-through exposing a single public method, the
request/response model contracts (validation + immutability + defaults), and
the composition-root wiring. A static-import audit proves the framework pulls in
no SDK, no networking, no streaming, and no runtime dependency.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_multimodal_ai_service
"""

import ast
import importlib
import inspect
import unittest
import uuid
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.services.interaction.models import InteractionType
from app.services.multimodal_ai import (
    MultimodalAIProvider,
    MultimodalAIRequest,
    MultimodalAIResponse,
    MultimodalAIService,
)
from app.services.multimodal_ai.providers.base import (
    MultimodalAIProvider as BaseMultimodalAIProvider,
)


def _make_request(**overrides):
    payload = {
        "interaction_type": InteractionType.VOICE,
        "normalized_content": "what's on my calendar today?",
        "conversation_id": uuid.uuid4(),
        "employee_id": uuid.uuid4(),
        "metadata": {"trace": "abc"},
    }
    payload.update(overrides)
    return MultimodalAIRequest(**payload)


# =====================================================================
# Provider abstraction
# =====================================================================
class MultimodalAIProviderAbstractionTests(unittest.TestCase):
    def test_provider_is_the_abstract_base(self):
        self.assertIs(MultimodalAIProvider, BaseMultimodalAIProvider)

    def test_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            MultimodalAIProvider()  # abstract generate_response not implemented

    def test_generate_response_is_abstract(self):
        # Sprint 12.2 ships only the contract: the sole method is abstract, so
        # no concrete generation is provided here.
        self.assertIn(
            "generate_response",
            MultimodalAIProvider.__abstractmethods__,
        )

    def test_concrete_subclass_is_instantiable(self):
        class OkProvider(MultimodalAIProvider):
            name = "ok"

            def generate_response(self, request):
                return MultimodalAIResponse(response_text="ok")

        provider = OkProvider()
        self.assertIsInstance(provider, MultimodalAIProvider)


# =====================================================================
# MultimodalAIService (provider mocked)
# =====================================================================
class MultimodalAIServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = _make_request()
        self.response = MultimodalAIResponse(
            response_text="You have two meetings.", metadata={"model": "mock"}
        )
        self.provider = MagicMock(name="MultimodalAIProvider")
        self.provider.generate_response.return_value = self.response
        self.service = MultimodalAIService(self.provider)

    def test_delegates_to_provider_exactly_once(self):
        self.service.generate_response(self.request)
        self.provider.generate_response.assert_called_once()

    def test_request_forwarded_unchanged(self):
        self.service.generate_response(self.request)
        self.provider.generate_response.assert_called_once_with(self.request)
        self.assertIs(
            self.provider.generate_response.call_args.args[0], self.request
        )

    def test_result_returned_unchanged(self):
        result = self.service.generate_response(self.request)
        self.assertIs(result, self.response)

    def test_provider_exception_propagates(self):
        self.provider.generate_response.side_effect = RuntimeError(
            "provider boom"
        )
        with self.assertRaises(RuntimeError):
            self.service.generate_response(self.request)

    def test_stateless_only_injected_provider(self):
        # No session, repository, cache, memory, runtime, or execution state.
        self.assertEqual(set(vars(self.service)), {"provider"})

    def test_constructor_uses_injected_provider(self):
        self.assertIs(self.service.provider, self.provider)

    def test_exposes_single_public_method(self):
        # A pure delegator: ``generate_response`` is the only public method — no
        # retry, cache, prompt, planner, or runtime surface is exposed.
        public_methods = {
            name
            for name, attr in vars(MultimodalAIService).items()
            if not name.startswith("_") and callable(attr)
        }
        self.assertEqual(public_methods, {"generate_response"})


# =====================================================================
# Models: MultimodalAIRequest validation / MultimodalAIResponse immutability
# =====================================================================
class MultimodalAIRequestModelTests(unittest.TestCase):
    def test_trims_normalized_content(self):
        request = _make_request(normalized_content="  hello world  ")
        self.assertEqual(request.normalized_content, "hello world")

    def test_rejects_empty_normalized_content(self):
        with self.assertRaises(ValidationError):
            _make_request(normalized_content="")

    def test_rejects_whitespace_normalized_content(self):
        with self.assertRaises(ValidationError):
            _make_request(normalized_content="   ")

    def test_requires_normalized_content(self):
        with self.assertRaises(ValidationError):
            MultimodalAIRequest(
                interaction_type=InteractionType.TEXT,
                conversation_id=uuid.uuid4(),
                employee_id=uuid.uuid4(),
            )

    def test_requires_conversation_and_employee_ids(self):
        with self.assertRaises(ValidationError):
            MultimodalAIRequest(
                interaction_type=InteractionType.TEXT,
                normalized_content="hi",
            )

    def test_rejects_invalid_conversation_id(self):
        with self.assertRaises(ValidationError):
            _make_request(conversation_id="not-a-uuid")

    def test_accepts_uuid_string_and_coerces(self):
        cid = uuid.uuid4()
        request = _make_request(conversation_id=str(cid))
        self.assertEqual(request.conversation_id, cid)
        self.assertIsInstance(request.conversation_id, uuid.UUID)

    def test_rejects_unknown_interaction_type(self):
        with self.assertRaises(ValidationError):
            _make_request(interaction_type="hologram")

    def test_accepts_every_interaction_type(self):
        for member in InteractionType:
            request = _make_request(interaction_type=member)
            self.assertEqual(request.interaction_type, member)

    def test_metadata_defaults_empty(self):
        request = MultimodalAIRequest(
            interaction_type=InteractionType.TEXT,
            normalized_content="hi",
            conversation_id=uuid.uuid4(),
            employee_id=uuid.uuid4(),
        )
        self.assertEqual(request.metadata, {})


class MultimodalAIResponseModelTests(unittest.TestCase):
    def test_response_is_immutable(self):
        response = MultimodalAIResponse(response_text="hi")
        with self.assertRaises(ValidationError):
            response.response_text = "changed"

    def test_response_metadata_is_immutable(self):
        response = MultimodalAIResponse(response_text="hi")
        with self.assertRaises(ValidationError):
            response.metadata = {"x": 1}

    def test_response_metadata_defaults_empty(self):
        response = MultimodalAIResponse(response_text="hi")
        self.assertEqual(response.metadata, {})

    def test_response_requires_response_text(self):
        with self.assertRaises(ValidationError):
            MultimodalAIResponse()

    def test_response_holds_fields(self):
        response = MultimodalAIResponse(
            response_text="the answer", metadata={"tokens": 12}
        )
        self.assertEqual(response.response_text, "the answer")
        self.assertEqual(response.metadata, {"tokens": 12})


# =====================================================================
# Static import audit: no SDK, no network, no streaming, no runtime dependency
# =====================================================================
class MultimodalAINoForbiddenImportsTests(unittest.TestCase):
    _MODULES = (
        "app.services.multimodal_ai",
        "app.services.multimodal_ai.models",
        "app.services.multimodal_ai.multimodal_ai_service",
        "app.services.multimodal_ai.providers",
        "app.services.multimodal_ai.providers.base",
    )

    # Third-party SDK / networking / streaming roots that must never be imported.
    _FORBIDDEN_ROOTS = {
        "openai",
        "google",
        "anthropic",
        "httpx",
        "requests",
        "aiohttp",
        "websocket",
        "websockets",
        "socket",
        "grpc",
        "boto3",
        "asyncio",
    }

    # App modules the framework must NOT depend on (runtime/orchestration/etc.).
    _FORBIDDEN_APP_SUBSTRINGS = (
        "runtime",
        "orchestrator",
        "planner",
        "permissions",
        "tools",
        "memory",
        "api",
        "prompt",
    )

    def _imports(self, module_name):
        module = importlib.import_module(module_name)
        tree = ast.parse(inspect.getsource(module))
        roots, full = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    roots.add(alias.name.split(".")[0])
                    full.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
                full.add(node.module)
        return roots, full

    def test_no_sdk_network_or_streaming_imports(self):
        for name in self._MODULES:
            roots, _ = self._imports(name)
            offenders = roots & self._FORBIDDEN_ROOTS
            self.assertEqual(
                offenders, set(), f"{name} imports forbidden root(s): {offenders}"
            )

    def test_no_runtime_or_orchestration_dependency(self):
        for name in self._MODULES:
            _, full = self._imports(name)
            app_imports = {m for m in full if m.startswith("app.")}
            for module_path in app_imports:
                for banned in self._FORBIDDEN_APP_SUBSTRINGS:
                    self.assertNotIn(
                        banned,
                        module_path,
                        f"{name} depends on forbidden app module: {module_path}",
                    )

    def test_only_reuses_interaction_type_from_app(self):
        # The single permitted app dependency is the reused Interaction enum.
        _, full = self._imports("app.services.multimodal_ai.models")
        external_app_imports = {
            m
            for m in full
            if m.startswith("app.") and not m.startswith("app.services.multimodal_ai")
        }
        self.assertEqual(
            external_app_imports, {"app.services.interaction.models"}
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class MultimodalAIDependencyTests(unittest.TestCase):
    def test_service_provider_resolves_with_injected_provider(self):
        from app.core.dependencies import get_multimodal_ai_service

        provider = MagicMock(name="MultimodalAIProvider")
        service = get_multimodal_ai_service(provider)
        self.assertIsInstance(service, MultimodalAIService)
        self.assertIs(service.provider, provider)

    def test_provider_seam_unfulfilled_until_later_sprint(self):
        # Sprint 12.2 ships only the framework: no concrete provider exists,
        # so the provider composition-root seam intentionally raises.
        from app.core.dependencies import get_multimodal_ai_provider

        with self.assertRaises(NotImplementedError):
            get_multimodal_ai_provider()


if __name__ == "__main__":
    unittest.main()
