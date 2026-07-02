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
from typing import List, Optional

from app.schemas.agent_context import PermissionProfile, RuntimeAIContext
from app.schemas.blueprint import BlueprintResponse
from app.schemas.conversation_context import (
    ConversationContextMessage,
    ConversationContextResponse,
)
from app.schemas.employee import EmployeeResponse
from app.schemas.memory_context import MemoryContextItem, MemoryContextResponse
from app.schemas.message import MessageResponse
from app.schemas.prompt_package import PromptPackage
from app.services.prompt.prompt_builder_service import (
    MAX_RETRIEVED_HISTORY_MESSAGES,
    RuntimePromptBuilderService,
)
from app.utils.constants import MemoryType, MessageRole


def make_context(
    *,
    with_memories: bool = True,
    with_conversation: bool = True,
    personality="Warm and concise",
    user_input: str = "What's next on my calendar?",
    retrieved_history: Optional[List[MessageResponse]] = None,
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
        retrieved_history=retrieved_history or [],
        permission_profile=PermissionProfile(),
        language="en",
        personality=personality,
        current_user_input=user_input,
    )


def make_retrieved_message(
    *, conversation_id: uuid.UUID, role: MessageRole, content: str
) -> MessageResponse:
    """Build a Sprint 9.1 ``MessageResponse`` for ``retrieved_history`` fixtures."""
    return MessageResponse(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc),
    )


