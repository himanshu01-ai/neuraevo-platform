"""Unit tests for the Sprint 12.3 Multimodal AI adapter framework (abstraction).

The adapter is an abstraction only: a mocked backend collaborator is injected
into a minimal in-test concrete adapter, so no network, SDK, model call,
streaming, provider, or runtime is touched. The tests verify the adapter
abstraction (abstract, non-instantiable, both methods abstract), that a concrete
adapter is constructor-injected, stateless, delegates once, returns a
``MultimodalAIResponse`` unchanged, and propagates exceptions. A static-import
audit proves the adapter package imports no SDK, no networking, no streaming, and
no runtime/orchestration/cross-layer module — it stays isolated. The
composition-root seam is proven intentionally unfulfilled.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_multimodal_ai_adapter
"""

import ast
import importlib
import inspect
import unittest
import uuid
from abc import ABC
from unittest.mock import MagicMock

from app.services.interaction.models import InteractionType
from app.services.multimodal_ai.adapters import MultimodalAIAdapter
from app.services.multimodal_ai.adapters.base import (
    MultimodalAIAdapter as BaseMultimodalAIAdapter,
)
from app.services.multimodal_ai.models import (
    MultimodalAIRequest,
    MultimodalAIResponse,
)


def _make_request(**overrides):
    payload = {
        "interaction_type": InteractionType.IMAGE,
        "normalized_content": "describe this image",
        "conversation_id": uuid.uuid4(),
        "employee_id": uuid.uuid4(),
        "metadata": {},
    }
    payload.update(overrides)
    return MultimodalAIRequest(**payload)


class _FakeAdapter(MultimodalAIAdapter):
    """Minimal concrete adapter for tests only — no SDK, no network, no stream.

    Delegates to an injected collaborator (a mock) purely to demonstrate that the
    adapter layer supports constructor injection, is stateless, and propagates
    exceptions unchanged. This is a test double, not shipped framework code.
    """

    name = "fake"

    def __init__(self, backend) -> None:
        self.backend = backend

    def generate_response(self, request):
        return self.backend.generate_response(request)

    def health_check(self):
        return self.backend.health_check()


# =====================================================================
# Adapter abstraction
# =====================================================================
class MultimodalAIAdapterAbstractionTests(unittest.TestCase):
    def test_adapter_is_the_abstract_base(self):
        self.assertIs(MultimodalAIAdapter, BaseMultimodalAIAdapter)

    def test_adapter_is_abstract(self):
        self.assertTrue(issubclass(MultimodalAIAdapter, ABC))
        self.assertTrue(inspect.isabstract(MultimodalAIAdapter))

    def test_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            MultimodalAIAdapter()

    def test_generate_response_is_abstract(self):
        self.assertIn(
            "generate_response", MultimodalAIAdapter.__abstractmethods__
        )

    def test_health_check_is_abstract(self):
        self.assertIn("health_check", MultimodalAIAdapter.__abstractmethods__)

    def test_partial_implementation_remains_abstract(self):
        # Implementing only one abstract method leaves the class abstract.
        class OnlyGenerate(MultimodalAIAdapter):
            name = "partial"

            def generate_response(self, request):
                return MultimodalAIResponse(response_text="x")

        with self.assertRaises(TypeError):
            OnlyGenerate()

    def test_concrete_subclass_is_instantiable(self):
        adapter = _FakeAdapter(MagicMock())
        self.assertIsInstance(adapter, MultimodalAIAdapter)

    def test_package_exports_abstract_contract(self):
        # The abstract contract remains exported and abstract. (Sprint 12.5
        # later added the concrete GeminiAdapter alongside it — the 12.3
        # framework itself is unchanged.)
        package = importlib.import_module(
            "app.services.multimodal_ai.adapters"
        )
        self.assertIn("MultimodalAIAdapter", getattr(package, "__all__", []))
        self.assertTrue(inspect.isabstract(package.MultimodalAIAdapter))


