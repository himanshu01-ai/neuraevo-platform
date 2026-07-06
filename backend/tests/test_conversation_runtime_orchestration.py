"""Unit tests for the Sprint 12.14 Conversation Runtime (orchestration only).

Everything below the runtime is faked — an in-memory session provider stands in
for the Gemini Live provider (implementing BOTH the frozen Session SPI and the
Sprint 12.9–12.13 live messaging surface), and the memory services are mocks —
so no network, SDK, database, or API key is touched. The tests verify:

* the RuntimeRequestType vocabulary and the RuntimeRequest/RuntimeResponse DTO
  contracts (validation, defaults, immutability, provider independence),
* the rule-based ``_RequestClassifier`` (every type, UNKNOWN for empty and for
  ambiguous requests, determinism — no AI),
* the ``_ResponseAssembler`` (one aggregated provider-independent response),
* runtime routing for text / audio / visual / document / action (the right
  port methods, called exactly once, with the right arguments),
* session coordination (created once, reused for every later request, never
  duplicated, stale sessions replaced, per-conversation isolation),
* memory coordination (context requested via the reused retrieval service,
  text turns stored via the reused persistence service, both optional),
* an import audit proving the runtime owns no provider/tool/business logic
  (no SDK, planner, registry, permission, tool-execution, HTTP, or repository
  import) and no duplicated architecture,
* the composition-root wiring, and
* performance measurements (routing latency, session reuse, memory overhead).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_conversation_runtime_orchestration
"""

import ast
import inspect
import time
import tracemalloc
import unittest
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

from pydantic import ValidationError

import dataclasses

from app.services.runtime import (
    ConversationRuntime,
    LiveMessagingPort,
    RuntimeContext,
    RuntimeRequest,
    RuntimeRequestType,
    RuntimeResponse,
)
from app.services.runtime.conversation_runtime import (
    _RequestClassifier,
    _ResponseAssembler,
)
from app.services.session import (
    ConversationSession,
    SessionProvider,
    SessionResult,
    SessionService,
    SessionState,
)
from app.services.session.providers.gemini_live_provider import (
    ActionRequest,
    ActionResult,
    DocumentInput,
    DocumentType,
    VisualInput,
    VisualSource,
)


# =====================================================================
# Fakes (test-local; no network, no SDK)
# =====================================================================
class _FakeLiveProvider(SessionProvider):
    """In-memory stand-in for the Gemini Live provider.

    Implements the frozen Session SPI plus the Sprint 12.9–12.13 messaging
    surface, mirroring production wiring where ONE provider instance serves
    both the SessionService and the LiveMessagingPort. Records every call.
    """

    name = "fake_live"

    def __init__(self):
        self._sessions: Dict[uuid.UUID, ConversationSession] = {}
        self.calls = []
        self.create_count = 0
        self.text_reply = "fake text reply"
        self.audio_reply = b"\x01\x02\x03\x04"
        self.visual_reply = "fake visual reply"
        self.document_reply = "fake document reply"
        self.action_reply = ActionResult(success=True, result="fake action ok")
        self.fail_create = False

    # -- Session SPI -------------------------------------------------
    def create_session(self, conversation_id, employee_id, metadata=None):
        self.calls.append(("create_session", conversation_id, employee_id, metadata))
        self.create_count += 1
        if self.fail_create:
            return SessionResult(success=False, session=None)
        now = datetime.now(timezone.utc)
        session = ConversationSession(
            session_id=uuid.uuid4(),
            conversation_id=conversation_id,
            employee_id=employee_id,
            state=SessionState.ACTIVE,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )
        self._sessions[session.session_id] = session
        return SessionResult(success=True, session=session)

    def pause_session(self, session_id):
        return self._transition(session_id, SessionState.PAUSED)

    def resume_session(self, session_id):
        return self._transition(session_id, SessionState.ACTIVE)

    def close_session(self, session_id):
        self.calls.append(("close_session", session_id))
        return self._transition(session_id, SessionState.CLOSED)

    def get_session(self, session_id):
        self.calls.append(("get_session", session_id))
        session = self._sessions.get(session_id)
        if session is None:
            return SessionResult(success=False, session=None)
        return SessionResult(success=True, session=session)

    def health_check(self):
        return True

    def _transition(self, session_id, state):
        session = self._sessions.get(session_id)
        if session is None:
            return SessionResult(success=False, session=None)
        updated = session.model_copy(update={"state": state})
        self._sessions[session_id] = updated
        return SessionResult(success=True, session=updated)

    # -- Live messaging surface (Sprint 12.9–12.13) ------------------
    def send_message(self, session_id, message):
        self.calls.append(("send_message", session_id, message))
        return SessionResult(success=True, session=self._sessions[session_id])

    def receive_response(self, session_id):
        self.calls.append(("receive_response", session_id))
        return self.text_reply

    def send_audio_chunk(self, session_id, pcm_chunk):
        self.calls.append(("send_audio_chunk", session_id, pcm_chunk))
        return SessionResult(success=True, session=self._sessions[session_id])

    def receive_audio_chunk(self, session_id):
        self.calls.append(("receive_audio_chunk", session_id))
        return self.audio_reply

    def send_visual_input(self, session_id, visual_input):
        self.calls.append(("send_visual_input", session_id, visual_input))
        return SessionResult(success=True, session=self._sessions[session_id])

    def receive_visual_response(self, session_id):
        self.calls.append(("receive_visual_response", session_id))
        return self.visual_reply

    def send_document(self, session_id, document_input):
        self.calls.append(("send_document", session_id, document_input))
        return SessionResult(success=True, session=self._sessions[session_id])

    def receive_document_response(self, session_id):
        self.calls.append(("receive_document_response", session_id))
        return self.document_reply

    def execute_action(self, session_id, action_request):
        self.calls.append(("execute_action", session_id, action_request))
        return self.action_reply

    # -- test helpers -------------------------------------------------
    def messaging_calls(self):
        lifecycle = {"create_session", "get_session", "close_session"}
        return [c for c in self.calls if c[0] not in lifecycle]


