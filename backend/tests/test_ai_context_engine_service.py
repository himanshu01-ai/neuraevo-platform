"""Unit tests for the Sprint 7.1 AI Context Engine.

These are pure unit tests: every collaborator is mocked, so no database, no
network, and no provider is involved. They verify that the engine
(a) assembles all runtime-context fields from the composed services,
(b) reuses ownership validation (and short-circuits on denial),
(c) performs no database writes, and
(d) carries a deny-by-default permission stub.

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

        # Mocked collaborators (constructor injection).
        self.employees = MagicMock()
        self.employees.get_employee.return_value = self.employee
        self.blueprints = MagicMock()
        self.blueprints.get_blueprint.return_value = self.blueprint
        self.memory = MagicMock()
        self.memory.build_memory_context.return_value = self.memory_context
        self.conversation = MagicMock()
        self.conversation.build_context.return_value = self.conversation_context

        self.session = MagicMock()
        self.service = AIContextEngineService(
            self.session,
            employees=self.employees,
            blueprints=self.blueprints,
            memory=self.memory,
            conversation=self.conversation,
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
        service = AIContextEngineService(self.session)
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


if __name__ == "__main__":
    unittest.main()
