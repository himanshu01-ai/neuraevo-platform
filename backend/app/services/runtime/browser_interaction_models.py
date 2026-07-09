"""Browser interaction models (Sprint 15.8 — immutable interaction DTOs).

Provider-independent, immutable DTOs for deterministic user interactions with a
page. A :class:`BrowserInteractionRequest` names the session, the target
:class:`BrowserElement` (the *only* interaction target — never a selector or a
Playwright handle), the interaction type, and an optional value. A
:class:`BrowserInteractionResult` reports the updated session and a deterministic
status.

These carry only plain data across the boundary — no Playwright object ever
appears. They cover the interaction *layer* (click, type, scroll, focus, select);
no DOM querying, HTML parsing, JavaScript execution, downloads, uploads, or
screenshots are represented here. Strictly additive to Sprints 15.6–15.7, whose
modules are left untouched.
"""

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.browser_capability_models import BrowserSession
from app.services.runtime.browser_dom_models import BrowserElement


class InteractionType(str, Enum):
    """The allowed, deterministic browser interaction types.

    ``CLICK`` clicks an element; ``TYPE`` types a value into it; ``SCROLL``
    scrolls it into view; ``FOCUS`` focuses it; ``SELECT`` selects a dropdown
    value. Kept as a ``str`` enum so each serialises to its label. These are the
    supported vocabulary; any other value is an unsupported interaction.
    """

    CLICK = "CLICK"
    TYPE = "TYPE"
    SCROLL = "SCROLL"
    FOCUS = "FOCUS"
    SELECT = "SELECT"


class InteractionStatus(str, Enum):
    """The allowed, deterministic interaction outcomes.

    ``SUCCESS`` — the interaction was performed. ``FAILED`` — it was unsupported or
    the provider reported a failure (reported gracefully, never as a leaked
    object). Kept as a ``str`` enum so each serialises to its label.
    """

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class BrowserInteractionRequest(BaseModel):
    """Immutable request to interact with one element (no execution).

    ``frozen=True`` makes instances immutable. ``session`` is the owning
    :class:`BrowserSession`; ``element`` is the target :class:`BrowserElement`
    (the only interaction target); ``interaction_type`` is one of the
    :class:`InteractionType` labels; ``interaction_value`` is the value for
    ``TYPE``/``SELECT`` (empty otherwise); and ``interaction_metadata`` carries
    deterministic call-context descriptors. Building this DTO interacts and
    executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    session: BrowserSession
    element: BrowserElement
    interaction_type: str
    interaction_value: str = ""
    interaction_metadata: Dict[str, Any] = Field(default_factory=dict)


class BrowserInteractionResult(BaseModel):
    """Immutable result of one interaction (no execution).

    ``frozen=True`` makes instances immutable. ``updated_session`` is the
    post-interaction :class:`BrowserSession` (its id preserved; the input session
    is never mutated); ``interaction_status`` is one of the
    :class:`InteractionStatus` labels; and ``interaction_metadata`` carries
    deterministic descriptors only (never a provider object). Producing this DTO
    executes nothing further.
    """

    model_config = ConfigDict(frozen=True)

    updated_session: BrowserSession
    interaction_status: str
    interaction_metadata: Dict[str, Any] = Field(default_factory=dict)
