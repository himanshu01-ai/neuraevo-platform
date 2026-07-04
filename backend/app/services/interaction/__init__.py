"""Interaction package (Sprint 12.1 — Multimodal Interaction Layer foundation).

Ships ONLY the interaction framework: the provider-independent
:class:`InteractionType` / :class:`InteractionRequest` / :class:`InteractionResult`
models, the abstract :class:`InteractionProvider` contract, and the stateless
:class:`InteractionService` delegator. It is a new interface into the existing
Agent Execution Core — the Runtime, Planner, Permission, Registry, and Execution
layers stay untouched. No concrete modality handling, speech-to-text,
text-to-speech, OCR, document parsing, AI inference, streaming, HTTP client, or
SDK — those belong to later sprints.
"""

from app.services.interaction.interaction_service import InteractionService
from app.services.interaction.models import (
    InteractionRequest,
    InteractionResult,
    InteractionType,
)
from app.services.interaction.providers import InteractionProvider

__all__ = [
    "InteractionService",
    "InteractionProvider",
    "InteractionType",
    "InteractionRequest",
    "InteractionResult",
]
