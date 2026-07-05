"""Unit tests for the Sprint 12.5 Gemini adapter (google-genai SDK integration).

Everything is mocked — no network call, no real SDK client, no API key, no
token is ever used. The tests verify: the adapter subclasses the Sprint 12.3
ABC and owns only its injected client (never instantiating the SDK itself);
``generate_response`` makes exactly one SDK call with the model taken from
request metadata (never hardcoded), maps ``response.text`` into an immutable
``MultimodalAIResponse`` with empty metadata, mutates nothing, and propagates
SDK exceptions unchanged; ``health_check`` uses the token-free ``models.list``
probe, returns True/False, never performs a generation, and never raises; the
adapter depends on the ``GenAIClientProtocol`` structural interface rather than
the concrete SDK class; the composition root reads/validates ``GEMINI_API_KEY``
and builds client + adapter via injection; and an AST audit over the whole app
proves only ``gemini_adapter.py`` imports the SDK, the deprecated
``google.generativeai`` is used nowhere, the provider stays business-only, and
the interaction layer is untouched.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_gemini_adapter
"""

import ast
import importlib
import importlib.util
import inspect
import os
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.interaction.models import InteractionType
from app.services.multimodal_ai.adapters import (
    MODEL_METADATA_KEY,
    GeminiAdapter,
    GenAIClientProtocol,
    MultimodalAIAdapter,
)
from app.services.multimodal_ai.models import (
    MultimodalAIRequest,
    MultimodalAIResponse,
)
from app.services.multimodal_ai.providers import GeminiProvider, ProviderConfig


def _make_request(model="test-model-v1", **overrides):
    metadata = {"trace": "abc"}
    if model is not None:
        metadata[MODEL_METADATA_KEY] = model
    payload = {
        "interaction_type": InteractionType.TEXT,
        "normalized_content": "hello gemini",
        "conversation_id": uuid.uuid4(),
        "employee_id": uuid.uuid4(),
        "metadata": metadata,
    }
    payload.update(overrides)
    return MultimodalAIRequest(**payload)


def _make_sdk_client(text="generated text"):
    """A mocked SDK client exposing only the surface the adapter uses."""
    client = MagicMock(name="GenAIClient")
    client.models.generate_content.return_value = SimpleNamespace(text=text)
    client.models.list.return_value = [SimpleNamespace(name="m")]
    return client


class _FakeModelsSurface:
    """Plain (non-mock) models surface for structural-protocol checks."""

    def generate_content(self, *, model, contents):
        return SimpleNamespace(text="ok")

    def list(self):
        return []


class _FakeClient:
    def __init__(self):
        self.models = _FakeModelsSurface()


# =====================================================================
# ABC inheritance / adapter shape
# =====================================================================
class GeminiAdapterInheritanceTests(unittest.TestCase):
    def test_subclasses_multimodal_ai_adapter(self):
        self.assertTrue(issubclass(GeminiAdapter, MultimodalAIAdapter))

    def test_is_concrete_and_instantiable(self):
        self.assertFalse(inspect.isabstract(GeminiAdapter))
        adapter = GeminiAdapter(_make_sdk_client())
        self.assertIsInstance(adapter, MultimodalAIAdapter)

    def test_constructor_stores_injected_client(self):
        client = _make_sdk_client()
        adapter = GeminiAdapter(client)
        self.assertIs(adapter.client, client)

    def test_adapter_owns_only_injected_client(self):
        adapter = GeminiAdapter(_make_sdk_client())
        self.assertEqual(set(vars(adapter)), {"client"})

    def test_sdk_client_never_instantiated_internally(self):
        # The adapter class itself never references the SDK: constructing it
        # touches no SDK symbol, and its source contains no genai reference.
        source = inspect.getsource(GeminiAdapter)
        self.assertNotIn("genai", source)
        self.assertNotIn("google", source)

    def test_depends_on_protocol_not_concrete_sdk_class(self):
        hints = inspect.signature(GeminiAdapter.__init__).parameters
        self.assertIs(hints["client"].annotation, GenAIClientProtocol)

    def test_plain_fake_satisfies_client_protocol(self):
        self.assertIsInstance(_FakeClient(), GenAIClientProtocol)

    def test_arbitrary_object_does_not_satisfy_protocol(self):
        self.assertNotIsInstance(object(), GenAIClientProtocol)