def _make_runtime(provider=None, memory_retrieval=None, memory_persistence=None):
    provider = provider or _FakeLiveProvider()
    runtime = ConversationRuntime(
        session_service=SessionService(provider),
        live_messaging=provider,
        memory_retrieval=memory_retrieval,
        memory_persistence=memory_persistence,
    )
    return runtime, provider


_CONVERSATION_ID = uuid.uuid4()
_EMPLOYEE_ID = uuid.uuid4()


def _request(**payload):
    return RuntimeRequest(
        conversation_id=_CONVERSATION_ID,
        employee_id=_EMPLOYEE_ID,
        **payload,
    )


def _visual():
    return VisualInput(
        payload=b"\x89PNG fake", mime_type="image/png", source=VisualSource.IMAGE
    )


def _document():
    return DocumentInput(
        payload=b"%PDF fake",
        mime_type="application/pdf",
        document_type=DocumentType.PDF,
    )


def _action():
    return ActionRequest(tool_name="get_current_time", arguments={})


# =====================================================================
# RuntimeRequestType (enum vocabulary)
# =====================================================================
class RuntimeRequestTypeTests(unittest.TestCase):
    def test_is_str_enum(self):
        self.assertTrue(issubclass(RuntimeRequestType, str))

    def test_exact_member_set(self):
        self.assertEqual(
            {m.name for m in RuntimeRequestType},
            {"TEXT", "AUDIO", "VISUAL", "DOCUMENT", "ACTION", "UNKNOWN"},
        )

    def test_member_values(self):
        self.assertEqual(RuntimeRequestType.TEXT.value, "text")
        self.assertEqual(RuntimeRequestType.AUDIO.value, "audio")
        self.assertEqual(RuntimeRequestType.VISUAL.value, "visual")
        self.assertEqual(RuntimeRequestType.DOCUMENT.value, "document")
        self.assertEqual(RuntimeRequestType.ACTION.value, "action")
        self.assertEqual(RuntimeRequestType.UNKNOWN.value, "unknown")


# =====================================================================
# Models: RuntimeRequest / RuntimeResponse
# =====================================================================
class RuntimeRequestModelTests(unittest.TestCase):
    def test_requires_identities(self):
        with self.assertRaises(ValidationError):
            RuntimeRequest(text="hello")

    def test_payloads_default_none_and_metadata_empty(self):
        request = _request()
        self.assertIsNone(request.text)
        self.assertIsNone(request.audio)
        self.assertIsNone(request.visual)
        self.assertIsNone(request.document)
        self.assertIsNone(request.action)
        self.assertEqual(request.metadata, {})

    def test_rejects_invalid_uuid(self):
        with self.assertRaises(ValidationError):
            RuntimeRequest(
                conversation_id="not-a-uuid", employee_id=_EMPLOYEE_ID
            )


