"""Browser capability models (Sprint 15.6 — immutable browser-session DTOs).

Provider-independent, immutable DTOs for the first real execution capability: a
browser session, a navigation request, and a navigation result. A
:class:`BrowserSession` is a plain snapshot of one browser session's state (id,
current url, page title, load flag); a :class:`BrowserNavigationRequest` names the
session and the target url to load; a :class:`BrowserNavigationResult` reports the
updated session, the retrieved DOM/HTML, and a deterministic status.

These carry only plain data across the boundary — never a Playwright/browser
object. They cover browser *foundation* only (sessions, navigation, page loading,
DOM retrieval): no clicking, typing, form filling, uploads, downloads, JavaScript
execution, or screenshots are represented here; those belong to later Browser
sprints. Strictly additive to Sprints 15.1–15.5, whose modules are left untouched.
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class NavigationStatus(str, Enum):
    """The allowed, deterministic browser-navigation statuses.

    ``SUCCESS`` — the page loaded and its DOM was retrieved. ``FAILED`` — the
    target url was invalid or the load could not complete. Kept as a ``str`` enum
    so each serialises to its label. These are outcome labels only.
    """

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class BrowserSession(BaseModel):
    """Immutable snapshot of one browser session's state (no execution).

    ``frozen=True`` makes instances immutable — navigation produces a *new*
    session rather than mutating one. ``session_id`` is the deterministic session
    identifier; ``current_url`` is the last successfully loaded url (``None`` for a
    fresh or failed session); ``page_title`` is the loaded page's title (``None``
    when nothing loaded); ``page_loaded`` marks whether a page is currently loaded;
    and ``browser_metadata`` carries deterministic descriptors (never a browser/SDK
    object). Building this DTO launches and executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    session_id: str
    current_url: Optional[str] = None
    page_title: Optional[str] = None
    page_loaded: bool = False
    browser_metadata: Dict[str, Any] = Field(default_factory=dict)


class BrowserNavigationRequest(BaseModel):
    """Immutable request to navigate a session to a url (no execution).

    ``frozen=True`` makes instances immutable. ``session_id`` names the session to
    navigate; ``target_url`` is the url to load; and ``navigation_metadata``
    carries deterministic call-context descriptors and defaults to empty. Building
    this DTO navigates and executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    session_id: str
    target_url: str
    navigation_metadata: Dict[str, Any] = Field(default_factory=dict)


class BrowserNavigationResult(BaseModel):
    """Immutable result of navigating a session to a url (no execution).

    ``frozen=True`` makes instances immutable. ``session`` is the updated
    :class:`BrowserSession` (its id preserved); ``page_content`` is the retrieved
    DOM/HTML on success and ``None`` on failure (never a browser/SDK object);
    ``navigation_status`` is one of the :class:`NavigationStatus` labels; and
    ``navigation_metadata`` carries deterministic descriptors only. Producing this
    DTO executes nothing further.
    """

    model_config = ConfigDict(frozen=True)

    session: BrowserSession
    page_content: Optional[str] = None
    navigation_status: str
    navigation_metadata: Dict[str, Any] = Field(default_factory=dict)
