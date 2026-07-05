"""Unit tests for the Sprint 12.7 Gemini Live session provider (lifecycle only).

Everything is mocked — no real SDK client, no network, no Live session, no
streaming, no tokens. The tests verify: the provider is a concrete
``SessionProvider`` constructed by DI from a ``GenAIClientProtocol`` +
``ProviderConfig`` (never building an SDK object); its public surface is exactly
the injected collaborators while session state stays private; the full lifecycle
(create → resume → pause → resume → close) and every invalid transition
(``ValueError``); DTO integrity (the provider-independent ``ConversationSession``
is not extended and ``is_active`` is computed); the private ``_validate_transition``
matrix; ``health_check`` using only the client; and an AST import audit proving
the provider imports only its own package + the two injected-type modules and no
runtime/planner/interaction/memory/tool/repository/api/google-SDK modules.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_gemini_live_provider
"""

import ast
import importlib
import inspect
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.multimodal_ai.adapters import GenAIClientProtocol
from app.services.multimodal_ai.providers import ProviderConfig
from app.services.session import (
    ConversationSession,
    SessionProvider,
    SessionResult,
    SessionState,
)
from app.services.session.providers.gemini_live_provider import (
    GeminiLiveSessionProvider,
    LiveSessionProtocol,
)


def _make_client(list_ok=True):
    client = MagicMock(name="GenAIClient")
    if list_ok:
        client.models.list.return_value = [SimpleNamespace(name="m")]
    return client


def _make_config():
    return ProviderConfig(provider_name="gemini", default_model="gemini-2.5-flash")


def _make_provider(client=None, config=None):
    client = client if client is not None else _make_client()
    config = config if config is not None else _make_config()
    return GeminiLiveSessionProvider(client, config), client, config


def _new_session_id(provider, **meta):
    result = provider.create_session(uuid.uuid4(), uuid.uuid4(), meta or None)
    return result.session.session_id


# =====================================================================
# Concrete provider / construction / DI
# =====================================================================
class ConcreteProviderTests(unittest.TestCase):
    def test_subclasses_session_provider(self):
        self.assertTrue(issubclass(GeminiLiveSessionProvider, SessionProvider))

    def test_is_concrete_and_instantiable(self):
        provider, _, _ = _make_provider()
        self.assertFalse(inspect.isabstract(GeminiLiveSessionProvider))
        self.assertIsInstance(provider, SessionProvider)

    def test_name(self):
        provider, _, _ = _make_provider()
        self.assertEqual(provider.name, "gemini_live")

    def test_constructor_stores_injected_collaborators(self):
        provider, client, config = _make_provider()
        self.assertIs(provider.client, client)
        self.assertIs(provider.config, config)

    def test_public_vars_are_only_injected_collaborators(self):
        provider, _, _ = _make_provider()
        public = {k for k in vars(provider) if not k.startswith("_")}
        self.assertEqual(public, {"client", "config"})

    def test_no_sdk_client_constructed_internally(self):
        client = _make_client()
        provider = GeminiLiveSessionProvider(client, _make_config())
        # The client is exactly the injected object — never rebuilt internally.
        self.assertIs(provider.client, client)

    def test_constructor_depends_on_protocol_and_config(self):
        params = inspect.signature(
            GeminiLiveSessionProvider.__init__
        ).parameters
        self.assertIs(params["client"].annotation, GenAIClientProtocol)
        self.assertIs(params["config"].annotation, ProviderConfig)

    def test_provider_state_is_private(self):
        provider, _, _ = _make_provider()
        self.assertIn("_sessions", vars(provider))
        self.assertNotIn("sessions", vars(provider))
        _new_session_id(provider)
        # Created sessions live only in the private store, not the public surface.
        public = {k for k in vars(provider) if not k.startswith("_")}
        self.assertEqual(public, {"client", "config"})