class RuntimeResponseModelTests(unittest.TestCase):
    def _response(self, **overrides):
        payload = {
            "request_type": RuntimeRequestType.TEXT,
            "session_id": uuid.uuid4(),
            "conversation_id": _CONVERSATION_ID,
            "employee_id": _EMPLOYEE_ID,
        }
        payload.update(overrides)
        return RuntimeResponse(**payload)

    def test_is_immutable(self):
        response = self._response()
        with self.assertRaises(ValidationError):
            response.text = "mutated"

    def test_outputs_default_none_and_metadata_empty(self):
        response = self._response()
        self.assertIsNone(response.text)
        self.assertIsNone(response.audio)
        self.assertIsNone(response.action_result)
        self.assertEqual(response.metadata, {})

    def test_carries_only_provider_independent_types(self):
        # Every field is a plain value or a provider-independent DTO — the
        # response type never references a session handle, provider class, or
        # SDK object.
        fields = RuntimeResponse.model_fields
        self.assertEqual(
            set(fields),
            {
                "request_type",
                "session_id",
                "conversation_id",
                "employee_id",
                "text",
                "audio",
                "action_result",
                "metadata",
            },
        )


# =====================================================================
# _RequestClassifier (rule-based, deterministic, no AI)
# =====================================================================
class RequestClassifierTests(unittest.TestCase):
    def setUp(self):
        self.classifier = _RequestClassifier()

    def test_text(self):
        self.assertIs(
            self.classifier.classify(_request(text="hello")),
            RuntimeRequestType.TEXT,
        )

    def test_audio(self):
        self.assertIs(
            self.classifier.classify(_request(audio=b"\x00\x01")),
            RuntimeRequestType.AUDIO,
        )

    def test_visual(self):
        self.assertIs(
            self.classifier.classify(_request(visual=_visual())),
            RuntimeRequestType.VISUAL,
        )

    def test_document(self):
        self.assertIs(
            self.classifier.classify(_request(document=_document())),
            RuntimeRequestType.DOCUMENT,
        )

    def test_action(self):
        self.assertIs(
            self.classifier.classify(_request(action=_action())),
            RuntimeRequestType.ACTION,
        )

    def test_empty_request_is_unknown(self):
        self.assertIs(
            self.classifier.classify(_request()), RuntimeRequestType.UNKNOWN
        )

    def test_whitespace_text_is_unknown(self):
        self.assertIs(
            self.classifier.classify(_request(text="   \n\t ")),
            RuntimeRequestType.UNKNOWN,
        )

    def test_empty_audio_is_unknown(self):
        self.assertIs(
            self.classifier.classify(_request(audio=b"")),
            RuntimeRequestType.UNKNOWN,
        )

    def test_ambiguous_request_is_unknown(self):
        # More than one payload => not classifiable; the classifier never
        # guesses between modalities.
        request = _request(text="hello", audio=b"\x00\x01")
        self.assertIs(
            self.classifier.classify(request), RuntimeRequestType.UNKNOWN
        )
        request = _request(visual=_visual(), document=_document())
        self.assertIs(
            self.classifier.classify(request), RuntimeRequestType.UNKNOWN
        )

    def test_exactly_one_type_for_every_single_payload(self):
        payloads = {
            RuntimeRequestType.TEXT: {"text": "hi"},
            RuntimeRequestType.AUDIO: {"audio": b"\x00\x01"},
            RuntimeRequestType.VISUAL: {"visual": _visual()},
            RuntimeRequestType.DOCUMENT: {"document": _document()},
            RuntimeRequestType.ACTION: {"action": _action()},
        }
        for expected, payload in payloads.items():
            self.assertIs(self.classifier.classify(_request(**payload)), expected)

    def test_deterministic(self):
        request = _request(text="same input")
        results = {self.classifier.classify(request) for _ in range(50)}
        self.assertEqual(results, {RuntimeRequestType.TEXT})

    def test_rule_based_no_ai_collaborators(self):
        # The classifier is constructed with nothing and holds nothing — no
        # provider, model, client, or service to consult.
        self.assertNotIn("__init__", vars(_RequestClassifier))
        self.assertEqual(vars(self.classifier), {})


