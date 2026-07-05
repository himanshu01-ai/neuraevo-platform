"""Unit tests for the Sprint 12.8 Gemini Live session provider (real lifecycle).

Everything is mocked — a fake async context manager stands in for the SDK Live
session, so no network, no real SDK, no API key, and no messages/streaming are
involved. The provider's real sync<->async bridge (background event loop) drives
the fakes. The tests verify: successful Live-session creation (CREATED -> ACTIVE
with exactly one SDK connect and a privately-stored handle); failed creation
(cleanup + FAILED + success=False, no leaked handle); clean close (exactly one
SDK close, handle removed); provider-private handle; DTO/SPI unchanged; exception
propagation for invalid transitions; health_check using only the client (no Live
session, no generation); dependency injection; and a static import audit proving
the provider imports no SDK/network/streaming modules and no cross-layer modules.

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
    VisualInput,
    VisualSource,
    _AudioTransport,
    _LiveSessionHandle,
    _StreamAggregator,
    _VisualTransport,
)
from pydantic import ValidationError


class _FakeAsyncCM:
    """Fake async context manager standing in for the SDK Live connection."""

    def __init__(self, session=None, fail_on_enter=False):
        self._session = session if session is not None else object()
        self._fail_on_enter = fail_on_enter
        self.enter_count = 0
        self.exit_count = 0

    async def __aenter__(self):
        self.enter_count += 1
        if self._fail_on_enter:
            raise RuntimeError("live connect failed")
        return self._session

    async def __aexit__(self, *exc):
        self.exit_count += 1
        return False


def _make_config():
    return ProviderConfig(provider_name="gemini", default_model="gemini-2.5-flash")


def _make_client(cm=None):
    client = MagicMock(name="GenAIClient")
    client.models.list.return_value = [SimpleNamespace(name="m")]
    if cm is not None:
        client.aio.live.connect = MagicMock(return_value=cm)
    return client


def _make_provider(cm=None, config=None):
    client = _make_client(cm=cm)
    provider = GeminiLiveSessionProvider(
        client, config if config is not None else _make_config()
    )
    return provider, client


# =====================================================================
# Successful Live-session creation
# =====================================================================
class CreateSuccessTests(unittest.TestCase):
    def setUp(self):
        self.cm = _FakeAsyncCM(session=SimpleNamespace(id="sdk-sess"))
        self.provider, self.client = _make_provider(cm=self.cm)

    def test_creates_active_session_on_successful_connect(self):
        result = self.provider.create_session(
            uuid.uuid4(), uuid.uuid4(), {"model": "gemini-live-x"}
        )
        self.assertIsInstance(result, SessionResult)
        self.assertTrue(result.success)
        self.assertIsInstance(result.session, ConversationSession)
        self.assertEqual(result.session.state, SessionState.ACTIVE)
        self.assertTrue(result.session.is_active)

    def test_exactly_one_sdk_connect(self):
        self.provider.create_session(uuid.uuid4(), uuid.uuid4(), {"model": "m"})
        self.client.aio.live.connect.assert_called_once()
        self.assertEqual(self.cm.enter_count, 1)
        self.assertEqual(self.cm.exit_count, 0)  # not closed yet

    def test_model_taken_from_metadata(self):
        self.provider.create_session(
            uuid.uuid4(), uuid.uuid4(), {"model": "gemini-live-x"}
        )
        self.assertEqual(
            self.client.aio.live.connect.call_args.kwargs["model"],
            "gemini-live-x",
        )

    def test_model_falls_back_to_config_default(self):
        self.provider.create_session(uuid.uuid4(), uuid.uuid4())
        self.assertEqual(
            self.client.aio.live.connect.call_args.kwargs["model"],
            "gemini-2.5-flash",
        )

    def test_handle_stored_privately_and_wraps_sdk_session(self):
        result = self.provider.create_session(
            uuid.uuid4(), uuid.uuid4(), {"model": "m"}
        )
        record = self.provider._sessions[result.session.session_id]
        self.assertIsInstance(record.handle, _LiveSessionHandle)
        self.assertIs(record.handle.cm, self.cm)
        self.assertEqual(record.handle.sdk_session.id, "sdk-sess")

    def test_sdk_session_never_escapes_in_result(self):
        result = self.provider.create_session(
            uuid.uuid4(), uuid.uuid4(), {"model": "m"}
        )
        # The public result carries only the provider-independent DTO.
        self.assertEqual(
            set(result.session.model_dump().keys()),
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


# =====================================================================
# Failed Live-session creation
# =====================================================================
class CreateFailureTests(unittest.TestCase):
    def setUp(self):
        self.cm = _FakeAsyncCM(fail_on_enter=True)
        self.provider, self.client = _make_provider(cm=self.cm)

    def test_failed_connect_yields_failed_state_and_unsuccessful_result(self):
        result = self.provider.create_session(
            uuid.uuid4(), uuid.uuid4(), {"model": "m"}
        )
        self.assertFalse(result.success)
        self.assertEqual(result.session.state, SessionState.FAILED)
        self.assertFalse(result.session.is_active)

    def test_connect_attempted_once_and_no_handle_leaked(self):
        result = self.provider.create_session(
            uuid.uuid4(), uuid.uuid4(), {"model": "m"}
        )
        self.assertEqual(self.cm.enter_count, 1)
        record = self.provider._sessions[result.session.session_id]
        self.assertIsNone(record.handle)  # cleaned up — no leak

    def test_failure_does_not_propagate_exception(self):
        # Connection errors are handled (FAILED), not raised, per the SPI.
        try:
            self.provider.create_session(uuid.uuid4(), uuid.uuid4(), {"model": "m"})
        except Exception as exc:  # pragma: no cover
            self.fail(f"create_session should not raise, got {exc!r}")


# =====================================================================
# Clean close / cleanup
# =====================================================================
class CloseTests(unittest.TestCase):
    def setUp(self):
        self.cm = _FakeAsyncCM(session=SimpleNamespace(id="s"))
        self.provider, self.client = _make_provider(cm=self.cm)
        self.sid = self.provider.create_session(
            uuid.uuid4(), uuid.uuid4(), {"model": "m"}
        ).session.session_id

    def test_close_transitions_to_closed(self):
        result = self.provider.close_session(self.sid)
        self.assertTrue(result.success)
        self.assertEqual(result.session.state, SessionState.CLOSED)

    def test_exactly_one_sdk_close(self):
        self.provider.close_session(self.sid)
        self.assertEqual(self.cm.exit_count, 1)

    def test_close_removes_private_handle(self):
        self.provider.close_session(self.sid)
        self.assertIsNone(self.provider._sessions[self.sid].handle)

    def test_double_close_is_invalid_transition(self):
        self.provider.close_session(self.sid)
        with self.assertRaises(ValueError):
            self.provider.close_session(self.sid)  # CLOSED -> CLOSED invalid

    def test_cleanup_is_best_effort_on_sdk_error(self):
        # Even if the SDK close errors, close_session completes and drops handle.
        cm = _FakeAsyncCM(session=SimpleNamespace(id="s"))

        async def _boom(*a):
            raise RuntimeError("sdk close error")

        cm.__aexit__ = _boom
        provider, _ = _make_provider(cm=cm)
        sid = provider.create_session(
            uuid.uuid4(), uuid.uuid4(), {"model": "m"}
        ).session.session_id
        result = provider.close_session(sid)
        self.assertTrue(result.success)
        self.assertEqual(result.session.state, SessionState.CLOSED)
        self.assertIsNone(provider._sessions[sid].handle)


# =====================================================================
# Construction / DI / private state
# =====================================================================
class ConstructionTests(unittest.TestCase):
    def test_subclasses_session_provider_and_concrete(self):
        provider, _ = _make_provider()
        self.assertTrue(issubclass(GeminiLiveSessionProvider, SessionProvider))
        self.assertFalse(inspect.isabstract(GeminiLiveSessionProvider))
        self.assertIsInstance(provider, SessionProvider)

    def test_public_vars_are_only_injected_collaborators(self):
        provider, client = _make_provider()
        public = {k for k in vars(provider) if not k.startswith("_")}
        self.assertEqual(public, {"client", "config"})
        self.assertIs(provider.client, client)

    def test_constructor_depends_on_protocol_and_config(self):
        params = inspect.signature(
            GeminiLiveSessionProvider.__init__
        ).parameters
        self.assertIs(params["client"].annotation, GenAIClientProtocol)
        self.assertIs(params["config"].annotation, ProviderConfig)

    def test_no_background_loop_until_a_session_opens(self):
        provider, _ = _make_provider()
        self.assertIsNone(provider._loop)  # lazily started only on connect

    def test_dto_not_extended(self):
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

    def test_live_session_protocol_is_structural(self):
        self.assertTrue(hasattr(LiveSessionProtocol, "__subclasshook__"))


# =====================================================================
# Lifecycle transitions / exception propagation (no SDK effect)
# =====================================================================
class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.cm = _FakeAsyncCM(session=SimpleNamespace(id="s"))
        self.provider, _ = _make_provider(cm=self.cm)
        self.sid = self.provider.create_session(
            uuid.uuid4(), uuid.uuid4(), {"model": "m"}
        ).session.session_id  # ACTIVE

    def test_pause_then_resume(self):
        self.assertEqual(
            self.provider.pause_session(self.sid).session.state,
            SessionState.PAUSED,
        )
        self.assertEqual(
            self.provider.resume_session(self.sid).session.state,
            SessionState.ACTIVE,
        )

    def test_resume_active_raises(self):
        with self.assertRaises(ValueError):
            self.provider.resume_session(self.sid)  # ACTIVE -> ACTIVE invalid

    def test_close_from_paused_raises(self):
        self.provider.pause_session(self.sid)
        with self.assertRaises(ValueError):
            self.provider.close_session(self.sid)

    def test_missing_session_soft_failure(self):
        missing = uuid.uuid4()
        for op in (
            self.provider.pause_session,
            self.provider.resume_session,
            self.provider.close_session,
            self.provider.get_session,
        ):
            result = op(missing)
            self.assertFalse(result.success)
            self.assertIsNone(result.session)

    def test_validator_matrix(self):
        allowed = {
            (SessionState.CREATED, SessionState.ACTIVE),
            (SessionState.CREATED, SessionState.FAILED),
            (SessionState.ACTIVE, SessionState.PAUSED),
            (SessionState.ACTIVE, SessionState.CLOSED),
            (SessionState.ACTIVE, SessionState.FAILED),
            (SessionState.PAUSED, SessionState.ACTIVE),
            (SessionState.PAUSED, SessionState.FAILED),
        }
        for current in SessionState:
            for target in SessionState:
                if (current, target) in allowed:
                    self.provider._validate_transition(current, target)
                else:
                    with self.assertRaises(ValueError):
                        self.provider._validate_transition(current, target)


# =====================================================================
# health_check
# =====================================================================
class HealthCheckTests(unittest.TestCase):
    def test_true_when_client_usable_and_opens_no_live_session(self):
        provider, client = _make_provider()
        self.assertTrue(provider.health_check())
        client.models.list.assert_called_once_with()
        client.aio.live.connect.assert_not_called()

    def test_false_on_client_failure(self):
        provider, client = _make_provider()
        client.models.list.side_effect = RuntimeError("unauthorized")
        self.assertFalse(provider.health_check())

    def test_never_raises_for_broken_client(self):
        provider = GeminiLiveSessionProvider(object(), _make_config())
        self.assertFalse(provider.health_check())


# =====================================================================
# Static import audit
# =====================================================================
class ImportAuditTests(unittest.TestCase):
    _MODULE = "app.services.session.providers.gemini_live_provider"
    # asyncio/threading are now legitimately required for the async<->sync bridge.
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

    def test_no_forbidden_roots(self):
        roots, _ = self._imports(self._MODULE)
        self.assertEqual(roots & self._FORBIDDEN_ROOTS, set())

    def test_provider_does_not_import_google_sdk_directly(self):
        roots, _ = self._imports(self._MODULE)
        self.assertNotIn("google", roots)
        self.assertNotIn("vertexai", roots)

    def test_app_imports_exactly_whitelisted(self):
        _, modules = self._imports(self._MODULE)
        app_imports = {m for m in modules if m.startswith("app.")}
        self.assertEqual(app_imports, self._ALLOWED_APP_IMPORTS)


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
        from app.core.dependencies import get_session_provider

        with self.assertRaises(NotImplementedError):
            get_session_provider()


# =====================================================================
# Sprint 12.9 — Live text messaging
# =====================================================================
def _text_msg(text):
    return SimpleNamespace(text=text, server_content=None)


def _transcript_msg(text):
    return SimpleNamespace(
        text=None,
        server_content=SimpleNamespace(
            output_transcription=SimpleNamespace(text=text)
        ),
    )


class _FakeSDKSession:
    """Fake SDK AsyncSession for messaging tests (send + streamed receive)."""

    def __init__(self, messages=(), send_error=None, receive_error=None):
        self._messages = list(messages)
        self._send_error = send_error
        self._receive_error = receive_error
        self.send_count = 0
        self.receive_count = 0
        self.sent = []
        self.realtime_sends = 0
        self.realtime_sent = []

    async def send_client_content(self, **kwargs):
        self.send_count += 1
        self.sent.append(kwargs)
        if self._send_error is not None:
            raise self._send_error

    async def send_realtime_input(self, **kwargs):
        self.realtime_sends += 1
        self.realtime_sent.append(kwargs)
        if self._send_error is not None:
            raise self._send_error

    def receive(self):
        self.receive_count += 1
        return self._agen()

    async def _agen(self):
        if self._receive_error is not None:
            raise self._receive_error
        for message in self._messages:
            yield message

    async def __aexit__(self, *exc):  # for close via the CM
        return False


def _messaging_provider(messages=(), **session_kwargs):
    sdk = _FakeSDKSession(messages=messages, **session_kwargs)
    cm = _FakeAsyncCM(session=sdk)
    provider, client = _make_provider(cm=cm)
    sid = provider.create_session(
        uuid.uuid4(), uuid.uuid4(), {"model": "m"}
    ).session.session_id
    return provider, sdk, sid, client


class SendMessageTests(unittest.TestCase):
    def test_send_returns_success_and_session_stays_active(self):
        provider, sdk, sid, _ = _messaging_provider()
        result = provider.send_message(sid, "hello")
        self.assertTrue(result.success)
        self.assertEqual(result.session.state, SessionState.ACTIVE)

    def test_exactly_one_send_with_user_text_turn(self):
        provider, sdk, sid, _ = _messaging_provider()
        provider.send_message(sid, "hello world")
        self.assertEqual(sdk.send_count, 1)
        turns = sdk.sent[0]["turns"]
        self.assertEqual(turns["role"], "user")
        self.assertEqual(turns["parts"][0]["text"], "hello world")
        self.assertTrue(sdk.sent[0]["turn_complete"])

    def test_send_missing_session_raises(self):
        provider, _, _, _ = _messaging_provider()
        with self.assertRaises(ValueError):
            provider.send_message(uuid.uuid4(), "hi")

    def test_send_inactive_session_raises(self):
        provider, sdk, sid, _ = _messaging_provider()
        provider.pause_session(sid)  # ACTIVE -> PAUSED
        with self.assertRaises(ValueError):
            provider.send_message(sid, "hi")
        self.assertEqual(sdk.send_count, 0)  # rejected before any SDK call

    def test_send_exception_propagates(self):
        provider, sdk, sid, _ = _messaging_provider(
            send_error=RuntimeError("sdk send boom")
        )
        with self.assertRaises(RuntimeError):
            provider.send_message(sid, "hi")


class ReceiveResponseTests(unittest.TestCase):
    def test_aggregates_text_chunks_into_one_string(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_text_msg("Neura"), _text_msg("Evo"), _text_msg(" Works")]
        )
        result = provider.receive_response(sid)
        self.assertEqual(result, "NeuraEvo Works")
        self.assertIsInstance(result, str)

    def test_exactly_one_receive(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_text_msg("a")]
        )
        provider.receive_response(sid)
        self.assertEqual(sdk.receive_count, 1)

    def test_ignores_empty_and_none_chunks(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[
                _text_msg("A"),
                _text_msg(""),
                _text_msg(None),
                _text_msg("B"),
            ]
        )
        self.assertEqual(provider.receive_response(sid), "AB")

    def test_preserves_order(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_text_msg("1"), _text_msg("2"), _text_msg("3")]
        )
        self.assertEqual(provider.receive_response(sid), "123")

    def test_aggregates_output_audio_transcription(self):
        # Audio-native Live models stream text via output transcription.
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_transcript_msg("Neura"), _transcript_msg("Evo Live")]
        )
        self.assertEqual(provider.receive_response(sid), "NeuraEvo Live")

    def test_receive_missing_session_raises(self):
        provider, _, _, _ = _messaging_provider()
        with self.assertRaises(ValueError):
            provider.receive_response(uuid.uuid4())

    def test_receive_inactive_session_raises(self):
        provider, sdk, sid, _ = _messaging_provider(messages=[_text_msg("x")])
        provider.pause_session(sid)
        with self.assertRaises(ValueError):
            provider.receive_response(sid)
        self.assertEqual(sdk.receive_count, 0)

    def test_receive_exception_propagates(self):
        provider, sdk, sid, _ = _messaging_provider(
            receive_error=RuntimeError("stream boom")
        )
        with self.assertRaises(RuntimeError):
            provider.receive_response(sid)


class StreamAggregatorTests(unittest.TestCase):
    def test_collects_orders_and_joins(self):
        agg = _StreamAggregator()
        agg.add("Hello, ")
        agg.add("World")
        self.assertEqual(agg.result(), "Hello, World")

    def test_ignores_empty_and_none(self):
        agg = _StreamAggregator()
        agg.add("A")
        agg.add("")
        agg.add(None)
        agg.add("B")
        self.assertEqual(agg.result(), "AB")

    def test_empty_aggregator_returns_empty_string(self):
        self.assertEqual(_StreamAggregator().result(), "")

    def test_is_a_private_module_member(self):
        self.assertTrue(_StreamAggregator.__name__.startswith("_"))


class MessagingConfigAndSpiTests(unittest.TestCase):
    def test_connect_enables_output_transcription(self):
        _, _, _, client = _messaging_provider()
        self.assertEqual(
            client.aio.live.connect.call_args.kwargs.get("config"),
            {"output_audio_transcription": {}},
        )

    def test_session_spi_unchanged_and_messaging_is_provider_only(self):
        from app.services.session.providers.base import (
            SessionProvider as SPI,
        )

        self.assertEqual(
            SPI.__abstractmethods__,
            frozenset(
                {
                    "create_session",
                    "pause_session",
                    "resume_session",
                    "close_session",
                    "get_session",
                    "health_check",
                }
            ),
        )
        self.assertFalse(hasattr(SPI, "send_message"))
        self.assertFalse(hasattr(SPI, "receive_response"))
        self.assertFalse(hasattr(SPI, "send_audio_chunk"))
        self.assertFalse(hasattr(SPI, "receive_audio_chunk"))
        self.assertFalse(hasattr(SPI, "send_visual_input"))
        self.assertFalse(hasattr(SPI, "receive_visual_response"))


# =====================================================================
# Sprint 12.10 — Live audio transport
# =====================================================================
def _audio_msg(data):
    return SimpleNamespace(data=data)


class SendAudioTests(unittest.TestCase):
    def test_send_returns_success_and_session_stays_active(self):
        provider, sdk, sid, _ = _messaging_provider()
        result = provider.send_audio_chunk(sid, b"\x01\x02\x03\x04")
        self.assertTrue(result.success)
        self.assertEqual(result.session.state, SessionState.ACTIVE)

    def test_exactly_one_audio_send_as_realtime_blob(self):
        provider, sdk, sid, _ = _messaging_provider()
        provider.send_audio_chunk(sid, b"\x10\x20\x30\x40")
        self.assertEqual(sdk.realtime_sends, 1)
        blob = sdk.realtime_sent[0]["audio"]
        self.assertEqual(blob["data"], b"\x10\x20\x30\x40")
        self.assertEqual(blob["mime_type"], "audio/pcm;rate=16000")

    def test_accepts_bytearray(self):
        provider, sdk, sid, _ = _messaging_provider()
        result = provider.send_audio_chunk(sid, bytearray(b"\xaa\xbb"))
        self.assertTrue(result.success)
        self.assertEqual(sdk.realtime_sent[0]["audio"]["data"], b"\xaa\xbb")

    def test_send_missing_session_raises(self):
        provider, _, _, _ = _messaging_provider()
        with self.assertRaises(ValueError):
            provider.send_audio_chunk(uuid.uuid4(), b"\x01\x02")

    def test_send_inactive_session_raises(self):
        provider, sdk, sid, _ = _messaging_provider()
        provider.pause_session(sid)
        with self.assertRaises(ValueError):
            provider.send_audio_chunk(sid, b"\x01\x02")
        self.assertEqual(sdk.realtime_sends, 0)

    def test_empty_chunk_rejected(self):
        provider, sdk, sid, _ = _messaging_provider()
        with self.assertRaises(ValueError):
            provider.send_audio_chunk(sid, b"")
        self.assertEqual(sdk.realtime_sends, 0)

    def test_non_bytes_chunk_rejected(self):
        provider, sdk, sid, _ = _messaging_provider()
        with self.assertRaises(TypeError):
            provider.send_audio_chunk(sid, "not-bytes")
        self.assertEqual(sdk.realtime_sends, 0)

    def test_malformed_pcm_length_rejected(self):
        provider, sdk, sid, _ = _messaging_provider()
        with self.assertRaises(ValueError):
            provider.send_audio_chunk(sid, b"\x01\x02\x03")  # odd length
        self.assertEqual(sdk.realtime_sends, 0)

    def test_send_exception_propagates(self):
        provider, sdk, sid, _ = _messaging_provider(
            send_error=RuntimeError("sdk realtime boom")
        )
        with self.assertRaises(RuntimeError):
            provider.send_audio_chunk(sid, b"\x01\x02")


class ReceiveAudioTests(unittest.TestCase):
    def test_aggregates_audio_bytes_in_order(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_audio_msg(b"\x01\x02"), _audio_msg(b"\x03\x04")]
        )
        result = provider.receive_audio_chunk(sid)
        self.assertEqual(result, b"\x01\x02\x03\x04")
        self.assertIsInstance(result, bytes)

    def test_exactly_one_receive(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_audio_msg(b"\x01\x02")]
        )
        provider.receive_audio_chunk(sid)
        self.assertEqual(sdk.receive_count, 1)

    def test_ignores_empty_audio_chunks(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[
                _audio_msg(b"\x01"),
                _audio_msg(b""),
                _audio_msg(None),
                _audio_msg(b"\x02"),
            ]
        )
        self.assertEqual(provider.receive_audio_chunk(sid), b"\x01\x02")

    def test_preserves_order(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_audio_msg(bytes([i])) for i in range(5)]
        )
        self.assertEqual(
            provider.receive_audio_chunk(sid), bytes(range(5))
        )

    def test_receive_missing_session_raises(self):
        provider, _, _, _ = _messaging_provider()
        with self.assertRaises(ValueError):
            provider.receive_audio_chunk(uuid.uuid4())

    def test_receive_inactive_session_raises(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_audio_msg(b"\x01\x02")]
        )
        provider.pause_session(sid)
        with self.assertRaises(ValueError):
            provider.receive_audio_chunk(sid)
        self.assertEqual(sdk.receive_count, 0)

    def test_receive_exception_propagates(self):
        provider, sdk, sid, _ = _messaging_provider(
            receive_error=RuntimeError("audio stream boom")
        )
        with self.assertRaises(RuntimeError):
            provider.receive_audio_chunk(sid)


class AudioTransportTests(unittest.TestCase):
    def test_encode_outgoing_produces_blob_dict(self):
        blob = _AudioTransport().encode_outgoing(b"\x01\x02")
        self.assertEqual(blob, {"data": b"\x01\x02", "mime_type": "audio/pcm;rate=16000"})

    def test_extract_incoming_returns_bytes(self):
        self.assertEqual(
            _AudioTransport().extract_incoming(_audio_msg(b"\x09\x08")), b"\x09\x08"
        )

    def test_extract_incoming_ignores_empty_and_none(self):
        transport = _AudioTransport()
        self.assertIsNone(transport.extract_incoming(_audio_msg(b"")))
        self.assertIsNone(transport.extract_incoming(_audio_msg(None)))

    def test_is_supported_format(self):
        transport = _AudioTransport()
        self.assertTrue(transport.is_supported_format(b"\x01\x02"))
        self.assertFalse(transport.is_supported_format(b"\x01\x02\x03"))

    def test_extract_incoming_returns_plain_bytes_not_sdk_object(self):
        # bytearray in the SDK message -> plain bytes out (never the SDK object).
        out = _AudioTransport().extract_incoming(_audio_msg(bytearray(b"\x07")))
        self.assertIs(type(out), bytes)

    def test_is_a_private_module_member(self):
        self.assertTrue(_AudioTransport.__name__.startswith("_"))


# =====================================================================
# Sprint 12.11 — Visual input messaging
# =====================================================================
_IMG = b"\x89PNG\r\n\x1a\n" + b"\x00\x10\x20\x30" * 8  # non-empty image bytes


def _make_visual(source=VisualSource.IMAGE, mime="image/png", payload=None, metadata=None):
    return VisualInput(
        payload=_IMG if payload is None else payload,
        mime_type=mime,
        source=source,
        metadata={} if metadata is None else metadata,
    )


class VisualSourceEnumTests(unittest.TestCase):
    def test_all_members(self):
        self.assertEqual(
            {m.name for m in VisualSource},
            {
                "IMAGE",
                "SCREENSHOT",
                "CAMERA_FRAME",
                "DOCUMENT_PAGE",
                "WHITEBOARD",
                "DIAGRAM",
                "OTHER",
            },
        )

    def test_values(self):
        self.assertEqual(VisualSource.IMAGE.value, "image")
        self.assertEqual(VisualSource.CAMERA_FRAME.value, "camera_frame")
        self.assertEqual(VisualSource.DOCUMENT_PAGE.value, "document_page")


class VisualInputDtoTests(unittest.TestCase):
    def test_is_frozen(self):
        visual = _make_visual()
        with self.assertRaises(ValidationError):
            visual.mime_type = "image/jpeg"

    def test_metadata_defaults_empty(self):
        self.assertEqual(_make_visual().metadata, {})

    def test_holds_fields(self):
        visual = _make_visual(
            source=VisualSource.DIAGRAM, mime="image/webp", metadata={"k": "v"}
        )
        self.assertEqual(visual.mime_type, "image/webp")
        self.assertIs(visual.source, VisualSource.DIAGRAM)
        self.assertEqual(visual.metadata, {"k": "v"})

    def test_payload_must_be_bytes(self):
        with self.assertRaises(ValidationError):
            VisualInput(payload=123, mime_type="image/png", source=VisualSource.IMAGE)

    def test_source_must_be_valid(self):
        with self.assertRaises(ValidationError):
            VisualInput(payload=_IMG, mime_type="image/png", source="bogus")

    def test_accepts_source_value_string(self):
        visual = VisualInput(
            payload=_IMG, mime_type="image/png", source="screenshot"
        )
        self.assertIs(visual.source, VisualSource.SCREENSHOT)


class VisualTransportTests(unittest.TestCase):
    def test_supported_and_unsupported_mimes(self):
        transport = _VisualTransport()
        for mime in ("image/jpeg", "image/png", "image/webp"):
            self.assertTrue(transport.is_supported_mime(mime))
        for mime in ("image/gif", "application/pdf", "text/plain", None):
            self.assertFalse(transport.is_supported_mime(mime))

    def test_encode_parts_image_only(self):
        parts = _VisualTransport().encode_parts(_make_visual())
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["inline_data"]["mime_type"], "image/png")
        self.assertEqual(parts[0]["inline_data"]["data"], _IMG)

    def test_encode_parts_with_prompt(self):
        parts = _VisualTransport().encode_parts(
            _make_visual(metadata={"prompt": "Describe this"})
        )
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[1]["text"], "Describe this")

    def test_encode_parts_ignores_blank_prompt(self):
        parts = _VisualTransport().encode_parts(
            _make_visual(metadata={"prompt": "   "})
        )
        self.assertEqual(len(parts), 1)

    def test_decode_response_text(self):
        transport = _VisualTransport()
        self.assertEqual(transport.decode_response_text(_text_msg("hi")), "hi")
        self.assertEqual(
            transport.decode_response_text(_transcript_msg("yo")), "yo"
        )
        self.assertIsNone(transport.decode_response_text(_audio_msg(b"\x00")))

    def test_is_a_private_module_member(self):
        self.assertTrue(_VisualTransport.__name__.startswith("_"))


class SendVisualTests(unittest.TestCase):
    def test_send_returns_success_and_session_stays_active(self):
        provider, sdk, sid, _ = _messaging_provider()
        result = provider.send_visual_input(sid, _make_visual())
        self.assertTrue(result.success)
        self.assertEqual(result.session.state, SessionState.ACTIVE)

    def test_exactly_one_send_with_image_part(self):
        provider, sdk, sid, _ = _messaging_provider()
        provider.send_visual_input(sid, _make_visual(mime="image/jpeg"))
        self.assertEqual(sdk.send_count, 1)
        parts = sdk.sent[0]["turns"]["parts"]
        self.assertEqual(parts[0]["inline_data"]["mime_type"], "image/jpeg")
        self.assertEqual(parts[0]["inline_data"]["data"], _IMG)

    def test_prompt_from_metadata_added_as_text_part(self):
        provider, sdk, sid, _ = _messaging_provider()
        provider.send_visual_input(
            sid, _make_visual(metadata={"prompt": "What is this?"})
        )
        parts = sdk.sent[0]["turns"]["parts"]
        self.assertEqual(parts[-1]["text"], "What is this?")

    def test_every_visual_source_sends_successfully(self):
        for source in VisualSource:
            provider, sdk, sid, _ = _messaging_provider()
            result = provider.send_visual_input(sid, _make_visual(source=source))
            self.assertTrue(result.success, source)
            self.assertEqual(sdk.send_count, 1)

    def test_all_supported_mimes_accepted(self):
        for mime in ("image/jpeg", "image/png", "image/webp"):
            provider, sdk, sid, _ = _messaging_provider()
            self.assertTrue(
                provider.send_visual_input(sid, _make_visual(mime=mime)).success
            )

    def test_unsupported_mime_rejected(self):
        provider, sdk, sid, _ = _messaging_provider()
        with self.assertRaises(ValueError):
            provider.send_visual_input(sid, _make_visual(mime="image/gif"))
        self.assertEqual(sdk.send_count, 0)

    def test_empty_payload_rejected(self):
        provider, sdk, sid, _ = _messaging_provider()
        with self.assertRaises(ValueError):
            provider.send_visual_input(sid, _make_visual(payload=b""))
        self.assertEqual(sdk.send_count, 0)

    def test_non_visualinput_rejected(self):
        provider, sdk, sid, _ = _messaging_provider()
        with self.assertRaises(TypeError):
            provider.send_visual_input(sid, "not-a-visual-input")
        self.assertEqual(sdk.send_count, 0)

    def test_send_missing_session_raises(self):
        provider, _, _, _ = _messaging_provider()
        with self.assertRaises(ValueError):
            provider.send_visual_input(uuid.uuid4(), _make_visual())

    def test_send_inactive_session_raises(self):
        provider, sdk, sid, _ = _messaging_provider()
        provider.pause_session(sid)
        with self.assertRaises(ValueError):
            provider.send_visual_input(sid, _make_visual())
        self.assertEqual(sdk.send_count, 0)

    def test_metadata_preserved(self):
        provider, sdk, sid, _ = _messaging_provider()
        visual = _make_visual(metadata={"prompt": "hi", "trace": "abc"})
        provider.send_visual_input(sid, visual)
        self.assertEqual(visual.metadata, {"prompt": "hi", "trace": "abc"})

    def test_send_exception_propagates(self):
        provider, sdk, sid, _ = _messaging_provider(
            send_error=RuntimeError("sdk visual boom")
        )
        with self.assertRaises(RuntimeError):
            provider.send_visual_input(sid, _make_visual())


class ReceiveVisualTests(unittest.TestCase):
    def test_aggregates_explanation_text(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_text_msg("A red "), _text_msg("square.")]
        )
        result = provider.receive_visual_response(sid)
        self.assertEqual(result, "A red square.")
        self.assertIsInstance(result, str)

    def test_aggregates_from_transcription(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_transcript_msg("A red "), _transcript_msg("square.")]
        )
        self.assertEqual(provider.receive_visual_response(sid), "A red square.")

    def test_exactly_one_receive(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_text_msg("x")]
        )
        provider.receive_visual_response(sid)
        self.assertEqual(sdk.receive_count, 1)

    def test_ignores_empty_chunks(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_text_msg("A"), _text_msg(""), _text_msg(None), _text_msg("B")]
        )
        self.assertEqual(provider.receive_visual_response(sid), "AB")

    def test_preserves_order(self):
        provider, sdk, sid, _ = _messaging_provider(
            messages=[_text_msg("1"), _text_msg("2"), _text_msg("3")]
        )
        self.assertEqual(provider.receive_visual_response(sid), "123")

    def test_receive_missing_session_raises(self):
        provider, _, _, _ = _messaging_provider()
        with self.assertRaises(ValueError):
            provider.receive_visual_response(uuid.uuid4())

    def test_receive_inactive_session_raises(self):
        provider, sdk, sid, _ = _messaging_provider(messages=[_text_msg("x")])
        provider.pause_session(sid)
        with self.assertRaises(ValueError):
            provider.receive_visual_response(sid)
        self.assertEqual(sdk.receive_count, 0)

    def test_receive_exception_propagates(self):
        provider, sdk, sid, _ = _messaging_provider(
            receive_error=RuntimeError("visual stream boom")
        )
        with self.assertRaises(RuntimeError):
            provider.receive_visual_response(sid)


if __name__ == "__main__":
    unittest.main()
