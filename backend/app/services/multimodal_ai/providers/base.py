"""Multimodal AI provider contract (Sprint 12.2 — abstraction only).

Defines the replaceable interface that future multimodal AI backends will
implement (e.g. Gemini / OpenAI / Anthropic). This sprint ships ONLY the
abstraction: no concrete provider, no SDK, no HTTP client, no websocket, no
streaming, no networking, no prompt building, and no model call. Concrete
providers — added in later sprints — own all vendor-specific code behind this
interface, isolated from services, repositories, models, and routers.
"""

from abc import ABC, abstractmethod

from app.services.multimodal_ai.models import (
    MultimodalAIRequest,
    MultimodalAIResponse,
)


class MultimodalAIProvider(ABC):
    """Replaceable strategy that turns a normalized request into a response.

    Concrete implementations (added in a later sprint) live behind this
    interface so the rest of the system stays provider-agnostic. ``name``
    identifies the provider; ``generate_response`` turns a provider-independent
    :class:`MultimodalAIRequest` into a provider-independent
    :class:`MultimodalAIResponse`. This sprint provides only the abstract
    contract — there is no concrete provider yet, and no model is ever called.
    """

    name: str

    @abstractmethod
    def generate_response(
        self, request: MultimodalAIRequest
    ) -> MultimodalAIResponse:
        """Return a :class:`MultimodalAIResponse` for ``request``.

        Concrete implementations perform the generation and return the response
        to the caller unchanged; they own all networking/SDK/streaming behind
        this boundary and perform no prompt building, orchestration, or runtime
        coordination. No provider/SDK object crosses this boundary.
        """
