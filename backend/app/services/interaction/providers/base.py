"""Interaction provider contract (Sprint 12.1 — abstraction only).

Defines the replaceable interface that future modality processors will implement
(text / voice / image / document normalization). This sprint ships ONLY the
abstraction: no concrete modality handling, no speech-to-text, no text-to-speech,
no OCR, no document parsing, no AI inference, no streaming, no HTTP client, and
no SDK. Concrete providers — added in later sprints — own all modality-specific
logic behind this interface, isolated from services, repositories, models, and
routers.
"""

from abc import ABC, abstractmethod

from app.services.interaction.models import (
    InteractionRequest,
    InteractionResult,
)


class InteractionProvider(ABC):
    """Replaceable strategy that normalizes one interaction into a result.

    Concrete implementations (added in a later sprint) live behind this
    interface so the rest of the system stays modality-agnostic. ``name``
    identifies the provider; ``process_interaction`` turns a provider-independent
    :class:`InteractionRequest` into a provider-independent
    :class:`InteractionResult`. This sprint provides only the abstract contract —
    there is no concrete provider yet, and nothing is recognized, synthesized,
    parsed, or executed.
    """

    name: str

    @abstractmethod
    def process_interaction(
        self, request: InteractionRequest
    ) -> InteractionResult:
        """Return an :class:`InteractionResult` for ``request``.

        Concrete implementations normalize the request's modality-specific
        content and return the result to the caller unchanged; they perform no
        planning, permission checks, tool execution, or runtime coordination. No
        provider/SDK object crosses this boundary.
        """
