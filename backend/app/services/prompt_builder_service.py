"""Prompt builder service.

Pure, stateless transformation of an :class:`AIContextResponse` (Sprint 6C)
into a deterministic plain-text prompt for later LLM consumption. This sprint
does NOT call any model, persist anything, or access repositories — it only
formats text. Same input always yields the identical string.
"""

from app.schemas.ai_context import AIContextResponse

_DIVIDER = "=" * 40

# Blueprint field -> display label, in fixed order.
_BLUEPRINT_FIELDS: list[tuple[str, str]] = [
    ("vision", "Vision"),
    ("goals", "Goals"),
    ("communication_style", "Communication Style"),
    ("personality_traits", "Personality Traits"),
    ("constraints", "Constraints"),
    ("preferences", "Preferences"),
]


class PromptBuilderService:
    """Builds a deterministic plain-text prompt from the unified AI context."""

    def build_prompt(self, ai_context: AIContextResponse) -> str:
        """Render ``ai_context`` into a single deterministic plain-text prompt."""
        lines: list[str] = []

        # --- SYSTEM ------------------------------------------------------
        lines.append(_DIVIDER)
        lines.append("SYSTEM")
        lines.append("")
        lines.append("You are the AI employee.")
        lines.append("")

        # --- BLUEPRINT ---------------------------------------------------
        lines.append(_DIVIDER)
        lines.append("BLUEPRINT")
        lines.append("")
        blueprint = ai_context.blueprint
        for field_name, label in _BLUEPRINT_FIELDS:
            value = getattr(blueprint, field_name)
            lines.append(f"{label}: {value if value else '(none)'}")
        lines.append("")

        # --- MEMORIES (newest first) -------------------------------------
        lines.append(_DIVIDER)
        lines.append("MEMORIES")
        lines.append("")
        memories = ai_context.memory.memories
        if memories:
            for index, memory in enumerate(memories):
                lines.append(f"[{memory.memory_type.value.upper()}]")
                lines.append(memory.content)
                if index < len(memories) - 1:
                    lines.append("")  # blank line between memories
        else:
            lines.append("(No memories)")
        lines.append("")

        # --- CONVERSATION (oldest to newest) -----------------------------
        lines.append(_DIVIDER)
        lines.append("CONVERSATION")
        lines.append("")
        messages = ai_context.conversation.messages
        if messages:
            for index, message in enumerate(messages):
                lines.append(f"{message.role.value.upper()}:")
                lines.append(message.content)
                if index < len(messages) - 1:
                    lines.append("")  # blank line between messages
        else:
            lines.append("(No conversation)")
        lines.append("")

        # --- FINAL INSTRUCTION -------------------------------------------
        lines.append(_DIVIDER)
        lines.append("FINAL INSTRUCTION")
        lines.append("")
        lines.append("Respond as the AI employee.")
        lines.append("Follow the blueprint.")
        lines.append("Use memories when relevant.")
        lines.append("Answer the latest user naturally.")
        lines.append("Return plain text only.")
        lines.append("")
        lines.append(_DIVIDER)

        return "\n".join(lines)