# =====================================================================
# create_session
# =====================================================================
class CreateSessionTests(unittest.TestCase):
    def setUp(self):
        self.provider, _, _ = _make_provider()
        self.conversation_id = uuid.uuid4()
        self.employee_id = uuid.uuid4()

    def test_returns_success_and_created_session(self):
        result = self.provider.create_session(
            self.conversation_id, self.employee_id, {"k": "v"}
        )
        self.assertIsInstance(result, SessionResult)
        self.assertTrue(result.success)
        self.assertIsInstance(result.session, ConversationSession)
        self.assertEqual(result.session.state, SessionState.CREATED)
        self.assertFalse(result.session.is_active)

    def test_binds_conversation_and_employee_and_metadata(self):
        result = self.provider.create_session(
            self.conversation_id, self.employee_id, {"k": "v"}
        )
        session = result.session
        self.assertEqual(session.conversation_id, self.conversation_id)
        self.assertEqual(session.employee_id, self.employee_id)
        self.assertEqual(session.metadata, {"k": "v"})

    def test_metadata_defaults_empty(self):
        result = self.provider.create_session(
            self.conversation_id, self.employee_id
        )
        self.assertEqual(result.session.metadata, {})

    def test_each_session_has_unique_id_and_is_tracked(self):
        a = self.provider.create_session(self.conversation_id, self.employee_id)
        b = self.provider.create_session(self.conversation_id, self.employee_id)
        self.assertNotEqual(a.session.session_id, b.session.session_id)
        self.assertEqual(len(self.provider._sessions), 2)

    def test_create_opens_no_live_session(self):
        result = self.provider.create_session(
            self.conversation_id, self.employee_id
        )
        record = self.provider._sessions[result.session.session_id]
        self.assertIsNone(record.live)  # no Live session opened this sprint


# =====================================================================
# Lifecycle — happy path
# =====================================================================
class LifecycleHappyPathTests(unittest.TestCase):
    def setUp(self):
        self.provider, _, _ = _make_provider()
        self.sid = _new_session_id(self.provider)

    def test_full_cycle_create_resume_pause_resume_close(self):
        r1 = self.provider.resume_session(self.sid)  # CREATED -> ACTIVE
        self.assertTrue(r1.success)
        self.assertEqual(r1.session.state, SessionState.ACTIVE)
        self.assertTrue(r1.session.is_active)

        r2 = self.provider.pause_session(self.sid)  # ACTIVE -> PAUSED
        self.assertEqual(r2.session.state, SessionState.PAUSED)
        self.assertFalse(r2.session.is_active)

        r3 = self.provider.resume_session(self.sid)  # PAUSED -> ACTIVE
        self.assertEqual(r3.session.state, SessionState.ACTIVE)

        r4 = self.provider.close_session(self.sid)  # ACTIVE -> CLOSED
        self.assertEqual(r4.session.state, SessionState.CLOSED)

    def test_get_reflects_current_state(self):
        self.provider.resume_session(self.sid)
        got = self.provider.get_session(self.sid)
        self.assertTrue(got.success)
        self.assertEqual(got.session.state, SessionState.ACTIVE)

    def test_transition_updates_timestamp_and_preserves_identity(self):
        before = self.provider.get_session(self.sid).session
        after = self.provider.resume_session(self.sid).session
        self.assertEqual(after.session_id, before.session_id)
        self.assertEqual(after.created_at, before.created_at)
        self.assertGreaterEqual(after.updated_at, before.updated_at)