# =====================================================================
# _ResponseAssembler
# =====================================================================
class ResponseAssemblerTests(unittest.TestCase):
    def setUp(self):
        self.assembler = _ResponseAssembler()
        now = datetime.now(timezone.utc)
        self.session = ConversationSession(
            session_id=uuid.uuid4(),
            conversation_id=_CONVERSATION_ID,
            employee_id=_EMPLOYEE_ID,
            state=SessionState.ACTIVE,
            created_at=now,
            updated_at=now,
        )

    def _context(
        self,
        request,
        request_type,
        session_reused,
        memory_context_messages=None,
    ):
        return RuntimeContext(
            request=request,
            owner=None,
            request_type=request_type,
            session=self.session,
            session_reused=session_reused,
            memory_context_messages=memory_context_messages,
        )

    def test_assembles_text_response(self):
        response = self.assembler.assemble(
            self._context(_request(text="hi"), RuntimeRequestType.TEXT, True),
            text="reply",
        )
        self.assertIsInstance(response, RuntimeResponse)
        self.assertIs(response.request_type, RuntimeRequestType.TEXT)
        self.assertEqual(response.session_id, self.session.session_id)
        self.assertEqual(response.conversation_id, _CONVERSATION_ID)
        self.assertEqual(response.employee_id, _EMPLOYEE_ID)
        self.assertEqual(response.text, "reply")
        self.assertIsNone(response.audio)
        self.assertIsNone(response.action_result)
        self.assertEqual(response.metadata, {"session_reused": True})

    def test_assembles_audio_response(self):
        response = self.assembler.assemble(
            self._context(
                _request(audio=b"\x00\x01"), RuntimeRequestType.AUDIO, False
            ),
            audio=b"\x09\x08",
        )
        self.assertEqual(response.audio, b"\x09\x08")
        self.assertIsNone(response.text)
        self.assertEqual(response.metadata, {"session_reused": False})

    def test_assembles_action_response(self):
        result = ActionResult(success=True, result="done")
        response = self.assembler.assemble(
            self._context(
                _request(action=_action()), RuntimeRequestType.ACTION, True
            ),
            action_result=result,
        )
        self.assertEqual(response.action_result, result)

    def test_memory_context_included_only_when_present(self):
        without = self.assembler.assemble(
            self._context(_request(text="hi"), RuntimeRequestType.TEXT, False)
        )
        self.assertNotIn("memory_context_messages", without.metadata)
        with_memory = self.assembler.assemble(
            self._context(
                _request(text="hi"),
                RuntimeRequestType.TEXT,
                False,
                memory_context_messages=7,
            )
        )
        self.assertEqual(with_memory.metadata["memory_context_messages"], 7)

    def test_result_is_immutable(self):
        response = self.assembler.assemble(
            self._context(_request(text="hi"), RuntimeRequestType.TEXT, False)
        )
        with self.assertRaises(ValidationError):
            response.text = "mutated"

    def test_never_exposes_session_or_provider_objects(self):
        response = self.assembler.assemble(
            self._context(_request(text="hi"), RuntimeRequestType.TEXT, False),
            text="reply",
        )
        for value in response.__dict__.values():
            self.assertNotIsInstance(value, ConversationSession)
            self.assertNotIsInstance(value, SessionResult)


