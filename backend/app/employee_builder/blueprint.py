"""Blueprint generation engine.

``BlueprintGenerator`` centralizes prompt construction and delegates the actual
draft synthesis to a replaceable :class:`BlueprintGenerationProvider`. Sprint
4A ships only a deterministic, no-AI stub provider; real AI providers
(Claude/OpenAI) can be dropped in later by implementing the same interface.

This module never calls an external AI service and never touches the database.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from app.schemas.blueprint_generation import (
    BlueprintGenerationContext,
    GeneratedBlueprintDraft,
)

# Human-readable labels for the blueprint fields, used in prompt construction
# and the deterministic draft. Order is intentional and stable.
_FIELD_LABELS: list[tuple[str, str]] = [
    ("vision", "Vision"),
    ("communication_style", "Communication style"),
    ("personality_traits", "Personality traits"),
    ("goals", "Goals"),
    ("constraints", "Constraints"),
    ("preferences", "Preferences"),
]


@dataclass
class GenerationResult:
    """Output of a generation run: the prompt, the draft, and provenance."""

    prompt: str
    draft: GeneratedBlueprintDraft
    provider: str
    model: Optional[str]
    deterministic: bool
    warnings: List[str] = field(default_factory=list)


class BlueprintGenerationProvider(ABC):
    """Replaceable strategy that turns a prompt + context into a draft.

    Concrete providers (e.g. an Anthropic or OpenAI implementation) live behind
    this interface so the rest of the engine is provider-agnostic.
    """

    name: str
    model: Optional[str] = None
    deterministic: bool = False

    @abstractmethod
    def generate(
        self, prompt: str, context: BlueprintGenerationContext
    ) -> GeneratedBlueprintDraft:
        """Produce a draft blueprint from the prompt and context."""


class DeterministicBlueprintProvider(BlueprintGenerationProvider):
    """No-AI placeholder provider.

    Preserves any existing blueprint field, and for empty fields emits a
    transparent, deterministic draft note referencing how much interview data
    is available. It never fabricates specific content — that is the job of a
    real AI provider added in a later sprint.
    """

    name = "deterministic-stub"
    model = None
    deterministic = True

    def generate(
        self, prompt: str, context: BlueprintGenerationContext
    ) -> GeneratedBlueprintDraft:
        existing = context.existing_blueprint
        answered = context.answered_count

        values: dict[str, Optional[str]] = {}
        for field_name, label in _FIELD_LABELS:
            current = getattr(existing, field_name)
            if current and current.strip():
                values[field_name] = current
            elif answered > 0:
                values[field_name] = (
                    f"[draft:{self.name}] {label} to be synthesized from "
                    f"{answered} answered interview question(s)."
                )
            else:
                values[field_name] = None

        return GeneratedBlueprintDraft(**values)


class BlueprintGenerator:
    """Constructs the generation prompt and runs it through a provider."""

    def __init__(
        self, provider: Optional[BlueprintGenerationProvider] = None
    ) -> None:
        self.provider = provider or DeterministicBlueprintProvider()

    def build_prompt(self, context: BlueprintGenerationContext) -> str:
        """Centralized prompt construction (deterministic).

        Produces the text a downstream AI provider would receive. Kept in one
        place so prompt changes never leak into routers or providers.
        """
        lines: list[str] = []
        lines.append(
            "You are generating a structured profile (blueprint) for an AI "
            "employee from interview data."
        )
        lines.append("")
        lines.append("# Employee")
        lines.append(f"- Name: {context.employee_name}")
        lines.append(f"- Role: {context.role}")
        lines.append(f"- Language: {context.language}")
        if context.personality:
            lines.append(f"- Personality: {context.personality}")
        lines.append("")

        lines.append("# Existing blueprint")
        existing = context.existing_blueprint
        for field_name, label in _FIELD_LABELS:
            value = getattr(existing, field_name)
            lines.append(f"- {label}: {value if value else '(empty)'}")
        lines.append("")

        lines.append(
            f"# Interview ({context.answered_count}/{context.total_questions} "
            "answered)"
        )
        if context.qa_items:
            for item in context.qa_items:
                answer = item.answer_text if item.answered else "(unanswered)"
                lines.append(f"{item.question_order}. Q: {item.question_text}")
                lines.append(f"   A: {answer}")
        else:
            lines.append("(no interview questions)")
        lines.append("")

        lines.append("# Task")
        field_names = ", ".join(label for _, label in _FIELD_LABELS)
        lines.append(
            f"Produce concise values for: {field_names}. Use the interview "
            "answers; leave a field empty if there is insufficient information."
        )
        return "\n".join(lines)

    def generate(
        self, context: BlueprintGenerationContext
    ) -> GenerationResult:
        """Build the prompt, run the provider, and collect warnings."""
        prompt = self.build_prompt(context)
        draft = self.provider.generate(prompt, context)

        warnings: list[str] = []
        if context.total_questions == 0:
            warnings.append(
                "No interview questions exist for this blueprint; the draft is "
                "based only on existing blueprint values."
            )
        elif context.answered_count == 0:
            warnings.append(
                "No interview questions have been answered; the draft is based "
                "only on existing blueprint values."
            )
        elif context.answered_count < context.total_questions:
            warnings.append(
                f"Only {context.answered_count} of {context.total_questions} "
                "questions are answered; the draft may be incomplete."
            )
        if self.provider.deterministic:
            warnings.append(
                "Generated by a deterministic stub provider; no AI provider is "
                "integrated yet."
            )

        return GenerationResult(
            prompt=prompt,
            draft=draft,
            provider=self.provider.name,
            model=self.provider.model,
            deterministic=self.provider.deterministic,
            warnings=warnings,
        )