# =====================================================================
# Concrete adapter behavior (mocked backend): DI, statelessness, delegation
# =====================================================================
class MultimodalAIAdapterBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = _make_request()
        self.response = MultimodalAIResponse(
            response_text="a cat on a mat", metadata={"model": "mock"}
        )
        self.backend = MagicMock(name="backend")
        self.backend.generate_response.return_value = self.response
        self.backend.health_check.return_value = True
        self.adapter = _FakeAdapter(self.backend)

    def test_constructor_uses_injected_collaborator(self):
        self.assertIs(self.adapter.backend, self.backend)

    def test_stateless_only_injected_collaborator(self):
        self.assertEqual(set(vars(self.adapter)), {"backend"})

    def test_abstract_base_introduces_no_state(self):
        # The ABC defines no __init__ of its own → it adds no hidden state.
        self.assertNotIn("__init__", vars(MultimodalAIAdapter))

    def test_generate_response_delegates_exactly_once(self):
        self.adapter.generate_response(self.request)
        self.backend.generate_response.assert_called_once_with(self.request)

    def test_generate_response_returns_response_unchanged(self):
        result = self.adapter.generate_response(self.request)
        self.assertIs(result, self.response)
        self.assertIsInstance(result, MultimodalAIResponse)

    def test_health_check_delegates_exactly_once(self):
        self.assertTrue(self.adapter.health_check())
        self.backend.health_check.assert_called_once_with()

    def test_generate_response_exception_propagates(self):
        self.backend.generate_response.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self.adapter.generate_response(self.request)

    def test_health_check_exception_propagates(self):
        self.backend.health_check.side_effect = RuntimeError("down")
        with self.assertRaises(RuntimeError):
            self.adapter.health_check()


# =====================================================================
# Static import audit: no SDK / network / streaming / cross-layer imports
# =====================================================================
class MultimodalAIAdapterImportAuditTests(unittest.TestCase):
    _MODULES = (
        "app.services.multimodal_ai.adapters",
        "app.services.multimodal_ai.adapters.base",
    )

    # Vendor SDK / networking / streaming roots that must never be imported.
    _FORBIDDEN_ROOTS = {
        "google",
        "openai",
        "anthropic",
        "grpc",
        "websocket",
        "websockets",
        "aiohttp",
        "requests",
        "httpx",
        "socket",
        "boto3",
        "asyncio",
    }

    # App modules the isolated adapter package must NOT depend on.
    _FORBIDDEN_APP_SUBSTRINGS = (
        "runtime",
        "planner",
        "permission",
        "registry",
        "tool_execution",
        "interaction_service",
        "api",
        "orchestrator",
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

    def test_no_runtime_orchestration_or_cross_layer_imports(self):
        for name in self._MODULES:
            _, full = self._imports(name)
            for module_path in (m for m in full if m.startswith("app.")):
                for banned in self._FORBIDDEN_APP_SUBSTRINGS:
                    self.assertNotIn(
                        banned,
                        module_path,
                        f"{name} imports forbidden app module: {module_path}",
                    )

    def test_adapter_base_only_depends_on_multimodal_models(self):
        # The single permitted app dependency is the sibling DTO module.
        _, full = self._imports("app.services.multimodal_ai.adapters.base")
        app_imports = {m for m in full if m.startswith("app.")}
        self.assertEqual(
            app_imports, {"app.services.multimodal_ai.models"}
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class MultimodalAIAdapterDependencyTests(unittest.TestCase):
    def test_adapter_seam_returns_injected_adapter(self):
        # Sprint 12.3 shipped this seam intentionally unfulfilled (raising
        # NotImplementedError); Sprint 12.5 fulfilled it with the concrete
        # Gemini adapter. The generic seam is a pure pass-through of the
        # injected adapter, so swapping adapters stays a composition-root-only
        # change.
        from app.core.dependencies import get_multimodal_ai_adapter

        adapter = MagicMock(name="MultimodalAIAdapter")
        self.assertIs(get_multimodal_ai_adapter(adapter), adapter)

    def test_adapter_dep_alias_exposed(self):
        from app.core import dependencies

        self.assertTrue(hasattr(dependencies, "MultimodalAIAdapterDep"))


if __name__ == "__main__":
    unittest.main()