# =====================================================================
# RuntimeContext (immutable per-turn coordination value object)
# =====================================================================
class RuntimeContextTests(unittest.TestCase):
    def _context(self, **overrides):
        now = datetime.now(timezone.utc)
        session = ConversationSession(
            session_id=uuid.uuid4(),
            conversation_id=_CONVERSATION_ID,
            employee_id=_EMPLOYEE_ID,
            state=SessionState.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        payload = {
            "request": _request(text="hi"),
            "owner": None,
            "request_type": RuntimeRequestType.TEXT,
            "session": session,
            "session_reused": True,
        }
        payload.update(overrides)
        return RuntimeContext(**payload)

    def test_is_frozen(self):
        context = self._context()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            context.session_reused = False

    def test_memory_context_messages_defaults_none(self):
        self.assertIsNone(self._context().memory_context_messages)

    def test_holds_the_turn_facts(self):
        context = self._context(memory_context_messages=4)
        self.assertIs(context.request_type, RuntimeRequestType.TEXT)
        self.assertTrue(context.session_reused)
        self.assertEqual(context.memory_context_messages, 4)


# =====================================================================
# Runtime routing — text / audio / visual / document / action
# =====================================================================
class RuntimeTextRoutingTests(unittest.TestCase):
    def test_routes_text_and_returns_reply(self):
        runtime, provider = _make_runtime()
        response = runtime.execute(_request(text="Hello."))
        names = [c[0] for c in provider.messaging_calls()]
        self.assertEqual(names, ["send_message", "receive_response"])
        self.assertEqual(provider.messaging_calls()[0][2], "Hello.")
        self.assertIs(response.request_type, RuntimeRequestType.TEXT)
        self.assertEqual(response.text, "fake text reply")
        self.assertIsNone(response.audio)
        self.assertIsNone(response.action_result)


class RuntimeAudioRoutingTests(unittest.TestCase):
    def test_routes_audio_and_returns_bytes(self):
        runtime, provider = _make_runtime()
        response = runtime.execute(_request(audio=b"\x00\x01\x02\x03"))
        names = [c[0] for c in provider.messaging_calls()]
        self.assertEqual(names, ["send_audio_chunk", "receive_audio_chunk"])
        self.assertEqual(provider.messaging_calls()[0][2], b"\x00\x01\x02\x03")
        self.assertIs(response.request_type, RuntimeRequestType.AUDIO)
        self.assertEqual(response.audio, b"\x01\x02\x03\x04")
        self.assertIsNone(response.text)


class RuntimeVisualRoutingTests(unittest.TestCase):
    def test_routes_visual_and_returns_text(self):
        runtime, provider = _make_runtime()
        visual = _visual()
        response = runtime.execute(_request(visual=visual))
        names = [c[0] for c in provider.messaging_calls()]
        self.assertEqual(names, ["send_visual_input", "receive_visual_response"])
        self.assertIs(provider.messaging_calls()[0][2], visual)
        self.assertIs(response.request_type, RuntimeRequestType.VISUAL)
        self.assertEqual(response.text, "fake visual reply")


class RuntimeDocumentRoutingTests(unittest.TestCase):
    def test_routes_document_and_returns_text(self):
        runtime, provider = _make_runtime()
        document = _document()
        response = runtime.execute(_request(document=document))
        names = [c[0] for c in provider.messaging_calls()]
        self.assertEqual(names, ["send_document", "receive_document_response"])
        self.assertIs(provider.messaging_calls()[0][2], document)
        self.assertIs(response.request_type, RuntimeRequestType.DOCUMENT)
        self.assertEqual(response.text, "fake document reply")


class RuntimeActionRoutingTests(unittest.TestCase):
    def test_routes_action_through_port_only(self):
        # The runtime hands the ActionRequest to the port's execute_action —
        # the Sprint 12.13 translation layer that forwards into the Sprint 11
        # pipeline — and never plans/permissions/executes anything itself.
        runtime, provider = _make_runtime()
        action = _action()
        response = runtime.execute(_request(action=action))
        names = [c[0] for c in provider.messaging_calls()]
        self.assertEqual(names, ["execute_action"])
        self.assertIs(provider.messaging_calls()[0][2], action)
        self.assertIs(response.request_type, RuntimeRequestType.ACTION)
        self.assertEqual(response.action_result, provider.action_reply)
        self.assertIsNone(response.text)
        self.assertIsNone(response.audio)

    def test_action_failure_result_returned_unchanged(self):
        runtime, provider = _make_runtime()
        provider.action_reply = ActionResult(
            success=False, result="permission denied",
            metadata={"permission_denied": True},
        )
        response = runtime.execute(_request(action=_action()))
        self.assertEqual(response.action_result, provider.action_reply)


class RuntimeUnknownRequestTests(unittest.TestCase):
    def test_unknown_raises_before_any_side_effect(self):
        runtime, provider = _make_runtime()
        with self.assertRaises(ValueError):
            runtime.execute(_request())
        self.assertEqual(provider.calls, [])
        self.assertEqual(provider.create_count, 0)

    def test_ambiguous_raises_before_any_side_effect(self):
        runtime, provider = _make_runtime()
        with self.assertRaises(ValueError):
            runtime.execute(_request(text="hi", audio=b"\x00\x01"))
        self.assertEqual(provider.calls, [])

    def test_exceptions_from_port_propagate_unchanged(self):
        runtime, provider = _make_runtime()
        boom = RuntimeError("live failure")

        def _raise(session_id, message):
            raise boom

        provider.send_message = _raise
        with self.assertRaises(RuntimeError) as ctx:
            runtime.execute(_request(text="hi"))
        self.assertIs(ctx.exception, boom)


# =====================================================================
# Session coordination — one session, reused, never duplicated
# =====================================================================
class SessionCoordinationTests(unittest.TestCase):
    def test_first_request_creates_exactly_one_session(self):
        runtime, provider = _make_runtime()
        response = runtime.execute(_request(text="hello"))
        self.assertEqual(provider.create_count, 1)
        self.assertFalse(response.metadata["session_reused"])

    def test_all_later_requests_reuse_the_same_session(self):
        runtime, provider = _make_runtime()
        first = runtime.execute(_request(text="hello"))
        later = [
            runtime.execute(_request(audio=b"\x00\x01")),
            runtime.execute(_request(visual=_visual())),
            runtime.execute(_request(document=_document())),
            runtime.execute(_request(action=_action())),
            runtime.execute(_request(text="continue")),
        ]
        self.assertEqual(provider.create_count, 1)  # never duplicated
        for response in later:
            self.assertEqual(response.session_id, first.session_id)
            self.assertTrue(response.metadata["session_reused"])

    def test_session_create_metadata_forwarded_verbatim(self):
        runtime, provider = _make_runtime()
        runtime.execute(
            _request(text="hello", metadata={"model": "some-live-model"})
        )
        create = [c for c in provider.calls if c[0] == "create_session"][0]
        self.assertEqual(create[3], {"model": "some-live-model"})

    def test_stale_session_replaced_by_exactly_one_new_session(self):
        runtime, provider = _make_runtime()
        first = runtime.execute(_request(text="hello"))
        provider.close_session(first.session_id)  # externally closed
        second = runtime.execute(_request(text="hello again"))
        self.assertEqual(provider.create_count, 2)
        self.assertNotEqual(second.session_id, first.session_id)
        self.assertFalse(second.metadata["session_reused"])

    def test_conversations_get_isolated_sessions(self):
        runtime, provider = _make_runtime()
        request_a = _request(text="hi")
        request_b = RuntimeRequest(
            conversation_id=uuid.uuid4(),
            employee_id=uuid.uuid4(),
            text="hi",
        )
        response_a = runtime.execute(request_a)
        response_b = runtime.execute(request_b)
        self.assertNotEqual(response_a.session_id, response_b.session_id)
        self.assertEqual(provider.create_count, 2)
        # And each conversation still reuses its own session afterwards.
        self.assertEqual(
            runtime.execute(request_a).session_id, response_a.session_id
        )
        self.assertEqual(
            runtime.execute(request_b).session_id, response_b.session_id
        )
        self.assertEqual(provider.create_count, 2)

    def test_failed_creation_raises_no_retries(self):
        runtime, provider = _make_runtime()
        provider.fail_create = True
        with self.assertRaises(RuntimeError):
            runtime.execute(_request(text="hello"))
        self.assertEqual(provider.create_count, 1)  # exactly one attempt

    def test_close_conversation_delegates_to_session_service(self):
        runtime, provider = _make_runtime()
        request = _request(text="hello")
        response = runtime.execute(request)
        self.assertTrue(runtime.close_conversation(request))
        closes = [c for c in provider.calls if c[0] == "close_session"]
        self.assertEqual(closes, [("close_session", response.session_id)])
        # Closed conversations get a fresh session on the next request.
        self.assertFalse(
            runtime.execute(request).metadata["session_reused"]
        )

    def test_close_conversation_without_session_is_false(self):
        runtime, _ = _make_runtime()
        self.assertFalse(runtime.close_conversation(_request(text="x")))


# =====================================================================
# Memory coordination — reused services, optional, never implemented here
# =====================================================================
class MemoryCoordinationTests(unittest.TestCase):
    def setUp(self):
        self.owner = MagicMock(name="owner")
        self.retrieval = MagicMock(name="memory_retrieval")
        self.retrieval.retrieve.return_value = ["m1", "m2", "m3"]
        self.persistence = MagicMock(name="memory_persistence")

    def test_context_requested_from_reused_retrieval_service(self):
        runtime, _ = _make_runtime(memory_retrieval=self.retrieval)
        response = runtime.execute(_request(text="hello"), owner=self.owner)
        self.retrieval.retrieve.assert_called_once_with(
            self.owner, _EMPLOYEE_ID, _CONVERSATION_ID
        )
        self.assertEqual(response.metadata["memory_context_messages"], 3)

    def test_context_skipped_without_owner(self):
        runtime, _ = _make_runtime(memory_retrieval=self.retrieval)
        response = runtime.execute(_request(text="hello"))
        self.retrieval.retrieve.assert_not_called()
        self.assertNotIn("memory_context_messages", response.metadata)

    def test_context_skipped_without_service(self):
        runtime, _ = _make_runtime()
        response = runtime.execute(_request(text="hello"), owner=self.owner)
        self.assertNotIn("memory_context_messages", response.metadata)

    def test_text_turn_stored_via_reused_persistence_service(self):
        runtime, provider = _make_runtime(memory_persistence=self.persistence)
        runtime.execute(_request(text="Hello."), owner=self.owner)
        self.persistence.persist.assert_called_once()
        args = self.persistence.persist.call_args.args
        self.assertIs(args[0], self.owner)
        self.assertEqual(args[1], _EMPLOYEE_ID)
        self.assertEqual(args[2], _CONVERSATION_ID)
        self.assertEqual(args[3], "Hello.")
        ai_response = args[4]
        self.assertEqual(ai_response.content, "fake text reply")
        self.assertEqual(ai_response.metadata.provider, provider.name)

    def test_non_text_turns_not_stored(self):
        runtime, _ = _make_runtime(memory_persistence=self.persistence)
        runtime.execute(_request(audio=b"\x00\x01"), owner=self.owner)
        runtime.execute(_request(visual=_visual()), owner=self.owner)
        runtime.execute(_request(document=_document()), owner=self.owner)
        runtime.execute(_request(action=_action()), owner=self.owner)
        self.persistence.persist.assert_not_called()

    def test_storage_skipped_without_owner(self):
        runtime, _ = _make_runtime(memory_persistence=self.persistence)
        runtime.execute(_request(text="hello"))
        self.persistence.persist.assert_not_called()

    def test_empty_reply_not_stored(self):
        runtime, provider = _make_runtime(memory_persistence=self.persistence)
        provider.text_reply = "   "
        runtime.execute(_request(text="hello"), owner=self.owner)
        self.persistence.persist.assert_not_called()

    def test_runtime_implements_no_memory(self):
        # The runtime exposes exactly the injected services and calls them —
        # it holds no repository, session (DB), or embedding machinery.
        runtime, _ = _make_runtime(
            memory_retrieval=self.retrieval,
            memory_persistence=self.persistence,
        )
        self.assertIs(runtime.memory_retrieval, self.retrieval)
        self.assertIs(runtime.memory_persistence, self.persistence)


# =====================================================================
# Import / boundary audit — runtime only orchestrates
# =====================================================================
def _imports_of(module_name):
    import importlib

    module = importlib.import_module(module_name)
    tree = ast.parse(inspect.getsource(module))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return module, tree, imported


class RuntimeImportAuditTests(unittest.TestCase):
    _FORBIDDEN_PREFIXES = (
        "google",            # no SDK import — ever
        "genai",
        "anthropic",
        "openai",
        "fastapi",           # no HTTP concerns
        "sqlalchemy",        # no direct persistence
        "requests",
        "httpx",
        "app.repositories",  # never bypass the service layer
        "app.api",
        "app.services.planner",      # action flow goes through the port only
        "app.services.tools",
        "app.services.permissions",
        "app.services.multimodal_ai",
        "app.services.orchestrator",
        "app.services.prompt",
        "app.services.providers",
        "app.services.embeddings",
        "app.services.vector_store",
    )

    def _audit(self, module_name):
        _, _, imported = _imports_of(module_name)
        for name in imported:
            for forbidden in self._FORBIDDEN_PREFIXES:
                self.assertFalse(
                    name == forbidden or name.startswith(forbidden + "."),
                    f"{module_name} imports forbidden module {name}",
                )

    def test_runtime_module_imports_are_clean(self):
        self._audit("app.services.runtime.conversation_runtime")

    def test_models_module_imports_are_clean(self):
        self._audit("app.services.runtime.models")

    def test_provider_module_used_only_for_frozen_dtos(self):
        # The only names taken from the Gemini Live module are the
        # provider-independent payload DTOs defined by Sprints 12.11–12.13 —
        # never the provider class, transports, bridge, or handle.
        allowed = {"ActionRequest", "ActionResult", "DocumentInput", "VisualInput"}
        for module_name in (
            "app.services.runtime.conversation_runtime",
            "app.services.runtime.models",
        ):
            _, tree, _ = _imports_of(module_name)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    == "app.services.session.providers.gemini_live_provider"
                ):
                    names = {alias.name for alias in node.names}
                    self.assertTrue(
                        names <= allowed,
                        f"{module_name} imports non-DTO names {names - allowed}",
                    )

    def test_runtime_never_calls_execution_stages_directly(self):
        # No duplicated execution architecture: the runtime source never
        # invokes planner/registry/permission/tool-execution methods — actions
        # cross only the port's execute_action seam.
        source = inspect.getsource(
            __import__(
                "app.services.runtime.conversation_runtime",
                fromlist=["conversation_runtime"],
            )
        )
        for marker in (
            "create_plan",
            "get_tool",
            "check_permission",
            "ToolExecutionRequest",
            "PermissionRequest",
        ):
            self.assertNotIn(marker, source)

    def test_runtime_holds_only_injected_collaborators(self):
        runtime, provider = _make_runtime()
        self.assertEqual(
            set(vars(runtime)),
            {
                "session_service",
                "live_messaging",
                "memory_retrieval",
                "memory_persistence",
                "_classifier",
                "_assembler",
                "_active_sessions",
            },
        )
        self.assertIsInstance(runtime.session_service, SessionService)
        self.assertIs(runtime.live_messaging, provider)

    def test_port_is_structural_and_provider_satisfies_it(self):
        self.assertIsInstance(_FakeLiveProvider(), LiveMessagingPort)
        from app.services.session.providers.gemini_live_provider import (
            GeminiLiveSessionProvider,
        )

        self.assertTrue(
            isinstance(
                GeminiLiveSessionProvider.__new__(GeminiLiveSessionProvider),
                LiveMessagingPort,
            )
        )


