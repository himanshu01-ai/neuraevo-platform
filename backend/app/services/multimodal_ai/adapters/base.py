"""Multimodal AI adapter contract (Sprint 12.3 — abstraction only).

Defines the replaceable adapter interface that sits *beneath* the Sprint 12.2
:class:`MultimodalAIProvider` abstraction. A future concrete provider will
delegate to a concrete adapter, which in turn owns all vendor SDK / networking /
streaming (e.g. Gemini Live SDK → Google). This sprint ships ONLY the
abstraction: no concrete adapter, no SDK, no HTTP client, no websocket, no
streaming, no networking, and no model call. Concrete adapters — added in later
sprints — own all vendor-specific code behind this interface, isolated from
services, providers, repositories, models, and routers.

Nothing is wired: the provider remains abstract, the adapter remains abstract,
and no provider delegates to an adapter yet.
"""

from abc import ABC, abstractmethod

from app.services.multimodal_ai.models import (
    MultimodalAIRequest,
    MultimodalAIResponse,
)


class MultimodalAIAdapter(ABC):
    """Replaceable low-level adapter beneath a :class:`MultimodalAIProvider`.

    Concrete implementations (added in a later sprint) live behind this interface
    so providers stay vendor-agnostic. ``name`` identifies the adapter;
    ``generate_response`` turns a provider-independent
    :class:`MultimodalAIRequest` into a provider-independent
    :class:`MultimodalAIResponse`; ``health_check`` reports adapter/backend
    readiness as a plain boolean. This sprint provides only the abstract
    contract — there is no concrete adapter yet, nothing is wired, and no model,
    SDK, or network is ever touched.
    """

    name: str

    @abstractmethod
    def generate_response(
        self, request: MultimodalAIRequest
    ) -> MultimodalAIResponse:
        """Return a :class:`MultimodalAIResponse` for ``request``.

        Concrete implementations own all networking / SDK / streaming behind this
        boundary and return the response to the caller unchanged. No provider/SDK
        object crosses this boundary — only the provider-independent response.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """Return whether the adapter (and its future backend) is ready.

        Concrete implementations perform a lightweight readiness probe behind
        this boundary and return a plain boolean; no provider/SDK object crosses
        this boundary. This sprint provides only the abstract contract.
        """
