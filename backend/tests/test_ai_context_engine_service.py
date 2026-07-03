"""Unit tests for the Sprint 7.1 AI Context Engine (Sprint 9.2 adds retrieval).

These are pure unit tests: every collaborator is mocked, so no database, no
network, and no provider is involved. They verify that the engine
(a) assembles all runtime-context fields from the composed services,
(b) reuses ownership validation (and short-circuits on denial),
(c) performs no database writes,
(d) carries a deny-by-default permission stub, and
(e) (Sprint 9.2) calls the existing MemoryRetrievalService exactly once, only
    after ownership has already been validated, and inserts its (unchanged)
    result into ``RuntimeAIContext.retrieved_history``.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_ai_context_engine_service
"""

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.schemas.agent_context import PermissionProfile, RuntimeAIContext
from app.schemas.conversation_context import (
    ConversationContextMessage,
    ConversationContextResponse,
)
from app.schemas.memory_context import MemoryContextItem, MemoryContextResponse
from app.services.context.ai_context_engine_service import (
    AIContextEngineService,
)
from app.services.conversation_service import ConversationNotFoundError
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
)
from app.utils.constants import MemoryType, MessageRole


class AIContextEngineServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(timezone.utc)
        self.owner = SimpleNamespace(id=uuid.uuid4())
        self.employee_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.user_input = "What's on my calendar today?"

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
        self.retrieved_messages = [
            SimpleNamespace(
                id=uuid.uuid4(),
                conversation_id=self.conversation_id,
                role=MessageRole.USER,
                content="Hi",
                created_at=self.now,
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                conversation_id=self.conversation_id,
                role=MessageRole.ASSISTANT,
                content="Hello!",
                created_at=self.now,
            ),
        ]

        # Mocked collaborators (constructor injection).
        self.employees = MagicMock()
        self.employees.get_employee.return_value = self.employee
        self.blueprints = MagicMock()
        self.blueprints.get_blueprint.return_value = self.blueprint
        self.memory = MagicMock()
        self.memory.build_memory_context.return_value = self.memory_context
        self.conversation = MagicMock()
        self.conversation.build_context.return_value = self.conversation_context
        self.memory_retrieval = MagicMock()
        self.memory_retrieval.retrieve.return_value = self.retrieved_messages
        # Sprint 10.5: semantic memories default to empty so pre-existing
        # retrieved_history assertions (recent-only) remain valid; individual
        # merge tests override this.
        self.memory_retrieval.retrieve_semantic.return_value = []

        self.session = MagicMock()
        self.service = AIContextEngineService(
            self.session,
            employees=self.employees,
            blueprints=self.blueprints,
            memory=self.memory,
            conversation=self.conversation,
            memory_retrieval=self.memory_retrieval,
        )

    def _build(self) -> RuntimeAIContext:
        return self.service.build_context(
            self.owner, self.employee_id, self.conversation_id, self.user_input
        )

    # --- assembly --------------------------------------------------------
    def test_assembles_all_runtime_fields(self):
        ctx = self._build()
        self.assertIsInstance(ctx, RuntimeAIContext)
        self.assertEqual(ctx.employee.id, self.employee_id)
        self.assertEqual(ctx.employee.name, "Ada")
        self.assertEqual(ctx.blueprint.vision, "Make the user's day effortless.")
        self.assertEqual(ctx.memories.memory_count, 1)
        self.assertEqual(ctx.recent_conversation.message_count, 2)
        self.assertEqual(ctx.current_user_input, self.user_input)

    def test_reuses_each_service_with_ownership_args(self):
        self._build()
        self.employees.get_employee.assert_called_once_with(
            self.owner, self.employee_id
        )
        self.blueprints.get_blueprint.assert_called_once_with(
            self.owner, self.employee_id
        )
        self.memory.build_memory_context.assert_called_once_with(
            self.owner, self.employee_id
        )
        self.conversation.build_context.assert_called_once_with(
            self.owner, self.employee_id, self.conversation_id
        )

    def test_language_and_personality_sourced_from_employee(self):
        ctx = self._build()
        self.assertEqual(ctx.language, "en")
        self.assertEqual(ctx.personality, "Warm and concise")

    def test_current_user_input_passthrough(self):
        ctx = self.service.build_context(
            self.owner, self.employee_id, self.conversation_id, "ping"
        )
        self.assertEqual(ctx.current_user_input, "ping")

    # --- permission stub -------------------------------------------------
    def test_permission_profile_is_deny_by_default_stub(self):
        ctx = self._build()
        self.assertIsInstance(ctx.permission_profile, PermissionProfile)
        self.assertFalse(ctx.permission_profile.can_use_tools)
        self.assertFalse(ctx.permission_profile.can_write_memory)
        self.assertEqual(ctx.permission_profile.allowed_tools, [])

    # --- no writes -------------------------------------------------------
    def test_performs_no_database_writes(self):
        self._build()
        self.session.commit.assert_not_called()
        self.session.add.assert_not_called()
        self.session.flush.assert_not_called()
        self.session.delete.assert_not_called()

    # --- ownership propagation / short-circuit ---------------------------
    def test_access_denied_short_circuits(self):
        self.employees.get_employee.side_effect = EmployeeAccessDeniedError("x")
        with self.assertRaises(EmployeeAccessDeniedError):
            self._build()
        # Nothing downstream should run once ownership fails.
        self.blueprints.get_blueprint.assert_not_called()
        self.memory.build_memory_context.assert_not_called()
        self.conversation.build_context.assert_not_called()
        self.session.commit.assert_not_called()

    def test_employee_not_found_propagates(self):
        self.employees.get_employee.side_effect = EmployeeNotFoundError("x")
        with self.assertRaises(EmployeeNotFoundError):
            self._build()

    def test_conversation_not_found_propagates(self):
        self.conversation.build_context.side_effect = ConversationNotFoundError(
            "x"
        )
        with self.assertRaises(ConversationNotFoundError):
            self._build()

    # --- default collaborators (no explicit injection) -------------------
    def test_defaults_to_session_bound_collaborators(self):
        # memory_retrieval has no session-based default (Sprint 9.2
        # refactor): its own constructor takes a repository, not a session, so
        # it must always be injected — supplied here so the *other* four
        # collaborators' defaulting behavior can still be exercised.
        service = AIContextEngineService(
            self.session, memory_retrieval=self.memory_retrieval
        )
        from app.services.blueprint_service import BlueprintService
        from app.services.conversation_context_service import (
            ConversationContextService,
        )
        from app.services.employee_service import EmployeeService
        from app.services.memory_context_service import MemoryContextService

        self.assertIsInstance(service.employees, EmployeeService)
        self.assertIsInstance(service.blueprints, BlueprintService)
        self.assertIsInstance(service.memory, MemoryContextService)
        self.assertIsInstance(service.conversation, ConversationContextService)
        self.assertIs(service.memory_retrieval, self.memory_retrieval)

    def test_memory_retrieval_is_required_not_defaulted(self):
        # Guards the Sprint 9.2 architectural fix: MemoryRetrievalService must
        # never be constructed inline by this engine (that would require
        # importing MessageRepository here), so omitting it is a TypeError
        # rather than silently building a default.
        with self.assertRaises(TypeError):
            AIContextEngineService(self.session)

    def test_does_not_import_message_repository(self):
        import app.services.context.ai_context_engine_service as module

        self.assertFalse(hasattr(module, "MessageRepository"))

    # --- Sprint 9.2: memory retrieval integration -------------------------
    def test_memory_retrieval_called_exactly_once(self):
        self._build()
        self.memory_retrieval.retrieve.assert_called_once()

    def test_memory_retrieval_called_with_correct_args(self):
        self._build()
        self.memory_retrieval.retrieve.assert_called_once_with(
            self.owner, self.employee_id, self.conversation_id
        )

    def test_memory_retrieval_called_after_ownership_validation(self):
        call_order = []
        self.conversation.build_context.side_effect = (
            lambda *a, **k: call_order.append("conversation_ownership")
            or self.conversation_context
        )
        self.memory_retrieval.retrieve.side_effect = (
            lambda *a, **k: call_order.append("retrieve")
            or self.retrieved_messages
        )
        self._build()
        self.assertEqual(call_order, ["conversation_ownership", "retrieve"])

    def test_retrieved_messages_inserted_into_context(self):
        ctx = self._build()
        self.assertEqual(len(ctx.retrieved_history), 2)
        self.assertEqual(ctx.retrieved_history[0].content, "Hi")
        self.assertEqual(ctx.retrieved_history[0].role, MessageRole.USER)
        self.assertEqual(ctx.retrieved_history[1].content, "Hello!")
        self.assertEqual(ctx.retrieved_history[1].role, MessageRole.ASSISTANT)

    def test_empty_history_returns_empty_list(self):
        self.memory_retrieval.retrieve.return_value = []
        ctx = self._build()
        self.assertEqual(ctx.retrieved_history, [])

    def test_memory_retrieval_exception_propagates(self):
        self.memory_retrieval.retrieve.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            self._build()

    def test_employee_ownership_failure_skips_retrieval(self):
        self.employees.get_employee.side_effect = EmployeeAccessDeniedError("x")
        with self.assertRaises(EmployeeAccessDeniedError):
            self._build()
        self.memory_retrieval.retrieve.assert_not_called()

    def test_conversation_ownership_failure_skips_retrieval(self):
        self.conversation.build_context.side_effect = ConversationNotFoundError(
            "x"
        )
        with self.assertRaises(ConversationNotFoundError):
            self._build()
        self.memory_retrieval.retrieve.assert_not_called()

    def test_constructor_injected_memory_retrieval_is_used(self):
        self.assertIs(self.service.memory_retrieval, self.memory_retrieval)

    def test_di_provider_wires_memory_retrieval_without_manual_construction(self):
        from app.core.dependencies import get_ai_context_engine_service

        session = MagicMock(name="Session")
        memory_retrieval = MagicMock(name="MemoryRetrievalService")
        service = get_ai_context_engine_service(session, memory_retrieval)
        self.assertIsInstance(service, AIContextEngineService)
        self.assertIs(service.memory_retrieval, memory_retrieval)

    # =================================================================
    # Sprint 10.5 — semantic memory merged into retrieved_history
    # =================================================================
    def _msg(self, *, mid=None, role=MessageRole.USER, content="x"):
        return SimpleNamespace(
            id=mid or uuid.uuid4(),
            conversation_id=self.conversation_id,
            role=role,
            content=content,
            created_at=self.now,
        )

    def _set_history(self, recent, semantic):
        self.memory_retrieval.retrieve.return_value = recent
        self.memory_retrieval.retrieve_semantic.return_value = semantic

    def test_retrieve_called_once(self):
        self._build()
        self.memory_retrieval.retrieve.assert_called_once()

    def test_retrieve_semantic_called_once(self):
        self._build()
        self.memory_retrieval.retrieve_semantic.assert_called_once()

    def test_current_user_input_passed_to_retrieve_semantic(self):
        self._build()
        self.memory_retrieval.retrieve_semantic.assert_called_once_with(
            self.user_input
        )

    def test_merge_order_recent_then_semantic_dedup_by_id(self):
        # Recent A,B,C ; Semantic C,D,E  ->  A,B,C,D,E (never reordered).
        a, b, c, d, e = (uuid.uuid4() for _ in range(5))
        recent = [
            self._msg(mid=a, content="A"),
            self._msg(mid=b, content="B"),
            self._msg(mid=c, content="C"),
        ]
        semantic = [
            self._msg(mid=c, content="C"),
            self._msg(mid=d, content="D"),
            self._msg(mid=e, content="E"),
        ]
        self._set_history(recent, semantic)
        ctx = self._build()
        self.assertEqual([m.id for m in ctx.retrieved_history], [a, b, c, d, e])
        self.assertEqual(
            [m.content for m in ctx.retrieved_history],
            ["A", "B", "C", "D", "E"],
        )

    def test_duplicate_ids_removed_recent_copy_wins(self):
        dup = uuid.uuid4()
        self._set_history(
            [self._msg(mid=dup, content="recent-copy")],
            [self._msg(mid=dup, content="semantic-copy")],
        )
        ctx = self._build()
        self.assertEqual(len(ctx.retrieved_history), 1)
        self.assertEqual(ctx.retrieved_history[0].id, dup)
        # First (recent) occurrence is the one kept.
        self.assertEqual(ctx.retrieved_history[0].content, "recent-copy")

    def test_duplicate_text_different_ids_kept(self):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        self._set_history(
            [self._msg(mid=id1, content="identical text")],
            [self._msg(mid=id2, content="identical text")],
        )
        ctx = self._build()
        self.assertEqual([m.id for m in ctx.retrieved_history], [id1, id2])
        self.assertEqual(len(ctx.retrieved_history), 2)

    def test_empty_semantic_returns_recent_only(self):
        self._set_history(
            [self._msg(content="A"), self._msg(content="B")], []
        )
        ctx = self._build()
        self.assertEqual(
            [m.content for m in ctx.retrieved_history], ["A", "B"]
        )

    def test_empty_recent_returns_semantic_only(self):
        self._set_history(
            [], [self._msg(content="S1"), self._msg(content="S2")]
        )
        ctx = self._build()
        self.assertEqual(
            [m.content for m in ctx.retrieved_history], ["S1", "S2"]
        )

    def test_both_empty_returns_empty(self):
        self._set_history([], [])
        ctx = self._build()
        self.assertEqual(ctx.retrieved_history, [])

    def test_prompt_builder_receives_merged_history_unchanged(self):
        # The unchanged Sprint 7.2 builder consumes context.retrieved_history;
        # feeding it the merged context yields the same merged sequence.
        from app.services.prompt.prompt_builder_service import (
            RuntimePromptBuilderService,
        )

        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        recent = [
            self._msg(mid=a, role=MessageRole.USER, content="A"),
            self._msg(mid=b, role=MessageRole.ASSISTANT, content="B"),
        ]
        semantic = [
            self._msg(mid=b, role=MessageRole.ASSISTANT, content="B"),
            self._msg(mid=c, role=MessageRole.USER, content="C"),
        ]
        self._set_history(recent, semantic)
        ctx = self._build()

        package = RuntimePromptBuilderService().build(ctx)
        self.assertEqual(
            [m.content for m in package.retrieved_history], ["A", "B", "C"]
        )
        self.assertEqual(
            [m.role for m in package.retrieved_history],
            ["user", "assistant", "user"],
        )

    def test_semantic_failure_degrades_to_recent_only(self):
        # retrieve_semantic raises (e.g. embedding provider unwired); context
        # assembly must not fail — recent history is the guaranteed baseline.
        self.memory_retrieval.retrieve.return_value = [
            self._msg(content="A"),
            self._msg(content="B"),
        ]
        self.memory_retrieval.retrieve_semantic.side_effect = RuntimeError(
            "no embedding provider"
        )
        ctx = self._build()
        self.assertEqual(
            [m.content for m in ctx.retrieved_history], ["A", "B"]
        )

    def test_repeated_build_does_not_accumulate_state(self):
        self._set_history([self._msg(content="A")], [self._msg(content="S")])
        first = self._build()
        second = self._build()
        self.assertEqual(len(first.retrieved_history), 2)
        self.assertEqual(len(second.retrieved_history), 2)


if __name__ == "__main__":
    unittest.main()
