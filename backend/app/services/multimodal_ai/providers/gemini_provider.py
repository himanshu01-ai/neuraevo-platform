"""Gemini provider — first concrete MultimodalAIProvider (Sprint 12.4).

Business-layer implementation of :class:`MultimodalAIProvider`. It delegates
generation to an injected :class:`MultimodalAIAdapter` and returns the adapter's
:class:`MultimodalAIResponse` unchanged. It is NOT the SDK adapter: it performs
no networking, no Google/SDK imports, no model call, and no streaming.

An immutable :class:`ProviderConfig` is injected alongside the adapter and stored
as part of the provider's architecture. It is not consumed for generation yet;
future sprints will drive model selection, sampling, and safety from it — so no
model name is ever hardcoded inside business logic.
"""

from typing import Annotated, Any, Dict

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.multimodal_ai.adapters import MultimodalAIAdapter
from app.services.multimodal_ai.models import (
    MultimodalAIRequest,
    MultimodalAIResponse,
)
from app.services.multimodal_ai.providers.base import MultimodalAIProvider

# Trimmed, required, non-empty identifier (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class ProviderConfig(BaseModel):
    """Immutable provider-layer configuration injected into a provider.

    Declarative settings that belong to the provider layer. ``provider_name``
    identifies the provider; ``default_model`` is the model the provider will use
    (business logic reads the model name ONLY from here — never a literal);
    ``temperature`` and ``max_output_tokens`` bound sampling/output;
    ``safety_profile`` names a safety configuration; ``metadata`` carries extra
    plain context. Not consumed for generation yet — it becomes part of the
    provider architecture so future sprints can configure behavior without
    touching business logic. ``frozen=True`` makes instances immutable.
    """

    model_config = ConfigDict(frozen=True)

    provider_name: _NonEmptyStr
    default_model: _NonEmptyStr
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=1024, gt=0)
    safety_profile: str = "standard"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GeminiProvider(MultimodalAIProvider):
    """First concrete :class:`MultimodalAIProvider` — business layer only.

    Receives its collaborators exclusively through the constructor: a
    :class:`MultimodalAIAdapter` (never instantiated internally) and an immutable
    :class:`ProviderConfig`. Its sole runtime behavior is to delegate a request
    to the adapter exactly once and return the adapter's response unchanged.

    It owns NO retry, timeout, SDK, networking, streaming, OCR, prompt building,
    runtime, planner, permission, memory, or execution concern. Stateless beyond
    its two injected collaborators.
    """

    def __init__(
        self, adapter: MultimodalAIAdapter, config: ProviderConfig
    ) -> None:
        self.adapter = adapter
        self.config = config

    @property
    def name(self) -> str:
        """Provider identity, taken from config (no literal in business logic)."""
        return self.config.provider_name

    @property
    def model(self) -> str:
        """The model the provider would use, chosen ONLY from config.

        No model literal ever appears in business logic; the name comes from
        ``ProviderConfig.default_model`` so future sprints switch models via
        configuration alone.
        """
        return self.config.default_model

    def generate_response(
        self, request: MultimodalAIRequest
    ) -> MultimodalAIResponse:
        """Delegate to the adapter exactly once; return its response unchanged.

        Business layer only: no retry, timeout, SDK, networking, streaming,
        prompt building, or orchestration. The request is forwarded to the
        injected adapter untouched and the adapter's response is returned as-is.
        Adapter exceptions propagate unchanged.
        """
        return self.adapter.generate_response(request)
