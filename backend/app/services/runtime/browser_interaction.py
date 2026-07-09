"""Browser interaction collaborator (Sprint 15.8 — deterministic interactions).

Performs deterministic user interactions (click, type, scroll, focus, select) on a
:class:`BrowserElement` DTO. It is the interaction collaborator of
:class:`~app.services.runtime.browser_capability.BrowserCapability`: it consumes
only :class:`BrowserElement` DTOs (never selectors or Playwright handles) and
delegates the low-level action to the injected :class:`BrowserDriver` — the single
Playwright-facing layer — turning provider exceptions into graceful failures whose
result never carries a provider object.

It never queries the DOM, parses HTML, executes JavaScript, or exposes Playwright
objects. Deterministic and offline within this layer: it validates the request,
hands the driver a plain element descriptor, and reports an immutable result. The
input element and session are only read — never mutated. Stateless — it holds
nothing between calls. Strictly additive to Sprints 15.6–15.7, whose modules are
left untouched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from app.services.runtime.browser_capability_models import BrowserSession
from app.services.runtime.browser_dom_models import BrowserElement
from app.services.runtime.browser_interaction_models import (
    BrowserInteractionRequest,
    BrowserInteractionResult,
    InteractionStatus,
    InteractionType,
)

if TYPE_CHECKING:  # avoid a runtime import cycle with browser_capability
    from app.services.runtime.browser_capability import BrowserDriver

# Default interaction timeout (ms). Kept local so this module never imports
# browser_capability at runtime; BrowserCapability passes its own timeout.
DEFAULT_INTERACTION_TIMEOUT_MS = 30_000

_SUPPORTED_INTERACTIONS = frozenset(interaction.value for interaction in InteractionType)


class BrowserInteraction:
    """Stateless performer of deterministic interactions on a BrowserElement.

    ``interact`` validates the request, hands the injected driver a plain element
    descriptor (never a Playwright handle), and reports an immutable
    :class:`BrowserInteractionResult`. It holds no state, never queries the DOM or
    parses HTML, and never mutates the element or session — an unsupported type or
    a provider exception becomes a graceful ``FAILED`` whose metadata carries only
    plain strings.
    """

    def interact(
        self,
        request: BrowserInteractionRequest,
        driver: "BrowserDriver",
        timeout_ms: int = DEFAULT_INTERACTION_TIMEOUT_MS,
    ) -> BrowserInteractionResult:
        """Perform the requested interaction and return an immutable result.

        Rejects an unsupported ``interaction_type`` and a session with no loaded
        page deterministically, before any provider call. Otherwise it delegates
        to ``driver.perform_interaction`` with a plain element descriptor; any
        provider exception is caught and reported as a graceful ``FAILED`` (only
        the exception *type name* — never the exception/provider object — reaches
        the result). The element and session are only read, never mutated.
        """
        interaction_type = request.interaction_type
        if interaction_type not in _SUPPORTED_INTERACTIONS:
            return self._result(
                request,
                InteractionStatus.FAILED,
                error=f"unsupported interaction: {interaction_type}",
            )
        if not request.session.current_url:
            return self._result(
                request, InteractionStatus.FAILED, error="no loaded page"
            )

        try:
            driver.perform_interaction(
                request.session.current_url,
                interaction_type,
                self._describe(request.element),
                request.interaction_value,
                timeout_ms,
            )
        except Exception as exc:  # graceful — never leak the provider object
            return self._result(
                request,
                InteractionStatus.FAILED,
                error=f"interaction error: {type(exc).__name__}",
            )
        return self._result(request, InteractionStatus.SUCCESS, error=None)

    @staticmethod
    def _describe(element: BrowserElement) -> Dict[str, Any]:
        """Build a plain element descriptor for the driver (no Playwright handle)."""
        return {
            "element_id": element.element_id,
            "tag_name": element.tag_name,
            "attributes": dict(element.attributes),
        }

    @staticmethod
    def _result(
        request: BrowserInteractionRequest,
        status: InteractionStatus,
        error: Optional[str],
    ) -> BrowserInteractionResult:
        """Build the immutable result, copying the session out (never mutating it)."""
        metadata = dict(request.session.browser_metadata)
        if status is InteractionStatus.SUCCESS:
            metadata["last_interaction"] = request.interaction_type
        updated_session = BrowserSession(
            session_id=request.session.session_id,
            current_url=request.session.current_url,
            page_title=request.session.page_title,
            page_loaded=request.session.page_loaded,
            browser_metadata=metadata,
        )
        interaction_metadata: Dict[str, Any] = {
            "interaction_type": request.interaction_type,
            "element_id": request.element.element_id,
            "interaction_status": status.value,
        }
        if error is not None:
            interaction_metadata["error"] = error
        return BrowserInteractionResult(
            updated_session=updated_session,
            interaction_status=status.value,
            interaction_metadata=interaction_metadata,
        )
