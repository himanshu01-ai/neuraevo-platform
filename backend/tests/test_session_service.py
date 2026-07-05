"""Unit tests for the Sprint 12.6 Session framework (abstraction only).

The provider is mocked, so no network, SDK, streaming, persistence, repository,
runtime, planner, or interaction is touched. The tests verify the provider
abstraction, that ``SessionService`` delegates each lifecycle method to the
injected provider exactly once (args forwarded, result returned unchanged,
exceptions propagated), that the service is a stateless, constructor-injected
pass-through, the enum vocabulary, the model contracts (validation + immutability
+ defaults + the computed ``is_active`` property), a static-import audit proving
the framework imports only its own package + stdlib/pydantic, and the
composition-root wiring.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_session_service
"""

import ast
import importlib
import inspect
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.services.session import (
    ConversationSession,
    SessionProvider,
    SessionResult,
    SessionService,
    SessionState,
)
from app.services.session.providers.base import (
    SessionProvider as BaseSessionProvider,
)


def _make_session(state=SessionState.ACTIVE, **overrides):
    now = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
    payload = {
        "session_id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "employee_id": uuid.uuid4(),
        "state": state,
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return ConversationSession(**payload)


# =====================================================================
# SessionState (enum vocabulary)
# =====================================================================
class SessionStateTests(unittest.TestCase):
    def test_is_str_enum(self):
        self.assertTrue(issubclass(SessionState, str))
        self.assertEqual(SessionState.ACTIVE, "active")

    def test_exact_member_set(self):
        self.assertEqual(
            {m.name for m in SessionState},
            {"CREATED", "ACTIVE", "PAUSED", "CLOSED", "FAILED"},
        )

    def test_member_values(self):
        self.assertEqual(SessionState.CREATED.value, "created")
        self.assertEqual(SessionState.ACTIVE.value, "active")
        self.assertEqual(SessionState.PAUSED.value, "paused")
        self.assertEqual(SessionState.CLOSED.value, "closed")
        self.assertEqual(SessionState.FAILED.value, "failed")


# =====================================================================
# Models: ConversationSession / SessionResult
# =====================================================================
class ConversationSessionModelTests(unittest.TestCase):
    def test_is_immutable(self):
        session = _make_session()
        with self.assertRaises(ValidationError):
            session.state = SessionState.CLOSED

    def test_metadata_defaults_empty(self):
        self.assertEqual(_make_session().metadata, {})

    def test_requires_all_identity_and_timestamps(self):
        with self.assertRaises(ValidationError):
            ConversationSession(session_id=uuid.uuid4())

    def test_rejects_invalid_state(self):
        with self.assertRaises(ValidationError):
            _make_session(state="bogus")

    def test_rejects_invalid_uuid(self):
        with self.assertRaises(ValidationError):
            _make_session(conversation_id="not-a-uuid")

    def test_accepts_state_value_string(self):
        session = _make_session(state="paused")
        self.assertIs(session.state, SessionState.PAUSED)

    def test_is_active_true_only_when_active(self):
        for state in SessionState:
            session = _make_session(state=state)
            self.assertEqual(
                session.is_active, state == SessionState.ACTIVE
            )

    def test_is_active_is_computed_not_stored(self):
        # Not a model field and not in the instance dict — purely derived.
        self.assertNotIn("is_active", ConversationSession.model_fields)
        self.assertNotIn("is_active", vars(_make_session()))

    def test_is_active_is_read_only(self):
        session = _make_session()
        with self.assertRaises((AttributeError, ValidationError)):
            session.is_active = True


class SessionResultModelTests(unittest.TestCase):
    def test_is_immutable(self):
        result = SessionResult(success=True)
        with self.assertRaises(ValidationError):
            result.success = False

    def test_defaults(self):
        result = SessionResult(success=False)
        self.assertFalse(result.success)
        self.assertIsNone(result.session)
        self.assertEqual(result.metadata, {})

    def test_requires_success(self):
        with self.assertRaises(ValidationError):
            SessionResult()

    def test_holds_session(self):
        session = _make_session()
        result = SessionResult(success=True, session=session, metadata={"x": 1})
        self.assertIs(result.session, session)
        self.assertEqual(result.metadata, {"x": 1})


# =====================================================================
# Provider abstraction
# =====================================================================
class SessionProviderAbstractionTests(unittest.TestCase):
    _ABSTRACT_METHODS = {
        "create_session",
        "pause_session",
        "resume_session",
        "close_session",
        "get_session",
        "health_check",
    }

    def test_provider_is_the_abstract_base(self):
        self.assertIs(SessionProvider, BaseSessionProvider)

    def test_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            SessionProvider()

    def test_all_lifecycle_methods_are_abstract(self):
        self.assertEqual(
            SessionProvider.__abstractmethods__, frozenset(self._ABSTRACT_METHODS)
        )

    def test_partial_implementation_remains_abstract(self):
        class Partial(SessionProvider):
            name = "partial"

            def create_session(self, conversation_id, employee_id, metadata=None):
                return SessionResult(success=True)

        with self.assertRaises(TypeError):
            Partial()

    def test_concrete_subclass_is_instantiable(self):
        class OkProvider(SessionProvider):
            name = "ok"

            def create_session(self, conversation_id, employee_id, metadata=None):
                return SessionResult(success=True)

            def pause_session(self, session_id):
                return SessionResult(success=True)

            def resume_session(self, session_id):
                return SessionResult(success=True)

            def close_session(self, session_id):
                return SessionResult(success=True)

            def get_session(self, session_id):
                return SessionResult(success=True)

            def health_check(self):
                return True

        self.assertIsInstance(OkProvider(), SessionProvider)


# =====================================================================
# SessionService (provider mocked): DI, statelessness, delegation
# =====================================================================
class SessionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conversation_id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.session_id = uuid.uuid4()
        self.metadata = {"trace": "abc"}
        self.result = SessionResult(success=True, session=_make_session())
        self.provider = MagicMock(name="SessionProvider")
        for method in (
            "create_session",
            "pause_session",
            "resume_session",
            "close_session",
            "get_session",
        ):
            getattr(self.provider, method).return_value = self.result
        self.provider.health_check.return_value = True
        self.service = SessionService(self.provider)

    def test_constructor_uses_injected_provider(self):
        self.assertIs(self.service.provider, self.provider)

    def test_stateless_only_injected_provider(self):
        self.assertEqual(set(vars(self.service)), {"provider"})

    def test_create_session_delegates_once_with_args(self):
        out = self.service.create_session(
            self.conversation_id, self.employee_id, self.metadata
        )
        self.provider.create_session.assert_called_once_with(
            self.conversation_id, self.employee_id, self.metadata
        )
        args = self.provider.create_session.call_args.args
        self.assertIs(args[0], self.conversation_id)
        self.assertIs(args[1], self.employee_id)
        self.assertIs(args[2], self.metadata)
        self.assertIs(out, self.result)

    def test_create_session_defaults_metadata_none(self):
        self.service.create_session(self.conversation_id, self.employee_id)
        self.provider.create_session.assert_called_once_with(
            self.conversation_id, self.employee_id, None
        )

    def test_pause_session_delegates_once_unchanged(self):
        out = self.service.pause_session(self.session_id)
        self.provider.pause_session.assert_called_once_with(self.session_id)
        self.assertIs(out, self.result)

    def test_resume_session_delegates_once_unchanged(self):
        out = self.service.resume_session(self.session_id)
        self.provider.resume_session.assert_called_once_with(self.session_id)
        self.assertIs(out, self.result)

    def test_close_session_delegates_once_unchanged(self):
        out = self.service.close_session(self.session_id)
        self.provider.close_session.assert_called_once_with(self.session_id)
        self.assertIs(out, self.result)

    def test_get_session_delegates_once_unchanged(self):
        out = self.service.get_session(self.session_id)
        self.provider.get_session.assert_called_once_with(self.session_id)
        self.assertIs(out, self.result)

    def test_health_check_delegates_once_unchanged(self):
        out = self.service.health_check()
        self.provider.health_check.assert_called_once_with()
        self.assertTrue(out)

    def test_exceptions_propagate(self):
        boom = RuntimeError("provider down")
        for method in (
            "create_session",
            "pause_session",
            "resume_session",
            "close_session",
            "get_session",
            "health_check",
        ):
            getattr(self.provider, method).side_effect = boom
        with self.assertRaises(RuntimeError):
            self.service.create_session(self.conversation_id, self.employee_id)
        with self.assertRaises(RuntimeError):
            self.service.pause_session(self.session_id)
        with self.assertRaises(RuntimeError):
            self.service.resume_session(self.session_id)
        with self.assertRaises(RuntimeError):
            self.service.close_session(self.session_id)
        with self.assertRaises(RuntimeError):
            self.service.get_session(self.session_id)
        with self.assertRaises(RuntimeError):
            self.service.health_check()


# =====================================================================
# Static import audit: only own package + stdlib/pydantic
# =====================================================================
class SessionImportAuditTests(unittest.TestCase):
    _MODULES = (
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
        "qdrant_client",
        "sqlalchemy",
        "boto3",
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

    def test_no_forbidden_sdk_network_persistence_roots(self):
        for name in self._MODULES:
            roots, _ = self._imports(name)
            self.assertEqual(
                roots & self._FORBIDDEN_ROOTS,
                set(),
                f"{name} imports a forbidden root",
            )

    def test_app_imports_stay_within_session_package(self):
        # No runtime / planner / interaction / multimodal / adapter / gemini /
        # memory / permission / tools / repositories / api imports anywhere.
        for name in self._MODULES:
            _, full = self._imports(name)
            for module_path in (m for m in full if m.startswith("app.")):
                self.assertTrue(
                    module_path.startswith("app.services.session"),
                    f"{name} imports outside the session package: {module_path}",
                )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class SessionDependencyTests(unittest.TestCase):
    def test_service_provider_resolves_with_injected_provider(self):
        from app.core.dependencies import get_session_service

        provider = MagicMock(name="SessionProvider")
        service = get_session_service(provider)
        self.assertIsInstance(service, SessionService)
        self.assertIs(service.provider, provider)

    def test_provider_seam_unfulfilled_until_later_sprint(self):
        from app.core.dependencies import get_session_provider

        with self.assertRaises(NotImplementedError):
            get_session_provider()

    def test_dep_aliases_exposed(self):
        from app.core import dependencies

        self.assertTrue(hasattr(dependencies, "SessionProviderDep"))
        self.assertTrue(hasattr(dependencies, "SessionServiceDep"))


if __name__ == "__main__":
    unittest.main()
