"""Unit tests for the Sprint 12.4 Gemini provider (business layer only).

The adapter is mocked, so no network, SDK, Google import, model call, or
streaming is touched. The tests verify ABC inheritance and that GeminiProvider
is concrete; constructor injection of the adapter + ProviderConfig; that
generate_response delegates to the adapter exactly once and returns its response
unchanged; exception propagation; statelessness; that the model is selected only
from config (never a hardcoded literal); the ProviderConfig contract (validation,
immutability, defaults); a static-import audit proving the provider imports only
the provider base, the adapter, and the DTO models (no SDK / runtime / cross
layer); and the composition-root wiring (adapter seam still raises).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_gemini_provider
"""

import ast
import importlib
import inspect
import unittest
import uuid
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.services.interaction.models import InteractionType
from app.services.multimodal_ai.models import (
    MultimodalAIRequest,
    MultimodalAIResponse,
)
from app.services.multimodal_ai.providers import (
    GeminiProvider,
    MultimodalAIProvider,
    ProviderConfig,
)
from app.services.multimodal_ai.providers.base import (
    MultimodalAIProvider as BaseMultimodalAIProvider,
)


def _make_config(**overrides):
    payload = {"provider_name": "gemini", "default_model": "test-model-v1"}
    payload.update(overrides)
    return ProviderConfig(**payload)


def _make_request(**overrides):
    payload = {
        "interaction_type": InteractionType.TEXT,
        "normalized_content": "hello",
        "conversation_id": uuid.uuid4(),
        "employee_id": uuid.uuid4(),
        "metadata": {},
    }
    payload.update(overrides)
    return MultimodalAIRequest(**payload)


# =====================================================================
# ABC inheritance / concreteness
# =====================================================================
class GeminiProviderInheritanceTests(unittest.TestCase):
    def test_inherits_multimodal_ai_provider(self):
        self.assertTrue(issubclass(GeminiProvider, MultimodalAIProvider))
        self.assertIs(MultimodalAIProvider, BaseMultimodalAIProvider)

    def test_is_concrete_and_instantiable(self):
        self.assertFalse(inspect.isabstract(GeminiProvider))
        provider = GeminiProvider(MagicMock(), _make_config())
        self.assertIsInstance(provider, MultimodalAIProvider)


# =====================================================================
# Constructor injection / statelessness / config storage
# =====================================================================
class GeminiProviderConstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = MagicMock(name="MultimodalAIAdapter")
        self.config = _make_config()
        self.provider = GeminiProvider(self.adapter, self.config)

    def test_constructor_stores_injected_adapter(self):
        self.assertIs(self.provider.adapter, self.adapter)

    def test_constructor_stores_injected_config(self):
        self.assertIs(self.provider.config, self.config)

    def test_stateless_only_injected_collaborators(self):
        self.assertEqual(set(vars(self.provider)), {"adapter", "config"})

    def test_name_comes_from_config(self):
        self.assertEqual(self.provider.name, self.config.provider_name)


# =====================================================================
# Delegation / identity / exception propagation
# =====================================================================
class GeminiProviderDelegationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.response = MultimodalAIResponse(
            response_text="hi", metadata={"m": 1}
        )
        self.adapter = MagicMock(name="MultimodalAIAdapter")
        self.adapter.generate_response.return_value = self.response
        self.provider = GeminiProvider(self.adapter, _make_config())
        self.request = _make_request()

    def test_delegates_to_adapter_exactly_once(self):
        self.provider.generate_response(self.request)
        self.adapter.generate_response.assert_called_once_with(self.request)

    def test_returns_adapter_response_unchanged(self):
        result = self.provider.generate_response(self.request)
        self.assertIs(result, self.response)

    def test_request_forwarded_unchanged(self):
        self.provider.generate_response(self.request)
        self.assertIs(
            self.adapter.generate_response.call_args.args[0], self.request
        )

    def test_adapter_exception_propagates(self):
        self.adapter.generate_response.side_effect = RuntimeError("adapter boom")
        with self.assertRaises(RuntimeError):
            self.provider.generate_response(self.request)

    def test_only_generation_is_delegated(self):
        # Business layer delegates generation only — no other adapter method.
        self.provider.generate_response(self.request)
        self.adapter.health_check.assert_not_called()


# =====================================================================
# Model selected from config, never hardcoded
# =====================================================================
class GeminiProviderModelSelectionTests(unittest.TestCase):
    def test_model_selected_from_config(self):
        provider = GeminiProvider(
            MagicMock(), _make_config(default_model="alpha-model")
        )
        self.assertEqual(provider.model, "alpha-model")

    def test_model_follows_config_change(self):
        p1 = GeminiProvider(MagicMock(), _make_config(default_model="m-one"))
        p2 = GeminiProvider(MagicMock(), _make_config(default_model="m-two"))
        self.assertEqual(p1.model, "m-one")
        self.assertEqual(p2.model, "m-two")

    def test_no_gemini_model_literals_in_provider_source(self):
        module = importlib.import_module(
            "app.services.multimodal_ai.providers.gemini_provider"
        )
        source = inspect.getsource(module)
        for literal in (
            "gemini-live-2.5",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-flash",
            "gemini-1.5",
            "gemini-2.5",
        ):
            self.assertNotIn(literal, source)


