"""Gemini adapter — first concrete MultimodalAIAdapter (Sprint 12.5).

Owns ALL Google GenAI SDK communication for the multimodal AI stack. This is
the ONLY module in the application permitted to import the official
``google-genai`` SDK (``from google import genai``); the provider, service,
interaction, runtime, and API layers stay SDK-agnostic and never learn the SDK
exists.

The adapter itself depends only on :class:`GenAIClientProtocol` — a structural
interface describing the two SDK capabilities it actually uses — never on the
concrete SDK class. The composition root reads configuration, builds the real
client through :func:`create_genai_client` (the single place the concrete SDK
class is instantiated), and injects it. The adapter never constructs clients,
never reads environment variables, and holds no globals or singletons.

The model name is never hardcoded here: the provider supplies it per call via
``request.metadata[MODEL_METADATA_KEY]`` (sourced from
``ProviderConfig.default_model``), the only provider→adapter channel available
through the frozen :class:`MultimodalAIAdapter` contract.
"""

from typing import Any, Protocol, runtime_checkable

from app.services.multimodal_ai.adapters.base import MultimodalAIAdapter
from app.services.multimodal_ai.models import (
    MultimodalAIRequest,
    MultimodalAIResponse,
)

# Request-metadata key through which the provider hands the adapter the model
# to use (from ProviderConfig.default_model). The adapter never invents or
# defaults a model name.
MODEL_METADATA_KEY = "model"


@runtime_checkable
class GenAIModelsProtocol(Protocol):
    """The only model-surface capabilities the adapter requires of the SDK."""

    def generate_content(self, *, model: str, contents: Any) -> Any:
        """Generate content for ``contents`` using ``model``."""
        ...

    def list(self) -> Any:
        """List available models (lightweight, token-free readiness probe)."""
        ...


@runtime_checkable
class GenAIClientProtocol(Protocol):
    """Structural view of the SDK client: only a ``models`` surface.

    ``google.genai.Client`` satisfies this protocol, but so does any test
    double — the adapter depends on this interface, not the concrete SDK class,
    so SDK upgrades or replacement stay localized to this module and the
    composition root.
    """

    models: GenAIModelsProtocol


def create_genai_client(api_key: str) -> GenAIClientProtocol:
    """Build the concrete google-genai client (SDK confined to this module).

    Called only by the composition root, which owns reading/validating the API
    key; this factory exists so ``core/dependencies.py`` never imports the SDK.
    The import lives inside the function so the application (and test suite)
    imports cleanly even when the SDK is not installed — mirroring the lazy
    Qdrant SDK import — while the client itself is still constructed eagerly,
    per composition, never lazily inside the adapter.
    """
    try:
        from google import genai  # the single sanctioned SDK import
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is not installed; add 'google-genai' to "
            "requirements.txt to use the Gemini adapter."
        ) from exc

    return genai.Client(api_key=api_key)


class GeminiAdapter(MultimodalAIAdapter):
    """Concrete adapter that fulfills the Sprint 12.3 contract via Gemini.

    Stateless beyond the single injected client (which is only ever received
    through the constructor — never instantiated, cached, or replaced here).
    ``generate_response`` makes exactly one SDK call and maps the SDK response
    to the provider-independent DTO; ``health_check`` performs the lightest
    token-free readiness probe. No retries, timeouts, logging, caching, prompt
    engineering, parsing beyond text extraction, business logic, or
    orchestration.
    """

    name = "gemini"

    def __init__(self, client: GenAIClientProtocol) -> None:
        self.client = client

    def generate_response(
        self, request: MultimodalAIRequest
    ) -> MultimodalAIResponse:
        """Call Gemini exactly once and return the mapped DTO unchanged.

        Builds the SDK request from the already-normalized content, using the
        model supplied by the provider in ``request.metadata`` — never a
        hardcoded name. SDK exceptions propagate exactly as received: no
        retries, wrapping, or swallowing. The request DTO is never mutated.
        """
        # TODO(sprint-12.x): the model currently rides in the generic
        # ``request.metadata["model"]`` entry. A future sprint may replace this
        # loosely-typed channel with a dedicated request/config object once tool
        # execution, multimodal hints, tracing, and execution context become
        # part of the framework — carrying model + generation params + trace ids
        # as a typed contract rather than free-form metadata. Documentation only;
        # no behavioral change here.
        model = request.metadata.get(MODEL_METADATA_KEY)
        if not isinstance(model, str) or not model.strip():
            raise ValueError(
                "MultimodalAIRequest.metadata['model'] must carry the model "
                "name (from ProviderConfig.default_model); the Gemini adapter "
                "never hardcodes or defaults a model."
            )

        sdk_response = self.client.models.generate_content(
            model=model, contents=request.normalized_content
        )

        return MultimodalAIResponse(
            response_text=sdk_response.text or "", metadata={}
        )

    def health_check(self) -> bool:
        """Return whether the injected client is usable; never raises.

        Performs the lightest readiness verification the SDK supports — listing
        models — which consumes no generation tokens and never performs a full
        generation request. Any SDK/client failure yields ``False``; no
        exception escapes.
        """
        try:
            self.client.models.list()
        except Exception:
            return False
        return True
