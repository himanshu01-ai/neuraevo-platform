"""Prompt Builder package (Sprint 7.2).

Deterministic, read-only assembly of a :class:`RuntimeAIContext` into a
provider-agnostic :class:`PromptPackage`. No AI providers, no execution, no
persistence. Distinct from the Sprint 6C ``app.services.prompt_builder_service``
(which renders a plain-text prompt from the 6C ``AIContextResponse``).
"""

from app.services.prompt.prompt_builder_service import (
    RuntimePromptBuilderService,
)

__all__ = ["RuntimePromptBuilderService"]
