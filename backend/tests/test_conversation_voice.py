"""Conversation + Voice integration tests (Sprint 21).

Voice is a first-class conversation *channel*, not a separate domain, so these
tests treat a spoken turn as an ordinary message tagged ``voice`` and prove text
and voice produce the same internal message model. Layers, none touching a
database or network:

* channel persistence — the schema default and the repository mapping;
* ``ConversationTurnService`` — a real turn over mocked collaborators, proving
  the human message and the reply are both persisted on the turn's channel;
* ``ConversationService`` hub methods — user-scoped resolution and ownership;
* the Conversation Hub API — status codes, error mapping, and the turn's shape.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_conversation_voice
"""

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_conversation_service,
    get_conversation_turn_service,
    get_current_user,
    get_message_service,
)
from app.main import app
from app.models.message import Message
from app.repositories.message_repository import MessageRepository
from app.schemas.message import MessageCreate, MessageResponse
from app.services.blueprint_service import BlueprintNotFoundError
from app.services.conversation_service import (
    ConversationNotFoundError,
    ConversationService,
)
from app.services.conversation_turn_service import ConversationTurnService
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
)
from app.services.providers.conversation_provider import (
    ConversationGenerationError,
    ConversationGenerationTimeoutError,
)
from app.utils.constants import MessageChannel, MessageRole


# --- Test doubles --------------------------------------------------------


class FakeSession:
    """Captures added rows and counts commits."""

    def __init__(self) -> None:
        self.added: list = []
        self.commits = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:  # pragma: no cover - no-op
        return None

    def refresh(self, obj) -> None:  # pragma: no cover - no-op
        return None

    def commit(self) -> None:
        self.commits += 1


def make_user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4())


def make_message(role=MessageRole.USER, content="hi", channel="text") -> Message:
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        role=role.value if isinstance(role, MessageRole) else role,
        content=content,
        channel=channel,
    )
    msg.created_at = datetime.now(timezone.utc)
    return msg


# --- Message channel (the message model supports multiple origins) -------


class MessageChannelTests(unittest.TestCase):
    def test_channel_defaults_to_text(self) -> None:
        create = MessageCreate(role=MessageRole.USER, content="hello")
        self.assertEqual(create.channel, MessageChannel.TEXT)

    def test_voice_channel_accepted(self) -> None:
        create = MessageCreate(
            role=MessageRole.USER, content="hello", channel=MessageChannel.VOICE
        )
        self.assertEqual(create.channel, MessageChannel.VOICE)

    def test_repository_persists_channel(self) -> None:
        session = FakeSession()
        repo = MessageRepository(session)
        repo.create_message(
            uuid.uuid4(),
            MessageCreate(
                role=MessageRole.USER, content="spoken", channel=MessageChannel.VOICE
            ),
        )
        # The row the repository built carries the voice channel — text and voice
        # land in the same table, distinguished only by this tag.
        self.assertEqual(session.added[0].channel, "voice")

    def test_response_exposes_channel(self) -> None:
        message = make_message(channel="voice")
        body = MessageResponse.model_validate(message)
        self.assertEqual(body.channel, MessageChannel.VOICE)


# --- Turn service (text and voice run the same pipeline) -----------------


class ConversationTurnServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = make_user()
        self.employee_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()

        generation = MagicMock()
        self.service = ConversationTurnService(FakeSession(), generation)
        self.service.conversations = MagicMock()
        self.service.messages = MagicMock()
        self.service.conversations.get_for_user.return_value = SimpleNamespace(
            id=self.conversation_id, employee_id=self.employee_id
        )
        self.service.messages.create_message.return_value = make_message(
            MessageRole.USER, "spoken", "voice"
        )
        generation.generate_reply.return_value = make_message(
            MessageRole.ASSISTANT, "reply", "voice"
        )

    def test_voice_turn_persists_both_on_voice_channel(self) -> None:
        user_msg, assistant_msg = self.service.run_turn(
            self.owner,
            self.conversation_id,
            "read me the report",
            channel=MessageChannel.VOICE,
        )
        self.assertEqual(user_msg.channel, "voice")
        self.assertEqual(assistant_msg.channel, "voice")

        # The human message is created on the turn's channel …
        created = self.service.messages.create_message.call_args
        payload: MessageCreate = created.args[3]
        self.assertEqual(payload.role, MessageRole.USER)
        self.assertEqual(payload.channel, MessageChannel.VOICE)

        # … and the reply is generated on the same channel, through the reused
        # (memory-and-blueprint-grounded) generation service.
        gen_kwargs = self.service.generation.generate_reply.call_args.kwargs
        self.assertEqual(gen_kwargs["channel"], MessageChannel.VOICE)

    def test_text_turn_defaults_to_text_channel(self) -> None:
        self.service.messages.create_message.return_value = make_message(
            MessageRole.USER, "typed", "text"
        )
        self.service.generation.generate_reply.return_value = make_message(
            MessageRole.ASSISTANT, "reply", "text"
        )
        self.service.run_turn(self.owner, self.conversation_id, "hello")
        payload = self.service.messages.create_message.call_args.args[3]
        self.assertEqual(payload.channel, MessageChannel.TEXT)

    def test_unknown_conversation_propagates(self) -> None:
        self.service.conversations.get_for_user.side_effect = (
            ConversationNotFoundError("nope")
        )
        with self.assertRaises(ConversationNotFoundError):
            self.service.run_turn(self.owner, self.conversation_id, "hi")
        # Nothing was created — the turn never started.
        self.service.messages.create_message.assert_not_called()


# --- Conversation hub service (user-scoped ownership) --------------------


class ConversationServiceHubTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = make_user()
        self.service = ConversationService(FakeSession())
        self.service.conversations = MagicMock()
        self.service.employees = MagicMock()

    def _conversation(self):
        return SimpleNamespace(id=uuid.uuid4(), employee_id=uuid.uuid4())

    def test_get_for_user_returns_owned_conversation(self) -> None:
        conv = self._conversation()
        self.service.conversations.get.return_value = conv
        self.service.employees.get_employee.return_value = SimpleNamespace()
        self.assertIs(self.service.get_for_user(self.owner, conv.id), conv)

    def test_get_for_user_missing_is_not_found(self) -> None:
        self.service.conversations.get.return_value = None
        with self.assertRaises(ConversationNotFoundError):
            self.service.get_for_user(self.owner, uuid.uuid4())

    def test_get_for_user_foreign_reads_as_not_found(self) -> None:
        # A conversation whose employee belongs to someone else must not leak as
        # 403 — it reads exactly like one that does not exist.
        conv = self._conversation()
        self.service.conversations.get.return_value = conv
        self.service.employees.get_employee.side_effect = EmployeeAccessDeniedError(
            "nope"
        )
        with self.assertRaises(ConversationNotFoundError):
            self.service.get_for_user(self.owner, conv.id)

    def test_get_for_user_foreign_employee_missing_is_not_found(self) -> None:
        conv = self._conversation()
        self.service.conversations.get.return_value = conv
        self.service.employees.get_employee.side_effect = EmployeeNotFoundError("x")
        with self.assertRaises(ConversationNotFoundError):
            self.service.get_for_user(self.owner, conv.id)

    def test_list_for_user_delegates_to_repo(self) -> None:
        rows = [(self._conversation(), "Atlas", 3, "last line")]
        self.service.conversations.list_summaries_for_user.return_value = rows
        self.assertEqual(self.service.list_for_user(self.owner), rows)
        self.service.conversations.list_summaries_for_user.assert_called_once_with(
            self.owner.id
        )


# --- Conversation Hub API ------------------------------------------------


class ConversationHubAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.user = make_user()
        self.conv_service = MagicMock()
        self.turn_service = MagicMock()
        self.message_service = MagicMock()
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_conversation_service] = lambda: self.conv_service
        app.dependency_overrides[get_conversation_turn_service] = (
            lambda: self.turn_service
        )
        app.dependency_overrides[get_message_service] = lambda: self.message_service

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _conv_row(self):
        conv = SimpleNamespace(
            id=uuid.uuid4(),
            employee_id=uuid.uuid4(),
            title="Quarterly review",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return conv

    def test_list_conversations(self) -> None:
        conv = self._conv_row()
        self.conv_service.list_for_user.return_value = [(conv, "Atlas", 2, "hi there")]
        resp = self.client.get("/api/v1/conversations")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["employee_name"], "Atlas")
        self.assertEqual(body["items"][0]["message_count"], 2)
        self.assertEqual(body["items"][0]["last_message"], "hi there")

    def test_create_conversation(self) -> None:
        conv = self._conv_row()
        self.conv_service.create_conversation.return_value = conv
        self.conv_service.overview_of.return_value = ("Atlas", 0, None)
        resp = self.client.post(
            "/api/v1/conversations",
            json={"employee_id": str(conv.employee_id), "title": "Quarterly review"},
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["message_count"], 0)

    def test_create_foreign_employee_is_403(self) -> None:
        self.conv_service.create_conversation.side_effect = EmployeeAccessDeniedError(
            "x"
        )
        resp = self.client.post(
            "/api/v1/conversations",
            json={"employee_id": str(uuid.uuid4()), "title": "Nope"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_get_missing_conversation_is_404(self) -> None:
        self.conv_service.get_for_user.side_effect = ConversationNotFoundError("x")
        resp = self.client.get(f"/api/v1/conversations/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["detail"], "Conversation not found.")

    def test_delete_conversation_204(self) -> None:
        self.conv_service.delete_for_user.return_value = None
        resp = self.client.delete(f"/api/v1/conversations/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 204)

    def test_list_messages_carries_channel(self) -> None:
        self.conv_service.get_for_user.return_value = self._conv_row()
        self.message_service.list_messages.return_value = [
            make_message(MessageRole.USER, "spoken", "voice"),
            make_message(MessageRole.ASSISTANT, "reply", "voice"),
        ]
        resp = self.client.get(f"/api/v1/conversations/{uuid.uuid4()}/messages")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([m["channel"] for m in resp.json()], ["voice", "voice"])

    def test_turn_returns_both_messages_with_channel(self) -> None:
        self.turn_service.run_turn.return_value = (
            make_message(MessageRole.USER, "read the report", "voice"),
            make_message(MessageRole.ASSISTANT, "Here it is.", "voice"),
        )
        resp = self.client.post(
            f"/api/v1/conversations/{uuid.uuid4()}/turn",
            json={"content": "read the report", "channel": "voice"},
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["user_message"]["channel"], "voice")
        self.assertEqual(body["assistant_message"]["role"], "assistant")

    def test_turn_defaults_channel_to_text(self) -> None:
        self.turn_service.run_turn.return_value = (
            make_message(MessageRole.USER, "hi", "text"),
            make_message(MessageRole.ASSISTANT, "hello", "text"),
        )
        resp = self.client.post(
            f"/api/v1/conversations/{uuid.uuid4()}/turn",
            json={"content": "hi"},
        )
        self.assertEqual(resp.status_code, 201)
        # The service was called with the default text channel.
        self.assertEqual(
            self.turn_service.run_turn.call_args.kwargs["channel"], MessageChannel.TEXT
        )

    def test_turn_missing_conversation_is_404(self) -> None:
        self.turn_service.run_turn.side_effect = ConversationNotFoundError("x")
        resp = self.client.post(
            f"/api/v1/conversations/{uuid.uuid4()}/turn",
            json={"content": "hi"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_turn_no_blueprint_is_404(self) -> None:
        self.turn_service.run_turn.side_effect = BlueprintNotFoundError("x")
        resp = self.client.post(
            f"/api/v1/conversations/{uuid.uuid4()}/turn",
            json={"content": "hi"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_turn_generation_failure_is_502(self) -> None:
        self.turn_service.run_turn.side_effect = ConversationGenerationError("x")
        resp = self.client.post(
            f"/api/v1/conversations/{uuid.uuid4()}/turn",
            json={"content": "hi"},
        )
        self.assertEqual(resp.status_code, 502)

    def test_turn_timeout_is_504(self) -> None:
        self.turn_service.run_turn.side_effect = ConversationGenerationTimeoutError("x")
        resp = self.client.post(
            f"/api/v1/conversations/{uuid.uuid4()}/turn",
            json={"content": "hi"},
        )
        self.assertEqual(resp.status_code, 504)

    def test_turn_empty_content_is_422(self) -> None:
        resp = self.client.post(
            f"/api/v1/conversations/{uuid.uuid4()}/turn",
            json={"content": "   "},
        )
        self.assertEqual(resp.status_code, 422)

    def test_unauthenticated_is_401(self) -> None:
        app.dependency_overrides.pop(get_current_user, None)
        resp = self.client.get("/api/v1/conversations")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