# =====================================================================
# generate_response: one SDK call, mapping, no mutation, propagation
# =====================================================================
class GeminiAdapterGenerateResponseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _make_sdk_client(text="the answer")
        self.adapter = GeminiAdapter(self.client)
        self.request = _make_request(model="model-from-config")

    def test_calls_sdk_exactly_once(self):
        self.adapter.generate_response(self.request)
        self.client.models.generate_content.assert_called_once()

    def test_sdk_call_uses_model_from_request_metadata(self):
        self.adapter.generate_response(self.request)
        kwargs = self.client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["model"], "model-from-config")

    def test_sdk_call_uses_normalized_content(self):
        self.adapter.generate_response(self.request)
        kwargs = self.client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["contents"], self.request.normalized_content)

    def test_returns_dto_with_extracted_text(self):
        result = self.adapter.generate_response(self.request)
        self.assertIsInstance(result, MultimodalAIResponse)
        self.assertEqual(result.response_text, "the answer")

    def test_response_metadata_is_empty(self):
        result = self.adapter.generate_response(self.request)
        self.assertEqual(result.metadata, {})

    def test_none_sdk_text_maps_to_empty_string(self):
        self.client.models.generate_content.return_value = SimpleNamespace(
            text=None
        )
        result = self.adapter.generate_response(self.request)
        self.assertEqual(result.response_text, "")

    def test_request_object_unchanged(self):
        before_metadata = dict(self.request.metadata)
        before_content = self.request.normalized_content
        self.adapter.generate_response(self.request)
        self.assertEqual(self.request.metadata, before_metadata)
        self.assertEqual(self.request.normalized_content, before_content)

    def test_request_metadata_dict_not_mutated_in_place(self):
        metadata_ref = self.request.metadata
        self.adapter.generate_response(self.request)
        self.assertIs(self.request.metadata, metadata_ref)
        self.assertEqual(
            metadata_ref,
            {"trace": "abc", MODEL_METADATA_KEY: "model-from-config"},
        )

    def test_sdk_exception_propagates_unchanged(self):
        boom = RuntimeError("sdk exploded")
        self.client.models.generate_content.side_effect = boom
        with self.assertRaises(RuntimeError) as ctx:
            self.adapter.generate_response(self.request)
        self.assertIs(ctx.exception, boom)

    def test_missing_model_metadata_raises_value_error(self):
        request = _make_request(model=None)
        with self.assertRaises(ValueError):
            self.adapter.generate_response(request)
        self.client.models.generate_content.assert_not_called()

    def test_blank_model_metadata_raises_value_error(self):
        request = _make_request(model="   ")
        with self.assertRaises(ValueError):
            self.adapter.generate_response(request)

    def test_no_model_literals_hardcoded_in_adapter_source(self):
        module = importlib.import_module(
            "app.services.multimodal_ai.adapters.gemini_adapter"
        )
        source = inspect.getsource(module)
        self.assertNotIn("gemini-", source)  # no gemini-live/pro/flash literals