# =====================================================================
# ProviderConfig contract
# =====================================================================
class ProviderConfigModelTests(unittest.TestCase):
    def test_is_immutable(self):
        config = _make_config()
        with self.assertRaises(ValidationError):
            config.default_model = "changed"

    def test_requires_provider_name(self):
        with self.assertRaises(ValidationError):
            ProviderConfig(default_model="m")

    def test_requires_default_model(self):
        with self.assertRaises(ValidationError):
            ProviderConfig(provider_name="gemini")

    def test_rejects_whitespace_provider_name(self):
        with self.assertRaises(ValidationError):
            _make_config(provider_name="   ")

    def test_rejects_empty_default_model(self):
        with self.assertRaises(ValidationError):
            _make_config(default_model="")

    def test_trims_string_fields(self):
        config = _make_config(provider_name="  gemini  ", default_model="  m  ")
        self.assertEqual(config.provider_name, "gemini")
        self.assertEqual(config.default_model, "m")

    def test_temperature_bounds_enforced(self):
        with self.assertRaises(ValidationError):
            _make_config(temperature=2.5)
        with self.assertRaises(ValidationError):
            _make_config(temperature=-0.1)

    def test_max_output_tokens_must_be_positive(self):
        with self.assertRaises(ValidationError):
            _make_config(max_output_tokens=0)

    def test_defaults(self):
        config = _make_config()
        self.assertEqual(config.temperature, 0.7)
        self.assertEqual(config.max_output_tokens, 1024)
        self.assertEqual(config.safety_profile, "standard")
        self.assertEqual(config.metadata, {})


# =====================================================================
# Static import audit: only base + adapter + DTO models; no SDK / cross-layer
# =====================================================================
class GeminiProviderImportAuditTests(unittest.TestCase):
    _MODULE = "app.services.multimodal_ai.providers.gemini_provider"
    _FORBIDDEN_ROOTS = {
        "google",
        "vertexai",
        "openai",
        "anthropic",
        "grpc",
        "aiohttp",
        "requests",
        "httpx",
        "socket",
        "websocket",
        "websockets",
        "asyncio",
        "boto3",
    }
    _FORBIDDEN_APP_SUBSTRINGS = (
        "runtime",
        "orchestrator",
        "planner",
        "permission",
        "registry",
        "tool_execution",
        "interaction_service",
        "memory",
        "prompt",
        "api",
    )
    _ALLOWED_APP_IMPORTS = {
        "app.services.multimodal_ai.providers.base",
        "app.services.multimodal_ai.adapters",
        "app.services.multimodal_ai.models",
    }

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
        roots, _ = self._imports(self._MODULE)
        self.assertEqual(roots & self._FORBIDDEN_ROOTS, set())

    def test_no_cross_layer_app_imports(self):
        _, full = self._imports(self._MODULE)
        for module_path in (m for m in full if m.startswith("app.")):
            for banned in self._FORBIDDEN_APP_SUBSTRINGS:
                self.assertNotIn(banned, module_path)

    def test_app_imports_are_exactly_whitelisted(self):
        _, full = self._imports(self._MODULE)
        app_imports = {m for m in full if m.startswith("app.")}
        self.assertEqual(app_imports, self._ALLOWED_APP_IMPORTS)


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class GeminiProviderDependencyTests(unittest.TestCase):
    def test_get_provider_config_returns_config(self):
        from app.core.dependencies import get_provider_config

        config = get_provider_config()
        self.assertIsInstance(config, ProviderConfig)
        self.assertTrue(config.default_model)
        self.assertTrue(config.provider_name)

    def test_get_gemini_provider_uses_injected_deps(self):
        from app.core.dependencies import get_gemini_provider

        adapter = MagicMock(name="MultimodalAIAdapter")
        config = _make_config()
        provider = get_gemini_provider(adapter, config)
        self.assertIsInstance(provider, GeminiProvider)
        self.assertIs(provider.adapter, adapter)
        self.assertIs(provider.config, config)

    def test_dep_aliases_exposed(self):
        from app.core import dependencies

        self.assertTrue(hasattr(dependencies, "GeminiProviderDep"))
        self.assertTrue(hasattr(dependencies, "ProviderConfigDep"))

    def test_adapter_seam_still_unfulfilled(self):
        from app.core.dependencies import get_multimodal_ai_adapter

        with self.assertRaises(NotImplementedError):
            get_multimodal_ai_adapter()


if __name__ == "__main__":
    unittest.main()
