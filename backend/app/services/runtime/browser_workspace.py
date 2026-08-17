"""Browser workspace collaborator (Sprint 15.9 — deterministic workspace mgmt).

Manages a persistent browser workspace: tabs, the unique active tab, cookies, and
driver-backed operations (screenshot, PDF, download, upload, cookie save/load). It
is the workspace collaborator of
:class:`~app.services.runtime.browser_capability.BrowserCapability`: tab actions are
pure deterministic transformations of immutable :class:`BrowserWorkspaceState`
DTOs, while I/O actions communicate *only* with the injected
:class:`BrowserDriver` — the single Playwright-facing layer — turning provider
exceptions into graceful failures whose result never carries a provider object.

It never executes JavaScript, never inspects network traffic, and never exposes a
provider object. Deterministic and offline within this layer: tabs are created in
order with deterministic ids, the active tab is always unique, and the input
workspace and session are only read — never mutated. Stateless — it holds nothing
between calls. Strictly additive to Sprints 15.6–15.8, whose modules are left
untouched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.services.runtime.browser_capability_models import BrowserSession
from app.services.runtime.browser_workspace_models import (
    BrowserTab,
    BrowserWorkspaceState,
    WorkspaceActionRequest,
    WorkspaceActionResult,
    WorkspaceActionStatus,
    WorkspaceActionType,
)

if TYPE_CHECKING:  # avoid a runtime import cycle with browser_capability
    from app.services.runtime.browser_capability import BrowserDriver

# Default workspace-action timeout (ms). Kept local so this module never imports
# browser_capability at runtime; BrowserCapability passes its own timeout.
DEFAULT_WORKSPACE_TIMEOUT_MS = 30_000

# Actions that go through the driver (the only Playwright-facing layer).
_DRIVER_ACTIONS = frozenset(
    {
        WorkspaceActionType.SCREENSHOT.value,
        WorkspaceActionType.PDF.value,
        WorkspaceActionType.DOWNLOAD.value,
        WorkspaceActionType.UPLOAD.value,
        WorkspaceActionType.SAVE_COOKIES.value,
        WorkspaceActionType.LOAD_COOKIES.value,
    }
)


class BrowserWorkspace:
    """Stateless manager of a persistent browser workspace.

    ``create_workspace`` mints an empty workspace; ``execute`` applies one action —
    tab actions transform the workspace deterministically, driver actions delegate
    to the injected :class:`BrowserDriver`. It holds no state, never executes
    JavaScript or inspects network traffic, and never mutates the input workspace
    or session — an unsupported action, a missing tab, or a provider exception
    becomes a graceful ``FAILED`` whose metadata carries only plain strings.
    """

    def create_workspace(self, session: BrowserSession) -> BrowserWorkspaceState:
        """Return a fresh, empty :class:`BrowserWorkspaceState` for ``session``.

        The workspace starts with no tabs, no active tab, cookies enabled, and a
        deterministic tab counter. Creating it opens no browser.
        """
        return BrowserWorkspaceState(
            session=session,
            tabs=[],
            active_tab_id=None,
            cookies_enabled=True,
            workspace_metadata={"next_tab_index": 0},
        )

    def execute(
        self,
        workspace: BrowserWorkspaceState,
        request: WorkspaceActionRequest,
        driver: "BrowserDriver",
        timeout_ms: int = DEFAULT_WORKSPACE_TIMEOUT_MS,
    ) -> WorkspaceActionResult:
        """Apply ``request`` to ``workspace`` and return an immutable result.

        Tab actions (``NEW_TAB``/``CLOSE_TAB``/``SWITCH_TAB``) transform the
        workspace deterministically without any provider call; driver actions
        delegate to ``driver.perform_workspace_action`` and catch provider
        exceptions gracefully (only the exception *type name* — never the
        exception/provider object — reaches the result). An unsupported action or
        a missing tab is a graceful ``FAILED`` that returns the workspace unchanged.
        """
        action = request.action_type
        if action == WorkspaceActionType.NEW_TAB.value:
            return self._new_tab(workspace, request)
        if action == WorkspaceActionType.CLOSE_TAB.value:
            return self._close_tab(workspace, request)
        if action == WorkspaceActionType.SWITCH_TAB.value:
            return self._switch_tab(workspace, request)
        if action in _DRIVER_ACTIONS:
            return self._driver_action(workspace, request, driver, timeout_ms)
        return self._failed(
            workspace, request, f"unsupported workspace action: {action}"
        )

    # --- tab actions (pure, deterministic) ------------------------------
    def _new_tab(
        self, workspace: BrowserWorkspaceState, request: WorkspaceActionRequest
    ) -> WorkspaceActionResult:
        metadata = dict(workspace.workspace_metadata)
        index = metadata.get("next_tab_index", 0)
        tab_id = f"tab-{index}"
        metadata["next_tab_index"] = index + 1
        metadata["last_action"] = WorkspaceActionType.NEW_TAB.value
        new_tab = BrowserTab(
            tab_id=tab_id,
            url=request.action_payload.get("url"),
            title=request.action_payload.get("title"),
            is_active=True,
            workspace_metadata={"created_index": index},
        )
        tabs = self._with_active(list(workspace.tabs) + [new_tab], tab_id)
        return self._success(
            self._rebuild(workspace, tabs, tab_id, metadata), request
        )

    def _close_tab(
        self, workspace: BrowserWorkspaceState, request: WorkspaceActionRequest
    ) -> WorkspaceActionResult:
        tab_id = request.action_payload.get("tab_id")
        if not self._has_tab(workspace, tab_id):
            return self._failed(workspace, request, f"tab not found: {tab_id}")
        remaining = [tab for tab in workspace.tabs if tab.tab_id != tab_id]
        if not remaining:
            active_id: Optional[str] = None
        elif workspace.active_tab_id == tab_id:
            active_id = remaining[-1].tab_id  # activate the most recent remaining
        else:
            active_id = workspace.active_tab_id
        metadata = {
            **workspace.workspace_metadata,
            "last_action": WorkspaceActionType.CLOSE_TAB.value,
        }
        tabs = self._with_active(remaining, active_id)
        return self._success(
            self._rebuild(workspace, tabs, active_id, metadata), request
        )

    def _switch_tab(
        self, workspace: BrowserWorkspaceState, request: WorkspaceActionRequest
    ) -> WorkspaceActionResult:
        tab_id = request.action_payload.get("tab_id")
        if not self._has_tab(workspace, tab_id):
            return self._failed(workspace, request, f"tab not found: {tab_id}")
        metadata = {
            **workspace.workspace_metadata,
            "last_action": WorkspaceActionType.SWITCH_TAB.value,
        }
        tabs = self._with_active(workspace.tabs, tab_id)
        return self._success(
            self._rebuild(workspace, tabs, tab_id, metadata), request
        )

    # --- driver actions (delegated, graceful) ---------------------------
    def _driver_action(
        self,
        workspace: BrowserWorkspaceState,
        request: WorkspaceActionRequest,
        driver: "BrowserDriver",
        timeout_ms: int,
    ) -> WorkspaceActionResult:
        try:
            result = driver.perform_workspace_action(
                request.action_type,
                self._active_url(workspace),
                request.action_payload,
                timeout_ms,
            )
        except Exception as exc:  # graceful — never leak the provider object
            return self._failed(
                workspace, request, f"workspace error: {type(exc).__name__}"
            )
        metadata = {
            **workspace.workspace_metadata,
            "last_action": request.action_type,
        }
        updated = self._rebuild(
            workspace, list(workspace.tabs), workspace.active_tab_id, metadata
        )
        return self._success(updated, request, extra={"result": result})

    # --- deterministic helpers ------------------------------------------
    @staticmethod
    def _with_active(tabs: List[BrowserTab], active_id: Optional[str]) -> List[BrowserTab]:
        """Rebuild ``tabs`` so exactly the ``active_id`` tab is active (or none)."""
        return [
            BrowserTab(
                tab_id=tab.tab_id,
                url=tab.url,
                title=tab.title,
                is_active=(tab.tab_id == active_id),
                workspace_metadata=tab.workspace_metadata,
            )
            for tab in tabs
        ]

    @staticmethod
    def _has_tab(workspace: BrowserWorkspaceState, tab_id: Optional[str]) -> bool:
        return any(tab.tab_id == tab_id for tab in workspace.tabs)

    @staticmethod
    def _active_url(workspace: BrowserWorkspaceState) -> Optional[str]:
        for tab in workspace.tabs:
            if tab.tab_id == workspace.active_tab_id and tab.url:
                return tab.url
        return workspace.session.current_url

    @staticmethod
    def _rebuild(
        workspace: BrowserWorkspaceState,
        tabs: List[BrowserTab],
        active_id: Optional[str],
        metadata: Dict[str, Any],
    ) -> BrowserWorkspaceState:
        """Build a new workspace preserving the (immutable) session."""
        return BrowserWorkspaceState(
            session=workspace.session,
            tabs=tabs,
            active_tab_id=active_id,
            cookies_enabled=workspace.cookies_enabled,
            workspace_metadata=metadata,
        )

    @staticmethod
    def _success(
        workspace: BrowserWorkspaceState,
        request: WorkspaceActionRequest,
        extra: Optional[Dict[str, Any]] = None,
    ) -> WorkspaceActionResult:
        metadata: Dict[str, Any] = {
            "action_type": request.action_type,
            "action_status": WorkspaceActionStatus.SUCCESS.value,
        }
        if extra:
            metadata.update(extra)
        return WorkspaceActionResult(
            updated_workspace=workspace,
            action_status=WorkspaceActionStatus.SUCCESS.value,
            action_metadata=metadata,
        )

    @staticmethod
    def _failed(
        workspace: BrowserWorkspaceState,
        request: WorkspaceActionRequest,
        error: str,
    ) -> WorkspaceActionResult:
        """Return the workspace unchanged with a graceful FAILED result."""
        return WorkspaceActionResult(
            updated_workspace=workspace,
            action_status=WorkspaceActionStatus.FAILED.value,
            action_metadata={
                "action_type": request.action_type,
                "action_status": WorkspaceActionStatus.FAILED.value,
                "error": error,
            },
        )