# =====================================================================
# health_check: lightweight, token-free, never raises, no generation
# =====================================================================
class GeminiAdapterHealthCheckTests(unittest.TestCase):
    def test_returns_true_when_client_usable(self):
        client = _make_sdk_client()
        self.assertTrue(GeminiAdapter(client).health_check())
        client.models.list.assert_called_once_with()

    def test_never_performs_generation(self):
        client = _make_sdk_client()
        GeminiAdapter(client).health_check()
        client.models.generate_content.assert_not_called()

    def test_returns_false_on_sdk_failure(self):
        client = _make_sdk_client()
        client.models.list.side_effect = RuntimeError("unauthorized")
        self.assertFalse(GeminiAdapter(client).health_check())

    def test_no_exception_escapes_even_for_broken_client(self):
        # A client without any models surface fails structurally, not loudly.
        self.assertFalse(GeminiAdapter(object()).health_check())


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class GeminiAdapterDependencyTests(unittest.TestCase):
    def test_get_genai_client_reads_key_and_builds_via_factory(self):
        from app.core.dependencies import get_genai_client

        sdk_client = MagicMock(name="genai.Client")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "app.core.dependencies.create_genai_client",
                return_value=sdk_client,
            ) as factory:
                client = get_genai_client()
        factory.assert_called_once_with("test-key")
        self.assertIs(client, sdk_client)

    def test_missing_api_key_raises_and_factory_untouched(self):
        from app.core.dependencies import get_genai_client

        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "app.core.dependencies.create_genai_client"
            ) as factory:
                with self.assertRaises(ValueError):
                    get_genai_client()
        factory.assert_not_called()

    def test_blank_api_key_raises(self):
        from app.core.dependencies import get_genai_client

        with patch.dict(os.environ, {"GEMINI_API_KEY": "   "}):
            with self.assertRaises(ValueError):
                get_genai_client()

    def test_get_gemini_adapter_injects_client(self):
        from app.core.dependencies import get_gemini_adapter

        client = _make_sdk_client()
        adapter = get_gemini_adapter(client)
        self.assertIsInstance(adapter, GeminiAdapter)
        self.assertIs(adapter.client, client)

    def test_adapter_seam_now_returns_injected_adapter(self):
        # Sprint 12.5 replaced the 12.3 NotImplementedError seam: the generic
        # adapter seam is now fulfilled by the injected Gemini adapter.
        from app.core.dependencies import get_multimodal_ai_adapter

        adapter = GeminiAdapter(_make_sdk_client())
        self.assertIs(get_multimodal_ai_adapter(adapter), adapter)

    def test_dep_aliases_exposed(self):
        from app.core import dependencies

        self.assertTrue(hasattr(dependencies, "GenAIClientDep"))
        self.assertTrue(hasattr(dependencies, "GeminiAdapterDep"))
        self.assertTrue(hasattr(dependencies, "MultimodalAIAdapterDep"))

    @unittest.skipUnless(
        importlib.util.find_spec("google") is not None
        and importlib.util.find_spec("google.genai") is not None,
        "google-genai not installed",
    )
    def test_factory_builds_real_sdk_client_satisfying_protocol(self):
        # Local construction only — no network call is made by the SDK here.
        from app.services.multimodal_ai.adapters import create_genai_client

        client = create_genai_client("dummy-key-never-used")
        self.assertIsInstance(client, GenAIClientProtocol)


# =====================================================================
# Full in-memory chain: Service → Provider → Adapter → (fake SDK)
# =====================================================================
class GeminiChainIntegrationTests(unittest.TestCase):
    def test_service_provider_adapter_chain_with_fake_sdk(self):
        from app.services.multimodal_ai import MultimodalAIService

        client = _make_sdk_client(text="chain works")
        adapter = GeminiAdapter(client)
        config = ProviderConfig(
            provider_name="gemini", default_model="chain-model"
        )
        service = MultimodalAIService(GeminiProvider(adapter, config))

        result = service.generate_response(_make_request(model="chain-model"))

        self.assertEqual(result.response_text, "chain works")
        client.models.generate_content.assert_called_once()
        kwargs = client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["model"], "chain-model")


