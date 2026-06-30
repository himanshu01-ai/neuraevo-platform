"""Unit tests for the Sprint 7.2 Prompt Builder (app/services/prompt/).

The builder is a pure transformer with no service/DB/provider collaborators
(there is nothing to mock), so these tests drive it with representative
``RuntimeAIContext`` inputs and assert the assembled ``PromptPackage``. No
database, network, or provider is involved.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_prompt_builder_service
"""

import unittest
import uuid
from datetime import datetime, timezone

from app.schemas.agent_context import PermissionProfile, RuntimeAIContext
from app.schemas.blueprint import BlueprintResponse
from app.schemas.conversation_context import (
    ConversationContextMessage,
    ConversationContextResponse,
)
from app.schemas.employee import EmployeeResponse
from app.schemas.memory_context import MemoryContextItem, MemoryContextResponse
from app.schemas.prompt_package import PromptPackage
from app.services.prompt.prompt_builder_service import (
    RuntimePromptBuilderService,
)
from app.utils.constants import MemoryType, MessageRole


def make_context(
    *,
    with_memories: bool = True,
    with_conversation: bool = True,
    personality="Warm and concise",
    user_input: str = "What's next on my calendar?",
) -> RuntimeAIContext:
    now = datetime.now(timezone.utc)
    employee_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    employee = EmployeeResponse(
        id=employee_id,
        user_id=uuid.uuid4(),
        name="Ada",
        role="Executive Assistant",
        description=None,
        language="en",
        personality=personality,
        status="active",
        created_at=now,
    )
    blueprint = BlueprintResponse(
        id=uuid.uuid4(),
        employee_id=employee_id,
        vision="Make the user's day effortless.",
        communication_style="Friendly",
        personality_traits="Proactive",
        goals="Keep the calendar tidy",
        constraints="Never double-book",
        preferences="Mornings for deep work",
        created_at=now,
    )
    mem_items = (
        [
            MemoryContextItem(
                id=uuid.uuid4(),
                title="Prefers brevity",
                content="The user prefers short replies.",
                memory_type=MemoryType.LEARNED,
                created_at=now,
            )
        ]
        if with_memories
        else []
    )
    memories = MemoryContextResponse(
        employee_id=employee_id,
        memory_count=len(mem_items),
        memories=mem_items,
    )
    msgs = (
        [
            ConversationContextMessage(role=MessageRole.USER, content="Hi"),
            ConversationContextMessage(
                role=MessageRole.ASSISTANT, content="Hello!"
            ),
        ]
        if with_conversation
        else []
    )
    conversation = ConversationContextResponse(
        employee_id=employee_id,
        conversation_id=conversation_id,
        message_count=len(msgs),
        messages=msgs,
    )
    return RuntimeAIContext(
        employee=employee,
        blueprint=blueprint,
        memories=memories,
        recent_conversation=conversation,
        permission_profile=PermissionProfile(),
        language="en",
        personality=personality,
        current_user_input=user_input,
    )


class PromptBuilderServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = RuntimePromptBuilderService()

    def test_build_returns_prompt_package(self):
        pkg = self.builder.build(make_context())
        self.assertIsInstance(pkg, PromptPackage)

    def test_system_prompt_assembles_all_parts(self):
        sp = self.builder.build(make_context()).system_prompt
        self.assertIn("Ada", sp)  # employee name
        self.assertIn("Executive Assistant", sp)  # employee role
        self.assertIn("Make the user's day effortless.", sp)  # blueprint vision
        self.assertIn("Friendly", sp)  # communication style
        self.assertIn("Warm and concise", sp)  # personality
        self.assertIn("en", sp)  # language directive
        self.assertIn("The user prefers short replies.", sp)  # memory content

    def test_messages_are_history_then_current_user_input(self):
        pkg = self.builder.build(make_context(user_input="Schedule a call"))
        pairs = [(m.role, m.content) for m in pkg.messages]
        self.assertEqual(pairs[0], ("user", "Hi"))
        self.assertEqual(pairs[1], ("assistant", "Hello!"))
        self.assertEqual(pairs[-1], ("user", "Schedule a call"))
        self.assertEqual(len(pkg.messages), 3)

    def test_language_surfaced_at_top_level(self):
        self.assertEqual(self.builder.build(make_context()).language, "en")

    def test_metadata_is_accurate(self):
        ctx = make_context()
        meta = self.builder.build(ctx).metadata
        self.assertEqual(meta.employee_id, ctx.employee.id)
        self.assertEqual(
            meta.conversation_id, ctx.recent_conversation.conversation_id
        )
        self.assertEqual(meta.memory_count, 1)
        self.assertEqual(meta.message_count, 2)

    def test_output_is_deterministic(self):
        ctx = make_context()
        self.assertEqual(
            self.builder.build(ctx).model_dump(),
            self.builder.build(ctx).model_dump(),
        )

    def test_empty_memories_and_conversation(self):
        pkg = self.builder.build(
            make_context(
                with_memories=False, with_conversation=False, user_input="Hello"
            )
        )
        self.assertIn("(none)", pkg.system_prompt)  # no memories block
        self.assertEqual(len(pkg.messages), 1)  # only the current input
        self.assertEqual(pkg.messages[0].role, "user")
        self.assertEqual(pkg.messages[0].content, "Hello")
        self.assertEqual(pkg.metadata.message_count, 0)

    def test_missing_personality_is_handled(self):
        pkg = self.builder.build(make_context(personality=None))
        self.assertNotIn("Personality:", pkg.system_prompt)

    def test_builder_is_stateless_no_collaborators(self):
        # Pure transformer: nothing to mock — it holds no session/services.
        self.assertEqual(vars(self.builder), {})

    def test_no_provider_or_ai_imports(self):
        import app.services.prompt.prompt_builder_service as module

        with open(module.__file__, encoding="utf-8") as handle:
            src = handle.read()
        for needle in ("import anthropic", "openai", "genai", ".messages.create"):
            self.assertNotIn(needle, src)
        for name in (
            "anthropic",
            "ClaudeConversationProvider",
            "ConversationProvider",
        ):
            self.assertNotIn(name, dir(module))


if __name__ == "__main__":
    unittest.main()
