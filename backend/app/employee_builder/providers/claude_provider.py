"""Claude (Anthropic) blueprint generation provider.

Implements :class:`BlueprintGenerationProvider` by calling the Anthropic
Messages API, parsing and validating the JSON response, and mapping it onto a
:class:`GeneratedBlueprintDraft`. All Claude-specific logic is contained here —
no Anthropic code appears in routers, repositories, models, or schemas.
"""

import json
from typing import Optional

import anthropic

from app.employee_builder.blueprint import (
    BlueprintGenerationError,
    BlueprintGenerationProvider,
    BlueprintGenerationTimeoutError,
)
from app.schemas.blueprint_generation import (
    BlueprintGenerationContext,
    GeneratedBlueprintDraft,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum characters per generated field (validation rule).
_MAX_FIELD_LENGTH = 10000

# The JSON keys Claude is instructed to return, mapped onto the blueprint draft
# fields (the unchanged Sprint 4A response contract). Keys not listed here are
# treated as unknown and ignored; ``decision_style`` and ``leadership_style``
# are requested for a richer profile but have no draft slot in the current
# schema, so they are intentionally unmapped.
_CLAUDE_TO_DRAFT_FIELD: dict[str, str] = {
    "vision": "vision",
    "communication_style": "communication_style",
    "goals": "goals",
    "strengths": "personality_traits",
    "development_areas": "constraints",
    "working_preferences": "preferences",
}

_JSON_INSTRUCTION = (
    "Return ONLY a single JSON object — no prose, no markdown, no code fences. "
    "Use exactly these keys, each mapping to a concise string "
    "(use an empty string if there is insufficient information):\n"
    "vision, goals, communication_style, decision_style, strengths, "
    "development_areas, working_preferences, leadership_style."
)

_SYSTEM_PROMPT = (
    "You generate a structured profile (blueprint) for an AI employee from "
    "interview data. You respond with valid JSON only and never include any "
    "text outside the JSON object."
)


class ClaudeBlueprintProvider(BlueprintGenerationProvider):
    """Generates a blueprint draft using Anthropic's Claude models."""

    name = "anthropic"
    deterministic = False

    def __init__(
        self,
        *,
        api_key: Optional[str],
        model: str,
        timeout: float = 30.0,
        max_tokens: int = 4096,
        client: Optional["anthropic.Anthropic"] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        # ``client`` allows injecting a stub in tests; otherwise it is built
        # lazily so importing this module never requires a configured key.
        self._client = client

    # --- Client ----------------------------------------------------------

    def _get_client(self) -> "anthropic.Anthropic":
        if self._client is None:
            self._client = anthropic.Anthropic(
                api_key=self.api_key, timeout=self.timeout
            )
        return self._client

    # --- Provider interface ---------------------------------------------

    def generate(
        self, prompt: str, context: BlueprintGenerationContext
    ) -> GeneratedBlueprintDraft:
        """Call Claude with the prompt and return a validated draft.

        Raises :class:`BlueprintGenerationTimeoutError` on timeout and
        :class:`BlueprintGenerationError` on any other failure (API error,
        empty response, invalid JSON, or failed validation).
        """
        try:
            client = self._get_client()
        except Exception as exc:  # missing key / misconfiguration
            logger.warning("Claude client initialization failed: %s", exc)
            raise BlueprintGenerationError("Claude client unavailable") from exc

        user_content = f"{prompt}\n\n{_JSON_INSTRUCTION}"
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
        except anthropic.APITimeoutError as exc:
            logger.warning("Claude request timed out for employee %s", context.employee_id)
            raise BlueprintGenerationTimeoutError(
                "Blueprint generation timed out"
            ) from exc
        except anthropic.APIError as exc:
            logger.warning("Claude API error: %s", exc)
            raise BlueprintGenerationError("Claude API request failed") from exc
        except Exception as exc:  # defensive — never leak internals
            logger.warning("Unexpected Claude failure: %s", exc)
            raise BlueprintGenerationError("Blueprint generation failed") from exc

        text = self._extract_text(response)
        data = self._parse_json(text)
        return self._to_draft(data)

    # --- Response handling ----------------------------------------------

    @staticmethod
    def _extract_text(response) -> str:
        """Concatenate text blocks from the response, rejecting empties."""
        parts: list[str] = []
        for block in getattr(response, "content", None) or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", "") or "")
        text = "".join(parts).strip()
        if not text:
            raise BlueprintGenerationError("Claude returned an empty response")
        return text

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove a surrounding ```json ... ``` fence if Claude added one."""
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        return stripped

    def _parse_json(self, text: str) -> dict:
        try:
            data = json.loads(self._strip_code_fences(text))
        except json.JSONDecodeError as exc:
            raise BlueprintGenerationError("Claude returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise BlueprintGenerationError(
                "Claude returned a non-object JSON value"
            )
        return data

    @staticmethod
    def _normalize(value: object) -> Optional[str]:
        """Trim whitespace, convert empty to ``None``, enforce max length."""
        if value is None:
            return None
        text = value if isinstance(value, str) else str(value)
        trimmed = text.strip()
        if trimmed == "":
            return None
        if len(trimmed) > _MAX_FIELD_LENGTH:
            raise BlueprintGenerationError(
                "A generated field exceeds the maximum length"
            )
        return trimmed

    def _to_draft(self, data: dict) -> GeneratedBlueprintDraft:
        """Map known Claude fields onto the draft; ignore unknown fields."""
        mapped: dict[str, Optional[str]] = {}
        for claude_key, draft_field in _CLAUDE_TO_DRAFT_FIELD.items():
            if claude_key in data:
                mapped[draft_field] = self._normalize(data[claude_key])
        return GeneratedBlueprintDraft(**mapped)
