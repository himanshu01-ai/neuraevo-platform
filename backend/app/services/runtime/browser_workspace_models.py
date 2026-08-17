"""Browser workspace models (Sprint 15.9 — immutable workspace-state DTOs).

Provider-independent, immutable DTOs for persistent browser workspace management:
tabs, an overall workspace state, and a workspace-action request/result. A
:class:`BrowserTab` is a plain description of one tab; a
:class:`BrowserWorkspaceState` pairs a :class:`BrowserSession` with its tabs (in
creation order), the unique active tab, and a cookies flag; a
:class:`WorkspaceActionRequest` names a workspace action; a
:class:`WorkspaceActionResult` reports the updated workspace.

These carry only plain data across the boundary — no Playwright object ever
appears. They cover workspace management (tabs, screenshots, PDF, downloads,
uploads, cookies, session persistence); no arbitrary JavaScript execution or
network interception is represented. Strictly additive to Sprints 15.6–15.8, whose
modules are left untouched.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.browser_capability_models import BrowserSession


class WorkspaceActionType(str, Enum):
    """The allowed, deterministic workspace action types.

    Tab actions: ``NEW_TAB``, ``CLOSE_TAB``, ``SWITCH_TAB``. Driver actions:
    ``SCREENSHOT``, ``PDF``, ``DOWNLOAD``, ``UPLOAD``, ``SAVE_COOKIES``,
    ``LOAD_COOKIES``. Kept as a ``str`` enum so each serialises to its label. Any
    other value is an unsupported action.
    """

    NEW_TAB = "NEW_TAB"
    CLOSE_TAB = "CLOSE_TAB"
    SWITCH_TAB = "SWITCH_TAB"
    SCREENSHOT = "SCREENSHOT"
    PDF = "PDF"
    DOWNLOAD = "DOWNLOAD"
    UPLOAD = "UPLOAD"
    SAVE_COOKIES = "SAVE_COOKIES"
    LOAD_COOKIES = "LOAD_COOKIES"


class WorkspaceActionStatus(str, Enum):
    """The allowed, deterministic workspace action outcomes.

    ``SUCCESS`` — the action was applied. ``FAILED`` — it was unsupported, invalid,
    or the provider reported a failure (reported gracefully, never as a leaked
    object). Kept as a ``str`` enum so each serialises to its label.
    """

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class BrowserTab(BaseModel):
    """Immutable description of one browser tab (no execution).

    ``frozen=True`` makes instances immutable. ``tab_id`` is the deterministic tab
    identifier; ``url``/``title`` are the tab's current page (``None`` for a blank
    tab); ``is_active`` marks the single active tab; and ``workspace_metadata``
    carries deterministic descriptors (never a browser/SDK object). Building this
    DTO opens and executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    tab_id: str
    url: Optional[str] = None
    title: Optional[str] = None
    is_active: bool = False
    workspace_metadata: Dict[str, Any] = Field(default_factory=dict)


class BrowserWorkspaceState(BaseModel):
    """Immutable snapshot of a browser workspace (no execution).

    ``frozen=True`` makes instances immutable — every action produces a *new*
    workspace. ``session`` is the owning :class:`BrowserSession` (never mutated);
    ``tabs`` are the :class:`BrowserTab` records in creation order — a fresh list,
    never a live browser reference; ``active_tab_id`` names the unique active tab
    (``None`` when there are no tabs); ``cookies_enabled`` flags cookie support;
    and ``workspace_metadata`` carries deterministic descriptors only. Producing
    this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    session: BrowserSession
    tabs: List[BrowserTab] = Field(default_factory=list)
    active_tab_id: Optional[str] = None
    cookies_enabled: bool = True
    workspace_metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkspaceActionRequest(BaseModel):
    """Immutable request to apply one workspace action (no execution).

    ``frozen=True`` makes instances immutable. ``session`` is the owning
    :class:`BrowserSession`; ``action_type`` is one of the
    :class:`WorkspaceActionType` labels; ``action_payload`` carries the action's
    plain inputs (e.g. a ``tab_id``, ``url``, or file path); and
    ``action_metadata`` carries deterministic call-context descriptors. Building
    this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    session: BrowserSession
    action_type: str
    action_payload: Dict[str, Any] = Field(default_factory=dict)
    action_metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkspaceActionResult(BaseModel):
    """Immutable result of one workspace action (no execution).

    ``frozen=True`` makes instances immutable. ``updated_workspace`` is the
    post-action :class:`BrowserWorkspaceState` (the input workspace and session are
    never mutated; on failure it is returned unchanged); ``action_status`` is one
    of the :class:`WorkspaceActionStatus` labels; and ``action_metadata`` carries
    deterministic descriptors only (never a provider object). Producing this DTO
    executes nothing further.
    """

    model_config = ConfigDict(frozen=True)

    updated_workspace: BrowserWorkspaceState
    action_status: str
    action_metadata: Dict[str, Any] = Field(default_factory=dict)
