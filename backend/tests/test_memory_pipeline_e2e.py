"""End-to-end regression tests for the Memory Retrieval milestone (Sprint 9.5).

Every seam of the retrieval path is unit-tested elsewhere, but each of those
tests mocks one side of a seam (the context-engine test mocks retrieval; the
prompt-builder test hand-builds the context; the retrieval test mocks the
repository). This module closes that gap: it wires the **real**
``MemoryRetrievalService`` -> **real** ``AIContextEngineService`` -> **real**
``RuntimePromptBuilderService`` together, mocking only the database boundary
(the ``MessageRepository``) and the unrelated ownership/context collaborators.

It proves the invariants the milestone depends on, across the real chain:

* a stored message propagates unchanged into ``PromptPackage.retrieved_history``
  (same order, roles, and content),
* retrieval happens exactly once and never writes,
* Sprint 9.4 windowing is applied by the time the prompt package is built, and
* the current-conversation ``package.messages`` are unaffected by retrieval or
  windowing.

Pure in-memory: no database, network, provider, or session is involved.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_memory_pipeline_e2e
"""

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import List
from unittest.mock import MagicMock

from app.schemas.conversation_context import (
    ConversationContextMessage,
    ConversationContextResponse,
)
from app.schemas.memory_context import MemoryContextItem, MemoryContextResponse
from app.services.context.ai_context_engine_service import (
    AIContextEngineService,
)
from app.services.memory import MemoryRetrievalService
from app.services.prompt.prompt_builder_service import (
    MAX_RETRIEVED_HISTORY_MESSAGES,
    RuntimePromptBuilderService,
)
from app.utils.constants import MemoryType, MessageRole


class MemoryPipelineEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(timezone.utc)
        self.owner = SimpleNamespace(id=uuid.uuid4())
        self.employee_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.user_input = "What's next on my calendar?"

        # --- ownership / non-retrieval collaborators (mocked) ------------
        self.employee = SimpleNamespace(
            id=self.employee_id,
            user_id=self.owner.id,
            name="Ada",
            role="Executive Assistant",
            description="Handles scheduling.",
            language="en",
            personality="Warm and concise",
            status="active",
            created_at=self.now,
        )
        self.blueprint = SimpleNamespace(
            id=uuid.uuid4(),
            employee_id=self.employee_id,
            vision="Make the user's day effortless.",
            communication_style="Friendly",
            personality_traits="Proactive",
            goals="Keep the calendar tidy",
            constraints="Never double-book",
            preferences="Mornings for deep work",
            created_at=self.now,
        )
        self.memory_context = MemoryContextResponse(
            employee_id=self.employee_id,
            memory_count=1,
            memories=[
                MemoryContextItem(
                    id=uuid.uuid4(),
                    title="Prefers brevity",
                    content="The user prefers short replies.",
                    memory_type=MemoryType.LEARNED,
                    created_at=self.now,
                )
            ],
        )
        # The current conversation window (distinct from retrieved history).
        self.conversation_context = ConversationContextResponse(
            employee_id=self.employee_id,
            conversation_id=self.conversation_id,
            message_count=2,
            messages=[
                ConversationContextMessage(role=MessageRole.USER, content="Hi"),
                ConversationContextMessage(
                    role=MessageRole.ASSISTANT, content="Hello!"
                ),
            ],
        )

        self.employees = MagicMock()
        self.employees.get_employee.return_value = self.employee
        self.blueprints = MagicMock()
        self.blueprints.get_blueprint.return_value = self.blueprint
        self.memory = MagicMock()
        self.memory.build_memory_context.return_value = self.memory_context
        self.conversation = MagicMock()
        self.conversation.build_context.return_value = self.conversation_context

        # --- the real retrieval path -------------------------------------
        # Only the database boundary is mocked: the repository. The retrieval
        # SERVICE, the context engine, and the prompt builder are all real.
        self.repo = MagicMock(name="MessageRepository")
        self.retrieval = MemoryRetrievalService(self.repo)
        self.session = MagicMock(name="Session")
        self.engine = AIContextEngineService(
            self.session,
            memory_retrieval=self.retrieval,
            employees=self.employees,
            blueprints=self.blueprints,
            memory=self.memory,
            conversation=self.conversation,
        )
        self.builder = RuntimePromptBuilderService()

    # --- helpers ----------------------------------------------------------
    def _stored_messages(self, count: int) -> List[SimpleNamespace]:
        """Chronological (oldest-first) stored rows: ``e2e-0`` .. ``e2e-N-1``."""
        return [
            SimpleNamespace(
                id=uuid.uuid4(),
                conversation_id=self.conversation_id,
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"e2e-{i}",
                created_at=self.now,
            )
            for i in range(count)
        ]

    def _run(self, count: int):
        """Drive the real retrieval -> context -> prompt chain end-to-end."""
        self.repo.list_messages.return_value = self._stored_messages(count)
        context = self.engine.build_context(
            self.owner, self.employee_id, self.conversation_id, self.user_input
        )
        package = self.builder.build(context)
        return context, package

    # --- propagation ------------------------------------------------------
    def test_stored_message_propagates_unchanged_to_prompt_package(self):
        context, package = self._run(3)
        # Context layer carries all three, unchanged and in order.
        self.assertEqual(
            [m.content for m in context.retrieved_history],
            ["e2e-0", "e2e-1", "e2e-2"],
        )
        # Prompt package exposes the same, with roles preserved.
        self.assertEqual(
            [(m.role, m.content) for m in package.retrieved_history],
            [("user", "e2e-0"), ("assistant", "e2e-1"), ("user", "e2e-2")],
        )

    # --- retrieval invariants --------------------------------------------
    def test_retrieval_queried_exactly_once(self):
        self._run(3)
        self.repo.list_messages.assert_called_once_with(self.conversation_id)

    def test_retrieval_never_writes(self):
        self._run(3)
        self.repo.create_message.assert_not_called()
        self.repo.delete_message.assert_not_called()
        self.session.commit.assert_not_called()
        self.session.add.assert_not_called()

    # --- windowing applied end-to-end ------------------------------------
    def test_windowing_applied_by_prompt_package(self):
        overflow = 5
        total = MAX_RETRIEVED_HISTORY_MESSAGES + overflow
        context, package = self._run(total)
        # The context still carries everything the repository returned...
        self.assertEqual(len(context.retrieved_history), total)
        # ...but the prompt package is windowed to the newest N, in order.
        self.assertEqual(
            len(package.retrieved_history), MAX_RETRIEVED_HISTORY_MESSAGES
        )
        self.assertEqual(
            package.retrieved_history[0].content, f"e2e-{overflow}"
        )
        self.assertEqual(
            package.retrieved_history[-1].content, f"e2e-{total - 1}"
        )
        self.assertEqual(
            [m.content for m in package.retrieved_history],
            [f"e2e-{i}" for i in range(overflow, total)],
        )

    # --- current conversation is independent of retrieval / windowing ----
    def test_current_conversation_messages_unaffected(self):
        _, package = self._run(MAX_RETRIEVED_HISTORY_MESSAGES + 10)
        pairs = [(m.role, m.content) for m in package.messages]
        self.assertEqual(pairs[0], ("user", "Hi"))
        self.assertEqual(pairs[1], ("assistant", "Hello!"))
        self.assertEqual(pairs[-1], ("user", self.user_input))
        self.assertEqual(len(package.messages), 3)

    # --- empty history ----------------------------------------------------
    def test_empty_history_end_to_end(self):
        context, package = self._run(0)
        self.assertEqual(context.retrieved_history, [])
        self.assertEqual(package.retrieved_history, [])
        # The current conversation is still assembled normally.
        self.assertEqual(len(package.messages), 3)


if __name__ == "__main__":
    unittest.main()