# =====================================================================
# Static import audit: SDK ownership + layer isolation, whole app
# =====================================================================
class GeminiSdkOwnershipAuditTests(unittest.TestCase):
    _ADAPTER_REL_PATH = Path("services", "multimodal_ai", "adapters", "gemini_adapter.py")

    @staticmethod
    def _app_root() -> Path:
        import app

        return Path(app.__file__).resolve().parent

    @classmethod
    def _iter_app_modules(cls):
        for path in cls._app_root().rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path

    @staticmethod
    def _import_names(path: Path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                yield node.module
                for alias in node.names:
                    yield f"{node.module}.{alias.name}"

    def test_only_gemini_adapter_imports_google_sdk(self):
        offenders = set()
        for path in self._iter_app_modules():
            roots = {name.split(".")[0] for name in self._import_names(path)}
            if roots & {"google", "vertexai"}:
                offenders.add(path.relative_to(self._app_root()))
        self.assertEqual(offenders, {self._ADAPTER_REL_PATH})

    def test_gemini_adapter_uses_official_sdk_not_deprecated_one(self):
        adapter_path = self._app_root() / self._ADAPTER_REL_PATH
        names = set(self._import_names(adapter_path))
        self.assertIn("google.genai", names)
        for name in names:
            self.assertFalse(name.startswith("google.generativeai"))

    def test_deprecated_sdk_used_nowhere_in_app(self):
        for path in self._iter_app_modules():
            for name in self._import_names(path):
                self.assertFalse(
                    name.startswith("google.generativeai"),
                    f"{path} imports deprecated google.generativeai",
                )

    def test_adapter_imports_no_http_streaming_or_cross_layer_modules(self):
        adapter_path = self._app_root() / self._ADAPTER_REL_PATH
        roots = {n.split(".")[0] for n in self._import_names(adapter_path)}
        forbidden = {
            "requests", "httpx", "aiohttp", "websocket", "websockets",
            "grpc", "socket", "asyncio", "openai", "anthropic", "boto3",
        }
        self.assertEqual(roots & forbidden, set())

    def test_adapter_app_imports_exactly_whitelisted(self):
        # No runtime, planner, orchestrator, interaction-service, or API import.
        adapter_path = self._app_root() / self._ADAPTER_REL_PATH
        app_imports = {
            n for n in self._import_names(adapter_path)
            if n.startswith("app.") and not n.startswith("app.services.multimodal_ai.adapters.base.")
        }
        app_modules = {
            n for n in app_imports
            if n in {
                "app.services.multimodal_ai.adapters.base",
                "app.services.multimodal_ai.models",
            }
            or n.rsplit(".", 1)[0] in {
                "app.services.multimodal_ai.adapters.base",
                "app.services.multimodal_ai.models",
            }
        }
        self.assertEqual(app_imports, app_modules)

    def test_dependencies_module_does_not_import_sdk(self):
        import app.core.dependencies as deps_module

        tree = ast.parse(inspect.getsource(deps_module))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        self.assertNotIn("google", roots)
        self.assertNotIn("vertexai", roots)

    def test_provider_remains_business_only_no_sdk_import(self):
        provider_path = (
            self._app_root()
            / "services" / "multimodal_ai" / "providers" / "gemini_provider.py"
        )
        roots = {n.split(".")[0] for n in self._import_names(provider_path)}
        self.assertNotIn("google", roots)
        self.assertNotIn("vertexai", roots)

    def test_provider_behavior_unchanged_pure_delegation(self):
        # Sprint 12.4 contract still holds: one delegation, result unchanged.
        adapter = MagicMock(name="MultimodalAIAdapter")
        expected = MultimodalAIResponse(response_text="ok")
        adapter.generate_response.return_value = expected
        provider = GeminiProvider(
            adapter,
            ProviderConfig(provider_name="gemini", default_model="m"),
        )
        result = provider.generate_response(_make_request())
        self.assertIs(result, expected)
        adapter.generate_response.assert_called_once()
        self.assertEqual(set(vars(provider)), {"adapter", "config"})

    def test_interaction_layer_untouched(self):
        interaction = importlib.import_module("app.services.interaction")
        self.assertEqual(
            set(interaction.__all__),
            {
                "InteractionService",
                "InteractionProvider",
                "InteractionType",
                "InteractionRequest",
                "InteractionResult",
            },
        )


if __name__ == "__main__":
    unittest.main()