def make_retrieved_history(count: int) -> List[MessageResponse]:
    """Build ``count`` chronological messages labeled ``msg-0`` (oldest) up to
    ``msg-{count-1}`` (newest), alternating USER/ASSISTANT roles."""
    conversation_id = uuid.uuid4()
    return [
        make_retrieved_message(
            conversation_id=conversation_id,
            role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
            content=f"msg-{i}",
        )
        for i in range(count)
    ]


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

    # --- Sprint 9.3: retrieved history exposed in the prompt package -----

    def test_retrieved_history_included_in_prompt_package(self):
        conversation_id = uuid.uuid4()
        history = [
            make_retrieved_message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content="What's the weather?",
            ),
            make_retrieved_message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content="Sunny and 72F.",
            ),
        ]
        pkg = self.builder.build(make_context(retrieved_history=history))
        self.assertEqual(len(pkg.retrieved_history), 2)
        self.assertEqual(pkg.retrieved_history[0].content, "What's the weather?")
        self.assertEqual(pkg.retrieved_history[1].content, "Sunny and 72F.")

    def test_retrieved_history_order_preserved(self):
        conversation_id = uuid.uuid4()
        history = [
            make_retrieved_message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content="first",
            ),
            make_retrieved_message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content="second",
            ),
            make_retrieved_message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content="third",
            ),
        ]
        pkg = self.builder.build(make_context(retrieved_history=history))
        self.assertEqual(
            [m.content for m in pkg.retrieved_history],
            ["first", "second", "third"],
        )

    def test_retrieved_history_roles_preserved(self):
        conversation_id = uuid.uuid4()
        history = [
            make_retrieved_message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content="hi",
            ),
            make_retrieved_message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content="hello",
            ),
        ]
        pkg = self.builder.build(make_context(retrieved_history=history))
        self.assertEqual(pkg.retrieved_history[0].role, "user")
        self.assertEqual(pkg.retrieved_history[1].role, "assistant")

    def test_retrieved_history_content_unaltered(self):
        conversation_id = uuid.uuid4()
        raw_content = "  Exact content, including   spacing.  "
        history = [
            make_retrieved_message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=raw_content,
            )
        ]
        pkg = self.builder.build(make_context(retrieved_history=history))
        self.assertEqual(pkg.retrieved_history[0].content, raw_content)

    def test_empty_retrieved_history_yields_empty_list(self):
        pkg = self.builder.build(make_context())
        self.assertEqual(pkg.retrieved_history, [])

    def test_empty_retrieved_history_matches_previous_sprint_structure(self):
        # With no retrieved_history, every other field must be byte-identical
        # to the pre-Sprint-9.3 package: system_prompt, messages, language,
        # and metadata are unaffected by this field's presence or absence.
        ctx = make_context(user_input="Schedule a call")
        pkg = self.builder.build(ctx)
        pairs = [(m.role, m.content) for m in pkg.messages]
        self.assertEqual(pairs[0], ("user", "Hi"))
        self.assertEqual(pairs[1], ("assistant", "Hello!"))
        self.assertEqual(pairs[-1], ("user", "Schedule a call"))
        self.assertEqual(len(pkg.messages), 3)
        self.assertEqual(pkg.language, "en")
        self.assertEqual(pkg.metadata.message_count, 2)
        self.assertEqual(pkg.retrieved_history, [])

    def test_retrieved_history_independent_of_recent_conversation(self):
        # retrieved_history and recent_conversation.messages are populated
        # from separate RuntimeAIContext fields; the builder must not mix
        # them — retrieved_history reflects only what it was given.
        conversation_id = uuid.uuid4()
        history = [
            make_retrieved_message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content="only in retrieved_history",
            )
        ]
        pkg = self.builder.build(
            make_context(with_conversation=True, retrieved_history=history)
        )
        self.assertEqual(len(pkg.retrieved_history), 1)
        self.assertEqual(
            pkg.retrieved_history[0].content, "only in retrieved_history"
        )
        # ``messages`` still comes solely from recent_conversation + input.
        self.assertEqual(len(pkg.messages), 3)

    def test_no_memory_retrieval_service_referenced(self):
        # No import, instantiation, or call of MemoryRetrievalService — only
        # a doc mention of where context.retrieved_history came from is
        # permitted (checked precisely, not by banning the bare word, since
        # the module's docstring legitimately explains the field's origin).
        import app.services.prompt.prompt_builder_service as module

        self.assertFalse(hasattr(module, "MemoryRetrievalService"))
        with open(module.__file__, encoding="utf-8") as handle:
            lines = handle.readlines()
        for line in lines:
            if "MemoryRetrievalService" in line:
                self.assertNotIn("import", line)
        self.assertNotIn(
            "MemoryRetrievalService(", "".join(lines)
        )
        self.assertNotIn(".retrieve(", "".join(lines))

    def test_no_repository_imports(self):
        import app.services.prompt.prompt_builder_service as module

        with open(module.__file__, encoding="utf-8") as handle:
            src = handle.read()
        self.assertNotIn("import app.repositories", src)
        self.assertNotIn("Repository(", src)
        self.assertFalse(hasattr(module, "MessageRepository"))

    # --- Sprint 9.4: retrieved history windowing --------------------------

    def test_history_below_limit_unchanged(self):
        history = make_retrieved_history(MAX_RETRIEVED_HISTORY_MESSAGES - 1)
        pkg = self.builder.build(make_context(retrieved_history=history))
        self.assertEqual(
            [m.content for m in pkg.retrieved_history],
            [m.content for m in history],
        )

    def test_history_exactly_at_limit_unchanged(self):
        history = make_retrieved_history(MAX_RETRIEVED_HISTORY_MESSAGES)
        pkg = self.builder.build(make_context(retrieved_history=history))
        self.assertEqual(
            len(pkg.retrieved_history), MAX_RETRIEVED_HISTORY_MESSAGES
        )
        self.assertEqual(
            [m.content for m in pkg.retrieved_history],
            [m.content for m in history],
        )

    def test_history_above_limit_truncated_to_window(self):
        history = make_retrieved_history(MAX_RETRIEVED_HISTORY_MESSAGES + 7)
        pkg = self.builder.build(make_context(retrieved_history=history))
        self.assertEqual(
            len(pkg.retrieved_history), MAX_RETRIEVED_HISTORY_MESSAGES
        )

    def test_window_keeps_newest_messages(self):
        overflow = 7
        total = MAX_RETRIEVED_HISTORY_MESSAGES + overflow
        history = make_retrieved_history(total)
        pkg = self.builder.build(make_context(retrieved_history=history))
        # The oldest `overflow` messages are dropped; the newest survive.
        self.assertEqual(pkg.retrieved_history[0].content, f"msg-{overflow}")
        self.assertEqual(pkg.retrieved_history[-1].content, f"msg-{total - 1}")

    def test_window_preserves_chronological_order(self):
        overflow = 3
        total = MAX_RETRIEVED_HISTORY_MESSAGES + overflow
        history = make_retrieved_history(total)
        pkg = self.builder.build(make_context(retrieved_history=history))
        self.assertEqual(
            [m.content for m in pkg.retrieved_history],
            [f"msg-{i}" for i in range(overflow, total)],
        )

    def test_windowing_leaves_package_messages_untouched(self):
        history = make_retrieved_history(MAX_RETRIEVED_HISTORY_MESSAGES + 10)
        ctx_with = make_context(
            user_input="Schedule a call", retrieved_history=history
        )
        pkg = self.builder.build(ctx_with)
        # package.messages is exactly recent_conversation + current input,
        # regardless of how much retrieved history was windowed away.
        pairs = [(m.role, m.content) for m in pkg.messages]
        self.assertEqual(pairs[0], ("user", "Hi"))
        self.assertEqual(pairs[1], ("assistant", "Hello!"))
        self.assertEqual(pairs[-1], ("user", "Schedule a call"))
        self.assertEqual(len(pkg.messages), 3)

    def test_windowed_empty_history_still_empty(self):
        pkg = self.builder.build(make_context(retrieved_history=[]))
        self.assertEqual(pkg.retrieved_history, [])

    def test_window_constant_is_simple_positive_int(self):
        # Guard the "plain constant" requirement: an int, not settings-driven.
        self.assertIsInstance(MAX_RETRIEVED_HISTORY_MESSAGES, int)
        self.assertGreater(MAX_RETRIEVED_HISTORY_MESSAGES, 0)

    def test_builder_still_stateless_after_windowing(self):
        history = make_retrieved_history(MAX_RETRIEVED_HISTORY_MESSAGES + 5)
        self.builder.build(make_context(retrieved_history=history))
        self.assertEqual(vars(self.builder), {})

    def test_no_settings_or_env_used_for_window(self):
        import app.services.prompt.prompt_builder_service as module

        with open(module.__file__, encoding="utf-8") as handle:
            src = handle.read()
        self.assertNotIn("os.environ", src)
        self.assertNotIn("getenv", src)
        self.assertNotIn("from app.core.config", src)


if __name__ == "__main__":
    unittest.main()