# =====================================================================
# Lifecycle — invalid transitions raise ValueError
# =====================================================================
class InvalidTransitionTests(unittest.TestCase):
    def setUp(self):
        self.provider, _, _ = _make_provider()

    def test_pause_created_raises(self):
        sid = _new_session_id(self.provider)
        with self.assertRaises(ValueError):
            self.provider.pause_session(sid)

    def test_resume_active_raises(self):
        sid = _new_session_id(self.provider)
        self.provider.resume_session(sid)  # -> ACTIVE
        with self.assertRaises(ValueError):
            self.provider.resume_session(sid)  # ACTIVE -> ACTIVE invalid

    def test_pause_paused_raises(self):
        sid = _new_session_id(self.provider)
        self.provider.resume_session(sid)
        self.provider.pause_session(sid)  # -> PAUSED
        with self.assertRaises(ValueError):
            self.provider.pause_session(sid)  # PAUSED -> PAUSED invalid

    def test_close_created_raises(self):
        sid = _new_session_id(self.provider)
        with self.assertRaises(ValueError):
            self.provider.close_session(sid)  # CLOSED only reachable from ACTIVE

    def test_close_paused_raises(self):
        sid = _new_session_id(self.provider)
        self.provider.resume_session(sid)
        self.provider.pause_session(sid)
        with self.assertRaises(ValueError):
            self.provider.close_session(sid)

    def test_resume_and_close_after_close_raise(self):
        sid = _new_session_id(self.provider)
        self.provider.resume_session(sid)
        self.provider.close_session(sid)  # -> CLOSED (terminal)
        with self.assertRaises(ValueError):
            self.provider.resume_session(sid)
        with self.assertRaises(ValueError):
            self.provider.close_session(sid)

    def test_missing_session_is_soft_failure_not_exception(self):
        missing = uuid.uuid4()
        for op in (
            self.provider.pause_session,
            self.provider.resume_session,
            self.provider.close_session,
        ):
            result = op(missing)
            self.assertFalse(result.success)
            self.assertIsNone(result.session)


# =====================================================================
# Private transition validator — full matrix
# =====================================================================
class TransitionValidatorMatrixTests(unittest.TestCase):
    _ALLOWED = {
        (SessionState.CREATED, SessionState.ACTIVE),
        (SessionState.CREATED, SessionState.FAILED),
        (SessionState.ACTIVE, SessionState.PAUSED),
        (SessionState.ACTIVE, SessionState.CLOSED),
        (SessionState.ACTIVE, SessionState.FAILED),
        (SessionState.PAUSED, SessionState.ACTIVE),
        (SessionState.PAUSED, SessionState.FAILED),
    }

    def test_full_matrix(self):
        provider, _, _ = _make_provider()
        for current in SessionState:
            for target in SessionState:
                if (current, target) in self._ALLOWED:
                    provider._validate_transition(current, target)  # no raise
                else:
                    with self.assertRaises(ValueError):
                        provider._validate_transition(current, target)

    def test_failed_reachable_from_every_live_state(self):
        provider, _, _ = _make_provider()
        for live in (
            SessionState.CREATED,
            SessionState.ACTIVE,
            SessionState.PAUSED,
        ):
            provider._validate_transition(live, SessionState.FAILED)

    def test_terminal_states_have_no_outgoing_transitions(self):
        provider, _, _ = _make_provider()
        for terminal in (SessionState.CLOSED, SessionState.FAILED):
            for target in SessionState:
                with self.assertRaises(ValueError):
                    provider._validate_transition(terminal, target)


# =====================================================================
# get_session / health_check
# =====================================================================
class GetSessionAndHealthTests(unittest.TestCase):
    def test_get_missing_session_soft_failure(self):
        provider, _, _ = _make_provider()
        result = provider.get_session(uuid.uuid4())
        self.assertFalse(result.success)
        self.assertIsNone(result.session)

    def test_health_check_true_when_client_usable(self):
        client = _make_client(list_ok=True)
        provider = GeminiLiveSessionProvider(client, _make_config())
        self.assertTrue(provider.health_check())
        client.models.list.assert_called_once_with()

    def test_health_check_uses_only_client_no_session_or_generation(self):
        client = _make_client()
        provider = GeminiLiveSessionProvider(client, _make_config())
        provider.health_check()
        client.models.generate_content.assert_not_called()
        self.assertEqual(provider._sessions, {})  # no session created

    def test_health_check_false_on_client_failure(self):
        client = _make_client()
        client.models.list.side_effect = RuntimeError("unauthorized")
        provider = GeminiLiveSessionProvider(client, _make_config())
        self.assertFalse(provider.health_check())

    def test_health_check_never_raises_for_broken_client(self):
        provider = GeminiLiveSessionProvider(object(), _make_config())
        self.assertFalse(provider.health_check())