# =====================================================================
# Composition-root wiring
# =====================================================================
class CompositionRootTests(unittest.TestCase):
    def test_get_conversation_runtime_wires_one_provider_for_both_seams(self):
        from app.core.dependencies import get_conversation_runtime

        provider = _FakeLiveProvider()
        retrieval = MagicMock()
        persistence = MagicMock()
        runtime = get_conversation_runtime(provider, retrieval, persistence)
        self.assertIsInstance(runtime, ConversationRuntime)
        # The SAME provider instance serves lifecycle and messaging.
        self.assertIs(runtime.session_service.provider, provider)
        self.assertIs(runtime.live_messaging, provider)
        self.assertIs(runtime.memory_retrieval, retrieval)
        self.assertIs(runtime.memory_persistence, persistence)


# =====================================================================
# Performance — routing latency, session reuse, memory overhead
# =====================================================================
class RuntimePerformanceTests(unittest.TestCase):
    _TURNS = 300

    def test_routing_latency_and_session_reuse(self):
        runtime, provider = _make_runtime()
        runtime.execute(_request(text="warmup"))
        started = time.perf_counter()
        for _ in range(self._TURNS):
            runtime.execute(_request(text="hello"))
        elapsed = time.perf_counter() - started
        avg_ms = (elapsed / self._TURNS) * 1000
        # Orchestration overhead (classify + route + assemble over a fake
        # port) must stay far below any network cost. Generous bound to avoid
        # flakiness — no optimization is performed or implied.
        self.assertLess(avg_ms, 50.0)
        self.assertEqual(provider.create_count, 1)  # perfect session reuse
        print(
            f"\n[PERF] runtime routing latency: avg={avg_ms:.3f} ms/turn "
            f"over {self._TURNS} turns | sessions created={provider.create_count}"
        )

    def test_memory_overhead_of_runtime_state(self):
        runtime, provider = _make_runtime()
        tracemalloc.start()
        before = tracemalloc.take_snapshot()
        for _ in range(self._TURNS):
            runtime.execute(_request(text="hello"))
        after = tracemalloc.take_snapshot()
        tracemalloc.stop()
        grown = sum(s.size_diff for s in after.compare_to(before, "filename"))
        # Bookkeeping is one dict entry per conversation — repeated turns on
        # one conversation must not grow runtime state materially (< 256 KiB
        # across the whole measured allocation set, dominated by test noise).
        self.assertEqual(len(runtime._active_sessions), 1)
        self.assertLess(grown, 256 * 1024)
        print(
            f"[PERF] memory overhead across {self._TURNS} reused-session turns: "
            f"{grown / 1024:.1f} KiB tracked; active-session entries="
            f"{len(runtime._active_sessions)}"
        )


if __name__ == "__main__":
    unittest.main()
