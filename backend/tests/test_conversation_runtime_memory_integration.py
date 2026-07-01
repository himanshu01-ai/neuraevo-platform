"""Integration unit tests for Sprint 8.2 — runtime memory persistence.

Every collaborator is mocked (context engine, prompt builder, orchestrator,
memory persistence), so no database, provider, or real service runs. These
verify that ``ConversationRuntimeService.execute`` persists the completed turn
exactly once, after generation, with the correct arguments and the same
``AIResponse`` instance, returns the response unchanged, skips persistence when
generation fails, and propagates persistence errors.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_conversation_runtime_memory_integration
"""

import unittest
import uuid
from unittest.mock import MagicMock

from app.schemas.ai_response import AIResponse, AIResponseMetadata
from app.services.providers import ConversationGenerationError
from app.services.runtime.conversation_runtime_service import (
    ConversationRuntimeService,
)


class RuntimeMemoryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = MagicMock(name="User")
        self.owner.id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.user_input = "What's my next meeting?"

        self.context = MagicMock(name="RuntimeAIContext")
        self.package = MagicMock(name="PromptPackage")
        self.response = AIResponse(
            content="You have a 3pm sync.",
            metadata=AIResponseMetadata(
                provider="test-provider",
                language="en",
                employee_id=self.employee_id,
                conversation_id=self.conversation_id,
                prompt_message_count=2,
            ),
        )

        self.context_engine = MagicMock()
        self.context_engine.build_context.return_value = self.context
        self.prompt_builder = MagicMock()
        self.prompt_builder.build.return_value = self.package
        self.orchestrator = MagicMock()
        self.orchestrator.run.return_value = self.response
        self.memory = MagicMock(name="MemoryPersistenceService")

        self.runtime = ConversationRuntimeService(
            self.context_engine,
            self.prompt_builder,
            self.orchestrator,
            self.memory,
        )

    def _execute(self) -> AIResponse:
        return self.runtime.execute(
            self.owner,
            self.employee_id,
            self.conversation_id,
            self.user_input,
        )

    # 1 / 14. persist called exactly once (no duplication)
    def test_persist_called_exactly_once(self):
        self._execute()
        self.assertEqual(self.memory.persist.call_count, 1)

    # 2. persist called after orchestrator.run()
    def test_persist_called_after_orchestrator(self):
        order = []
        self.orchestrator.run.side_effect = (
            lambda *a, **k: order.append("run") or self.response
        )
        self.memory.persist.side_effect = lambda *a, **k: order.append("persist")
        self._execute()
        self.assertEqual(order, ["run", "persist"])

    # 3-7. persist called with the exact same arguments
    def test_persist_called_with_all_expected_args(self):
        self._execute()
        self.memory.persist.assert_called_once_with(
            self.owner,
            self.employee_id,
            self.conversation_id,
            self.user_input,
            self.response,
        )

    def test_same_owner_passed(self):
        self._execute()
        self.assertIs(self.memory.persist.call_args.args[0], self.owner)

    def test_same_employee_id_passed(self):
        self._execute()
        self.assertEqual(self.memory.persist.call_args.args[1], self.employee_id)

    def test_same_conversation_id_passed(self):
        self._execute()
        self.assertEqual(
            self.memory.persist.call_args.args[2], self.conversation_id
        )

    def test_same_user_message_passed(self):
        self._execute()
        self.assertEqual(self.memory.persist.call_args.args[3], self.user_input)

    def test_same_ai_response_instance_passed(self):
        self._execute()
        self.assertIs(self.memory.persist.call_args.args[4], self.response)

    # 8. returned AIResponse is identical (unchanged)
    def test_returned_response_is_identical(self):
        result = self._execute()
        self.assertIs(result, self.response)

    # 9-11. other services still called exactly once
    def test_context_engine_still_called_once(self):
        self._execute()
        self.context_engine.build_context.assert_called_once()

    def test_prompt_builder_still_called_once(self):
        self._execute()
        self.prompt_builder.build.assert_called_once()

    def test_orchestrator_still_called_once(self):
        self._execute()
        self.orchestrator.run.assert_called_once()

    # 12. memory service exception propagates unchanged
    def test_persistence_exception_propagates(self):
        self.memory.persist.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            self._execute()

    # 13. if orchestrator fails, persist() is never called
    def test_orchestrator_failure_skips_persist(self):
        self.orchestrator.run.side_effect = ConversationGenerationError("boom")
        with self.assertRaises(ConversationGenerationError):
            self._execute()
        self.memory.persist.assert_not_called()

    # 15. service remains stateless (only injected collaborators)
    def test_service_remains_stateless(self):
        self.assertEqual(
            set(vars(self.runtime)),
            {
                "context_engine",
                "prompt_builder",
                "orchestrator",
                "memory_persistence",
            },
        )


if __name__ == "__main__":
    unittest.main()