# =====================================================================
# DTO integrity / SPI shape
# =====================================================================
class DtoIntegrityTests(unittest.TestCase):
    def test_conversation_session_not_extended(self):
        self.assertEqual(
            set(ConversationSession.model_fields),
            {
                "session_id",
                "conversation_id",
                "employee_id",
                "state",
                "created_at",
                "updated_at",
                "metadata",
            },
        )

    def test_results_are_provider_independent_dtos(self):
        provider, _, _ = _make_provider()
        result = provider.create_session(uuid.uuid4(), uuid.uuid4())
        self.assertIsInstance(result, SessionResult)
        self.assertIsInstance(result.session, ConversationSession)

    def test_live_session_protocol_is_structural(self):
        self.assertTrue(hasattr(LiveSessionProtocol, "__subclasshook__"))


# =====================================================================
# Static import audit
# =====================================================================
class ImportAuditTests(unittest.TestCase):
    _MODULE = "app.services.session.providers.gemini_live_provider"
    _OTHER_SESSION_MODULES = (
        "app.services.session",
        "app.services.session.models",
        "app.services.session.session_service",
        "app.services.session.providers",
        "app.services.session.providers.base",
    )
    _FORBIDDEN_ROOTS = {
        "google",
        "vertexai",
        "openai",
        "anthropic",
        "requests",
        "httpx",
        "aiohttp",
        "websocket",
        "websockets",
        "grpc",
        "socket",
        "asyncio",
        "sqlalchemy",
        "qdrant_client",
        "boto3",
    }
    _ALLOWED_APP_IMPORTS = {
        "app.services.session.models",
        "app.services.session.providers.base",
        "app.services.multimodal_ai.adapters",   # GenAIClientProtocol (injected)
        "app.services.multimodal_ai.providers",  # ProviderConfig (injected)
    }

    def _imports(self, module_name):
        module = importlib.import_module(module_name)
        tree = ast.parse(inspect.getsource(module))
        roots, modules = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    roots.add(alias.name.split(".")[0])
                    modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
                modules.add(node.module)
        return roots, modules

    def test_no_forbidden_sdk_network_persistence_roots(self):
        roots, _ = self._imports(self._MODULE)
        self.assertEqual(roots & self._FORBIDDEN_ROOTS, set())

    def test_provider_does_not_import_google_sdk_directly(self):
        roots, _ = self._imports(self._MODULE)
        self.assertNotIn("google", roots)
        self.assertNotIn("vertexai", roots)

    def test_app_imports_exactly_whitelisted(self):
        # No runtime / planner / interaction / memory / tool / repository / api
        # / orchestrator imports — only own package + the two injected-type modules.
        _, modules = self._imports(self._MODULE)
        app_imports = {m for m in modules if m.startswith("app.")}
        self.assertEqual(app_imports, self._ALLOWED_APP_IMPORTS)

    def test_other_session_modules_import_no_sdk_types(self):
        for name in self._OTHER_SESSION_MODULES:
            _, modules = self._imports(name)
            for module_path in modules:
                self.assertFalse(module_path.startswith("google"))
                self.assertFalse(
                    module_path.startswith("app.services.multimodal_ai"),
                    f"{name} should not import multimodal_ai types",
                )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyTests(unittest.TestCase):
    def test_get_gemini_live_session_provider_injects_deps(self):
        from app.core.dependencies import get_gemini_live_session_provider

        client = _make_client()
        config = _make_config()
        provider = get_gemini_live_session_provider(client, config)
        self.assertIsInstance(provider, GeminiLiveSessionProvider)
        self.assertIs(provider.client, client)
        self.assertIs(provider.config, config)

    def test_dep_alias_exposed(self):
        from app.core import dependencies

        self.assertTrue(hasattr(dependencies, "GeminiLiveSessionProviderDep"))

    def test_generic_session_seam_unchanged(self):
        # Sprint 12.6 seam remains intentionally unfulfilled; 12.7 does NOT
        # replace it (the Gemini Live provider is a separate, additive seam).
        from app.core.dependencies import get_session_provider

        with self.assertRaises(NotImplementedError):
            get_session_provider()

    def test_session_service_seam_unchanged(self):
        from app.core.dependencies import get_session_service

        provider = MagicMock(name="SessionProvider")
        service = get_session_service(provider)
        self.assertIs(service.provider, provider)


if __name__ == "__main__":
    unittest.main()
