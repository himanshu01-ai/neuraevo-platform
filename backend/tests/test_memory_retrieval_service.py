"""Unit tests for the Sprint 9.1 Memory Retrieval Service.

The repository is mocked, so no database is touched. The tests verify that
``retrieve`` calls the existing ``MessageRepository`` exactly once with the
given conversation, returns its result unchanged (including the empty-list
case), propagates repository failures untouched, performs no writes, and is
a stateless, constructor-injected service.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_memory_retrieval_service
"""

import unittest
import uuid
from unittest.mock import MagicMock

from app.services.memory.memory_retrieval_service import (
    MemoryRetrievalService,
)

_LOGGER = "app.services.memory.memory_retrieval_service"


class MemoryRetrievalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = MagicMock(name="User")
        self.owner.id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()

        self.stored_messages = [
            MagicMock(name="message_1"),
            MagicMock(name="message_2"),
        ]
        self.messages = MagicMock(name="MessageRepository")
        self.messages.list_messages.return_value = self.stored_messages
        self.service = MemoryRetrievalService(self.messages)

    def _retrieve(self):
        return self.service.retrieve(
            self.owner, self.employee_id, self.conversation_id
        )

    # --- repository interaction -------------------------------------------
    def test_repository_called_exactly_once(self):
        self._retrieve()
        self.messages.list_messages.assert_called_once()

    def test_correct_conversation_id_passed(self):
        self._retrieve()
        self.messages.list_messages.assert_called_once_with(
            self.conversation_id
        )

    def test_correct_owner_and_employee_id_used(self):
        with self.assertLogs(_LOGGER, level="INFO") as captured:
            self._retrieve()
        output = "\n".join(captured.output)
        self.assertIn(str(self.owner.id), output)
        self.assertIn(str(self.employee_id), output)
        self.assertIn(str(self.conversation_id), output)

    # --- return value -------------------------------------------------------
    def test_returned_messages_unchanged(self):
        result = self._retrieve()
        self.assertIs(result, self.stored_messages)

    def test_empty_conversation_returns_empty_list(self):
        self.messages.list_messages.return_value = []
        result = self._retrieve()
        self.assertEqual(result, [])

    # --- error propagation ----------------------------------------------------
    def test_repository_exception_propagates(self):
        self.messages.list_messages.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            self._retrieve()

    # --- read-only contract ---------------------------------------------------
    def test_no_write_calls_on_repository(self):
        self._retrieve()
        self.messages.create_message.assert_not_called()
        self.messages.delete_message.assert_not_called()

    # --- statelessness / DI -----------------------------------------------
    def test_stateless_only_injected_collaborator(self):
        self.assertEqual(set(vars(self.service)), {"messages"})

    def test_constructor_uses_injected_dependency(self):
        self.assertIs(self.service.messages, self.messages)

    def test_di_provider_wires_repository_without_manual_instantiation(self):
        from app.core.dependencies import get_memory_retrieval_service
        from app.repositories.message_repository import MessageRepository

        session = MagicMock(name="Session")
        service = get_memory_retrieval_service(session)
        self.assertIsInstance(service, MemoryRetrievalService)
        self.assertIsInstance(service.messages, MessageRepository)


if __name__ == "__main__":
    unittest.main()
