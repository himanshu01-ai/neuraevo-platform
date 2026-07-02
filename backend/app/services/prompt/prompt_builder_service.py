"""Prompt Builder (Sprint 7.2; Sprint 9.3 exposes retrieved history).

Transforms a :class:`RuntimeAIContext` (Sprint 7.1) into a deterministic,
provider-agnostic :class:`PromptPackage`. It assembles the employee identity,
blueprint, memories, recent conversation, retrieved message history, current
user input, language, and personality.

Pure, stateless transformation: no AI provider imports, no Anthropic/OpenAI/
Gemini calls, no prompt execution, no repositories, no service instantiation,
no memory retrieval, no HTTP, no persistence. The same input always yields the
identical package. ``context.retrieved_history`` (Sprint 9.1/9.2's
``MemoryRetrievalService`` result, already assembled by
``AIContextEngineService``) is only ever read here, never fetched, filtered,
ranked, or reordered.
"""

from typing import List

from app.schemas.agent_context import RuntimeAIContext
from app.schemas.message import MessageResponse
from app.schemas.prompt_package import (
    PromptMessage,
    PromptMetadata,
    PromptPackage,
)

_DIVIDER = "=" * 40

# Sprint 9.4: prompt-time window for retrieved history. Only the newest N
# retrieved messages (in their original chronological order) enter the
# PromptPackage; the database and retrieval remain untouched. Intentionally a
# plain constant — no settings, env vars, or injection.
MAX_RETRIEVED_HISTORY_MESSAGES = 50

# Blueprint field -> display label, in fixed order (deterministic output).
_BLUEPRINT_FIELDS: List[tuple] = [
    ("vision", "Vision"),
    ("goals", "Goals"),
    ("communication_style", "Communication Style"),
    ("personality_traits", "Personality Traits"),
    ("constraints", "Constraints"),
    ("preferences", "Preferences"),
]


class RuntimePromptBuilderService:
    """Builds a deterministic :class:`PromptPackage` from a runtime context.

    Stateless and dependency-free by design: it holds no session, services, or
    providers, so there is nothing to mock — it is a pure function of its input.

    Named distinctly from the Sprint 6C
    ``app.services.prompt_builder_service.PromptBuilderService`` (which renders a
    plain-text prompt from the 6C ``AIContextResponse``) to keep the runtime
    pipeline's terminology unambiguous.
    """

    def build(self, context: RuntimeAIContext) -> PromptPackage:
        """Assemble ``context`` into a provider-agnostic prompt package."""
        return PromptPackage(
            system_prompt=self._build_system_prompt(context),
            messages=self._build_messages(context),
            retrieved_history=self._build_retrieved_history(context),
            language=context.language,
            metadata=PromptMetadata(
                employee_id=context.employee.id,
                conversation_id=context.recent_conversation.conversation_id,
                memory_count=context.memories.memory_count,
                message_count=context.recent_conversation.message_count,
            ),
        )

    # --- system prompt ---------------------------------------------------

    def _build_system_prompt(self, context: RuntimeAIContext) -> str:
        """Render the identity/blueprint/personality/memory instruction block."""
        employee = context.employee
        blueprint = context.blueprint
        lines: List[str] = []

        # Identity + language + personality.
        lines.append(_DIVIDER)
        lines.append("IDENTITY")
        lines.append("")
        lines.append(
            f"You are {employee.name}, an AI employee in the role of "
            f"{employee.role}."
        )
        lines.append(
            f"Respond in the user's configured language: {context.language}."
        )
        if context.personality:
            lines.append(f"Personality: {context.personality}")
        lines.append("")

        # Blueprint (fixed field order).
        lines.append(_DIVIDER)
        lines.append("BLUEPRINT")
        lines.append("")
        for field_name, label in _BLUEPRINT_FIELDS:
            value = getattr(blueprint, field_name)
            lines.append(f"{label}: {value if value else '(none)'}")
        lines.append("")

        # Memories (newest-first, as provided by the context).
        lines.append(_DIVIDER)
        lines.append("MEMORIES")
        lines.append("")
        memories = context.memories.memories
        if memories:
            for memory in memories:
                lines.append(
                    f"[{memory.memory_type.value.upper()}] {memory.content}"
                )
        else:
            lines.append("(none)")
        lines.append("")
        lines.append(_DIVIDER)

        return "\n".join(lines)

    # --- messages --------------------------------------------------------

    def _build_messages(self, context: RuntimeAIContext) -> List[PromptMessage]:
        """Map recent history to messages, then append the current user input."""
        messages = [
            PromptMessage(role=message.role.value, content=message.content)
            for message in context.recent_conversation.messages
        ]
        messages.append(
            PromptMessage(role="user", content=context.current_user_input)
        )
        return messages

    # --- retrieved history (Sprint 9.3; windowed in Sprint 9.4) -----------

    def _build_retrieved_history(
        self, context: RuntimeAIContext
    ) -> List[PromptMessage]:
        """Expose ``context.retrieved_history``, windowed to the newest N.

        Roles preserved exactly and content passed through untouched. Sprint
        9.4 applies a prompt-time window (see
        :data:`MAX_RETRIEVED_HISTORY_MESSAGES`): only the newest messages are
        kept, in their original chronological order — no re-sorting, ranking,
        or summarization. An empty ``retrieved_history`` yields an empty list
        here, leaving every other field untouched.
        """
        windowed = self._apply_retrieved_history_window(
            context.retrieved_history
        )
        return [
            PromptMessage(role=message.role.value, content=message.content)
            for message in windowed
        ]

    @staticmethod
    def _apply_retrieved_history_window(
        messages: List[MessageResponse],
    ) -> List[MessageResponse]:
        """Keep only the newest ``MAX_RETRIEVED_HISTORY_MESSAGES`` messages.

        ``retrieved_history`` arrives oldest-first (chronological, matching
        the Sprint 5B repository ordering), so the newest messages are at the
        tail: a ``[-N:]`` slice drops the oldest overflow while preserving
        chronological order. At or below the limit, the input is returned
        unchanged.
        """
        if len(messages) <= MAX_RETRIEVED_HISTORY_MESSAGES:
            return messages
        return messages[-MAX_RETRIEVED_HISTORY_MESSAGES:]
