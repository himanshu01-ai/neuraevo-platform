"""Unit tests for the Sprint 8.1 Memory Persistence Service.

Every dependency is mocked (session + message repository), so no database is
touched. The tests verify that ``persist`` writes exactly the user then the
assistant message under the given conversation, commits atomically, propagates
repository failures (with rollback), and is a stateless, constructor-injected
service.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_memory_persistence_service
"""

import unittest
import uuid
from unittest.mock import MagicMock

from app.schemas.ai_response import AIResponse, AIResponseMetadata
from app.services.memory.memory_persistence_service import (
    MemoryPersistenceService,
)
from app.utils.constants import MessageRole

_LOGGER = "app.services.memory.memory_persistence_service"


class MemoryPersistenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = MagicMock(name="User")
        self.owner.id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.user_message = "What's on my calendar today?"
        self.ai_response = AIResponse(
            content="You have a 3pm sync.",
            metadata=AIResponseMetadata(
                provider="test-provider",
                language="en",
                employee_id=self.employee_id,
                conversation_id=self.conversation_id,
                prompt_message_count=2,
            ),
        )

        self.session = MagicMock(name="Session")
        self.messages = MagicMock(name="MessageRepository")
        self.messages.create_message.side_effect = [
            MagicMock(name="user_msg"),
            MagicMock(name="assistant_msg"),
        ]
        self.service = MemoryPersistenceService(self.session, self.messages)

    def _persist(self):
        return self.service.persist(
            self.owner,
            self.employee_id,
            self.conversation_id,
            self.user_message,
            self.ai_response,
        )

    def _create_calls(self):
        return self.messages.create_message.call_args_list

    # --- return value ----------------------------------------------------
    def test_returns_none(self):
        self.assertIsNone(self._persist())

    # --- writes ----------------------------------------------------------
    def test_exactly_two_messages_saved(self):
        self._persist()
        self.assertEqual(self.messages.create_message.call_count, 2)

    def test_user_message_saved_once(self):
        self._persist()
        user_calls = [
            c for c in self._create_calls() if c.args[1].role == MessageRole.USER
        ]
        self.assertEqual(len(user_calls), 1)

    def test_assistant_message_saved_once(self):
        self._persist()
        assistant_calls = [
            c
            for c in self._create_calls()
            if c.args[1].role == MessageRole.ASSISTANT
        ]
        self.assertEqual(len(assistant_calls), 1)

    def test_correct_conversation_id_passed(self):
        self._persist()
        for call in self._create_calls():
            self.assertEqual(call.args[0], self.conversation_id)

    def test_message_order_user_then_assistant(self):
        self._persist()
        roles = [c.args[1].role for c in self._create_calls()]
        self.assertEqual(roles, [MessageRole.USER, MessageRole.ASSISTANT])

    def test_user_content_stored_correctly(self):
        self._persist()
        self.assertEqual(self._create_calls()[0].args[1].content, self.user_message)

    def test_ai_response_content_stored_correctly(self):
        self._persist()
        self.assertEqual(
            self._create_calls()[1].args[1].content, self.ai_response.content
        )

    # --- transaction -----------------------------------------------------
    def test_commit_called_once_no_rollback(self):
        self._persist()
        self.session.commit.assert_called_once()
        self.session.rollback.assert_not_called()

    def test_repository_exception_propagates_and_rolls_back(self):
        self.messages.create_message.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            self._persist()
        self.session.rollback.assert_called_once()
        self.session.commit.assert_not_called()

    # --- owner / employee provenance ------------------------------------
    def test_correct_owner_and_employee_id_used(self):
        with self.assertLogs(_LOGGER, level="INFO") as captured:
            self._persist()
        output = "\n".join(captured.output)
        self.assertIn(str(self.owner.id), output)
        self.assertIn(str(self.employee_id), output)
        self.assertIn(str(self.conversation_id), output)

    # --- statelessness / DI ---------------------------------------------
    def test_stateless_only_injected_collaborators(self):
        self.assertEqual(set(vars(self.service)), {"session", "messages"})

    def test_constructor_uses_injected_dependencies(self):
        self.assertIs(self.service.session, self.session)
        self.assertIs(self.service.messages, self.messages)

    def test_di_provider_wires_repository_without_manual_instantiation(self):
        from app.core.dependencies import get_memory_persistence_service
        from app.repositories.message_repository import MessageRepository

        session = MagicMock(name="Session")
        service = get_memory_persistence_service(session)
        self.assertIsInstance(service, MemoryPersistenceService)
        self.assertIsInstance(service.messages, MessageRepository)
        self.assertIs(service.session, session)


if __name__ == "__main__":
    unittest.main()
