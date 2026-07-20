"""Browser capability (Sprint 15.6 — first real ExecutionCapability, foundation).

Implements the Sprint 14.3 :class:`ExecutionCapability` contract with a browser
*foundation*: create a session, navigate to a url, wait for the page to load, and
retrieve its DOM/HTML — nothing more. It never clicks, types, fills forms, uploads,
downloads, runs JavaScript, or takes screenshots; those belong to later Browser
sprints. There is no autonomous browsing: it loads only the exact url it is asked
to, one navigation at a time.

The actual browser is reached through the small, injectable :class:`BrowserDriver`
seam so the capability stays deterministic and offline in tests (a fake driver is
injected) while production uses :class:`PlaywrightBrowserDriver` (Playwright /
Chromium). Playwright is imported lazily inside the driver, so importing this
module — and constructing the capability — never requires the SDK. The capability
is stateless beyond its injected driver and timeout: it holds no live session, so
sessions are immutable DTOs threaded by the caller. Strictly additive to Sprints
15.1–15.5; it does not modify the ExecutionCapability interface, Runtime, or
Planning.
"""

import hashlib
from abc import ABC, abstractmethod
from typing import NamedTuple
from urllib.parse import urlparse

from app.services.runtime.browser_capability_models import (
    BrowserNavigationRequest,
    BrowserNavigationResult,
    BrowserSession,
    NavigationStatus,
)
from app.services.runtime.browser_dom import BrowserDOM
from app.services.runtime.browser_dom_models import (
    BrowserDOMSnapshot,
    BrowserQueryRequest,
    BrowserQueryResult,
)
from app.services.runtime.browser_interaction import BrowserInteraction
from app.services.runtime.browser_interaction_models import (
    BrowserInteractionRequest,
    BrowserInteractionResult,
    InteractionType,
)
from app.services.runtime.browser_workspace import BrowserWorkspace
from app.services.runtime.browser_workspace_models import (
    BrowserWorkspaceState,
    WorkspaceActionRequest,
    WorkspaceActionResult,
    WorkspaceActionType,
)
from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)

# Default navigation timeout (ms). Kept here rather than in settings because this
# sprint modifies only dependencies.py; it is a constructor-configurable default.
DEFAULT_NAVIGATION_TIMEOUT_MS = 30_000


class LoadedPage(NamedTuple):
    """A plain, immutable page-load result handed back by a :class:`BrowserDriver`.

    ``title`` is the loaded page's title and ``content`` is its DOM/HTML. This is
    plain data only — never a Playwright/browser object crosses the driver seam.
    """

    title: str
    content: str


class BrowserDriver(ABC):
    """Replaceable seam that loads one url and returns its title and DOM.

    Concrete drivers own all browser mechanics behind this interface so the
    capability stays deterministic and testable: production uses
    :class:`PlaywrightBrowserDriver`; tests inject a fake. A driver loads exactly
    the url it is given (no link-following) and must never expose a browser/SDK
    object across this boundary. It raises on any load failure.
    """

    @abstractmethod
    def load_page(self, url: str, timeout_ms: int) -> LoadedPage:
        """Load ``url`` (waiting for load, up to ``timeout_ms``) and return it.

        Returns a :class:`LoadedPage` with the page title and DOM/HTML. Raises an
        exception if the page cannot be loaded within the timeout; the capability
        turns that into a graceful ``FAILED`` navigation result.
        """

    def perform_interaction(
        self,
        url: str,
        action: str,
        target: dict,
        value: str,
        timeout_ms: int,
    ) -> None:
        """Perform a low-level interaction on the element described by ``target``.

        The single Playwright-facing interaction hook (Sprint 15.8). ``target`` is
        a plain element descriptor (never a Playwright handle). Concrete because
        Sprint 15.6/15.7 drivers need not implement it — the default reports the
        interaction is unsupported by raising, which the interaction layer turns
        into a graceful ``FAILED`` (the exception object never leaks). Raises on any
        provider failure; :class:`PlaywrightBrowserDriver` overrides it.
        """
        raise NotImplementedError(
            "This browser driver does not support interactions."
        )

    def perform_workspace_action(
        self,
        action: str,
        url: str,
        payload: dict,
        timeout_ms: int,
    ) -> dict:
        """Perform a driver-backed workspace action and return plain result data.

        The single Playwright-facing workspace hook (Sprint 15.9) for screenshots,
        PDF, downloads, uploads, and cookie save/load. Returns only plain data
        (paths, counts, cookie dicts) — never a Playwright object. Concrete because
        earlier drivers need not implement it; the default reports the action is
        unsupported by raising, which the workspace layer turns into a graceful
        ``FAILED`` (the exception object never leaks). Raises on any provider
        failure; :class:`PlaywrightBrowserDriver` overrides it.
        """
        raise NotImplementedError(
            "This browser driver does not support workspace actions."
        )


class BrowserDependencyError(RuntimeError):
    """Raised when the browser cannot run because its dependencies are absent.

    Distinct from an ordinary navigation failure (Sprint 18.9): a page that would
    not load is a fact about the page, while this is a fact about the deployment,
    and only one of the two is fixed by installing something. The capability
    reports it in those terms rather than passing on an ``ImportError`` that
    names a module and no remedy.
    """


def _import_playwright():
    """Import Playwright, or explain what to install.

    Kept lazy — importing this module and constructing the driver must not
    require the SDK, so a deployment that never runs a browser step needs
    nothing installed.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # the package is not installed
        raise BrowserDependencyError(
            "The Browser capability requires Playwright, which isn't installed. "
            "Install the backend requirements, then run "
            "`python -m playwright install chromium`."
        ) from exc
    return sync_playwright


def _launch_chromium(playwright, headless: bool):
    """Launch headless Chromium, naming the missing browser if that is why not.

    ``pip install playwright`` brings the client library but no browser, so the
    likeliest deployment mistake is a Chromium that was never downloaded.
    Playwright's own error says so, but says it with a filesystem path in it;
    this reports the same thing without describing the host. Any other launch
    failure is left alone — it is not a dependency problem and should not be
    dressed as one.
    """
    try:
        return playwright.chromium.launch(headless=headless)
    except Exception as exc:
        if not _chromium_present(playwright):
            raise BrowserDependencyError(
                "The Browser capability needs a Chromium build, which isn't "
                "installed. Run `python -m playwright install chromium`."
            ) from exc
        raise


def _chromium_present(playwright) -> bool:
    """Whether Playwright's Chromium is actually on disk."""
    try:
        import pathlib

        executable = playwright.chromium.executable_path
        return bool(executable) and pathlib.Path(executable).exists()
    except Exception:
        return False


class PlaywrightBrowserDriver(BrowserDriver):
    """Production :class:`BrowserDriver` backed by Playwright / Chromium.

    Launches a headless Chromium, opens one page, navigates to the url waiting for
    the ``load`` event, and returns the page title and full DOM/HTML — never a
    Playwright object. Each call is fully self-contained (launch → load → close),
    so the driver holds no state. Playwright is imported lazily inside
    :meth:`load_page`, so importing this module and constructing the driver never
    require the SDK. It only reads the page: no clicking, typing, forms, uploads,
    downloads, JavaScript, or screenshots.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = DEFAULT_NAVIGATION_TIMEOUT_MS,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms

    def load_page(self, url: str, timeout_ms: int) -> LoadedPage:
        """Load ``url`` in headless Chromium and return its title and DOM."""
        sync_playwright = _import_playwright()  # lazy: SDK optional

        with sync_playwright() as playwright:
            browser = _launch_chromium(playwright, self.headless)
            try:
                page = browser.new_page()
                page.goto(url, timeout=timeout_ms, wait_until="load")
                return LoadedPage(title=page.title(), content=page.content())
            finally:
                browser.close()

    def perform_interaction(
        self,
        url: str,
        action: str,
        target: dict,
        value: str,
        timeout_ms: int,
    ) -> None:
        """Load ``url`` and perform ``action`` on the described element (Chromium).

        Locates the element from the plain ``target`` descriptor (by id when
        present, else by tag) and performs exactly the one action — click, fill,
        focus, scroll-into-view, or select-option. No JavaScript, screenshots,
        uploads, or downloads. Playwright is imported lazily; the browser is always
        closed. Provider failures propagate for the interaction layer to catch.
        """
        sync_playwright = _import_playwright()  # lazy: SDK optional

        with sync_playwright() as playwright:
            browser = _launch_chromium(playwright, self.headless)
            try:
                page = browser.new_page()
                page.goto(url, timeout=timeout_ms, wait_until="load")
                locator = self._locate(page, target)
                if action == InteractionType.CLICK.value:
                    locator.click(timeout=timeout_ms)
                elif action == InteractionType.TYPE.value:
                    locator.fill(value, timeout=timeout_ms)
                elif action == InteractionType.FOCUS.value:
                    locator.focus(timeout=timeout_ms)
                elif action == InteractionType.SCROLL.value:
                    locator.scroll_into_view_if_needed(timeout=timeout_ms)
                elif action == InteractionType.SELECT.value:
                    locator.select_option(value, timeout=timeout_ms)
                else:
                    raise ValueError(f"unsupported interaction: {action}")
            finally:
                browser.close()

    @staticmethod
    def _locate(page, target: dict):
        """Locate the element from a plain descriptor (by id, else by tag)."""
        attributes = target.get("attributes", {})
        element_id = attributes.get("id")
        if element_id:
            return page.locator(f"#{element_id}")
        return page.locator(target.get("tag_name", "*")).first

    def perform_workspace_action(
        self,
        action: str,
        url: str,
        payload: dict,
        timeout_ms: int,
    ) -> dict:
        """Load ``url`` and perform the workspace ``action`` in Chromium.

        Captures a screenshot or PDF to a path, saves or loads cookies, or records
        a download/upload coordination descriptor — returning only plain data
        (paths, counts, cookie dicts), never a Playwright object. No JavaScript
        execution or network interception. Playwright is imported lazily; the
        browser is always closed. Provider failures propagate for the workspace
        layer to catch.
        """
        sync_playwright = _import_playwright()  # lazy: SDK optional

        with sync_playwright() as playwright:
            browser = _launch_chromium(playwright, self.headless)
            try:
                page = browser.new_page()
                if url:
                    page.goto(url, timeout=timeout_ms, wait_until="load")
                if action == WorkspaceActionType.SCREENSHOT.value:
                    path = payload.get("path", "screenshot.png")
                    page.screenshot(path=path, timeout=timeout_ms)
                    return {"path": path}
                if action == WorkspaceActionType.PDF.value:
                    path = payload.get("path", "page.pdf")
                    page.pdf(path=path)
                    return {"path": path}
                if action == WorkspaceActionType.SAVE_COOKIES.value:
                    cookies = page.context.cookies()
                    return {"cookies": cookies, "count": len(cookies)}
                if action == WorkspaceActionType.LOAD_COOKIES.value:
                    cookies = payload.get("cookies", [])
                    page.context.add_cookies(cookies)
                    return {"loaded": len(cookies)}
                if action == WorkspaceActionType.DOWNLOAD.value:
                    return {"coordinated": True, "url": payload.get("url")}
                if action == WorkspaceActionType.UPLOAD.value:
                    return {"coordinated": True, "path": payload.get("path")}
                raise ValueError(f"unsupported workspace action: {action}")
            finally:
                browser.close()


class BrowserCapability(ExecutionCapability):
    """Browser foundation capability: sessions, navigation, page load, DOM.

    Stateless beyond the injected :class:`BrowserDriver`, the default timeout, and
    the optional DOM/interaction collaborators — it holds no live browser or
    session, so :class:`BrowserSession` DTOs are immutable and threaded by the
    caller. ``create_session`` mints a deterministic session; ``navigate`` loads
    one url through the driver and reports the updated session plus DOM;
    ``capture_dom``/``query_dom`` delegate DOM discovery to :class:`BrowserDOM`
    (Sprint 15.7); ``interact`` delegates click/type/scroll/focus/select on a
    :class:`BrowserElement` to :class:`BrowserInteraction` (Sprint 15.8);
    ``create_workspace``/``workspace_action`` delegate tab, screenshot, PDF,
    download, upload, and cookie management to :class:`BrowserWorkspace` (Sprint
    15.9); and ``execute`` bridges the Sprint 14.3 runtime contract to a single
    navigation. It never executes arbitrary JavaScript, intercepts network
    traffic, or browses autonomously.
    """

    def __init__(
        self,
        browser_driver: BrowserDriver,
        timeout_ms: int = DEFAULT_NAVIGATION_TIMEOUT_MS,
        browser_dom: BrowserDOM | None = None,
        browser_interaction: BrowserInteraction | None = None,
        browser_workspace: BrowserWorkspace | None = None,
    ) -> None:
        self.browser_driver = browser_driver
        self.timeout_ms = timeout_ms
        # Sprint 15.7 DOM, Sprint 15.8 interaction, and Sprint 15.9 workspace
        # collaborators. Each is stored only when injected so the Sprint 15.6
        # constructor contract (driver + timeout only) is preserved; the
        # DOM/interaction/workspace methods fall back to a default stateless
        # collaborator when none is supplied.
        if browser_dom is not None:
            self.browser_dom = browser_dom
        if browser_interaction is not None:
            self.browser_interaction = browser_interaction
        if browser_workspace is not None:
            self.browser_workspace = browser_workspace

    # --- browser-native API ---------------------------------------------
    def create_session(
        self, seed: str, session_metadata: dict | None = None
    ) -> BrowserSession:
        """Return a fresh, deterministic :class:`BrowserSession` for ``seed``.

        The session id is derived deterministically from ``seed`` (same seed →
        same id) with no clock, uuid, or counter, so creation is repeatable and
        stateless. The new session has no loaded page yet. Launching happens later,
        on navigation — creating a session touches no browser.
        """
        metadata = {"engine": "chromium", "session_seed": seed}
        if session_metadata:
            metadata.update(session_metadata)
        return BrowserSession(
            session_id=self._derive_session_id(seed),
            current_url=None,
            page_title=None,
            page_loaded=False,
            browser_metadata=metadata,
        )

    def navigate(
        self, request: BrowserNavigationRequest
    ) -> BrowserNavigationResult:
        """Navigate the session to ``request.target_url`` and return the result.

        Rejects an invalid url deterministically (only ``http``/``https`` with a
        host) before touching the browser. Otherwise it loads the page through the
        driver, waiting for load; on success it returns a ``SUCCESS`` result with
        the updated session and retrieved DOM, and on any driver failure a graceful
        ``FAILED`` result. The session id is always preserved.
        """
        if not self._is_valid_url(request.target_url):
            return self._failed(request, "invalid target url")

        try:
            page = self.browser_driver.load_page(
                request.target_url, self.timeout_ms
            )
        except BrowserDependencyError as exc:
            # Nothing was attempted: the browser isn't installed. Its own message
            # says what to install, so it is reported as written rather than
            # wrapped as though a page had failed to load.
            return self._failed(request, str(exc))
        except Exception as exc:  # graceful navigation failure — never propagate
            return self._failed(request, f"navigation error: {exc}")

        session = BrowserSession(
            session_id=request.session_id,
            current_url=request.target_url,
            page_title=page.title,
            page_loaded=True,
            browser_metadata={"engine": "chromium"},
        )
        return BrowserNavigationResult(
            session=session,
            page_content=page.content,
            navigation_status=NavigationStatus.SUCCESS.value,
            navigation_metadata={
                "session_id": request.session_id,
                "target_url": request.target_url,
                "navigation_status": NavigationStatus.SUCCESS.value,
                "content_length": len(page.content),
            },
        )

    # --- ExecutionCapability contract (Sprint 14.3) ---------------------
    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        """Bridge the runtime contract to a single browser navigation.

        Reads ``session_id`` (defaulting to a deterministic id derived from the
        execution unit) and ``target_url`` from ``capability_inputs``, navigates
        once, and maps the outcome to a :class:`CapabilityExecutionResult`
        (``SUCCESS`` → ``COMPLETED``, ``FAILED`` → ``FAILED``) with plain outputs.
        It executes exactly one navigation — no autonomous browsing.
        """
        inputs = request.capability_inputs
        session_id = inputs.get("session_id") or self._derive_session_id(
            request.execution_unit_id
        )
        navigation = self.navigate(
            BrowserNavigationRequest(
                session_id=session_id,
                target_url=inputs.get("target_url", ""),
            )
        )
        status = (
            CapabilityExecutionStatus.COMPLETED
            if navigation.navigation_status == NavigationStatus.SUCCESS.value
            else CapabilityExecutionStatus.FAILED
        )
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=status.value,
            capability_outputs={
                "session_id": navigation.session.session_id,
                "current_url": navigation.session.current_url,
                "page_title": navigation.session.page_title,
                "page_loaded": navigation.session.page_loaded,
                "navigation_status": navigation.navigation_status,
                "page_content": navigation.page_content,
                # Sprint 18.9: a failed navigation carried its reason only in
                # metadata, so a failed browser step showed a person no reason at
                # all. The other capabilities report theirs in outputs; this one
                # now does too, and stays absent on success.
                **(
                    {"error": navigation.navigation_metadata["error"]}
                    if "error" in navigation.navigation_metadata
                    else {}
                ),
            },
            execution_metadata={
                "session_id": navigation.session.session_id,
                "target_url": inputs.get("target_url", ""),
                "navigation_status": navigation.navigation_status,
            },
        )

    # --- DOM discovery (Sprint 15.7 — delegates to BrowserDOM) ----------
    def capture_dom(
        self, session: BrowserSession, page_content: str
    ) -> BrowserDOMSnapshot:
        """Build an immutable DOM snapshot from already-retrieved page HTML.

        Delegates parsing to the injected :class:`BrowserDOM`, handing it plain
        HTML (extracted from Playwright *inside* this capability) so no browser
        object escapes. Reads only — nothing is clicked, typed, or executed.
        """
        return self._dom().build_snapshot(session, page_content)

    def query_dom(
        self, snapshot: BrowserDOMSnapshot, request: BrowserQueryRequest
    ) -> BrowserQueryResult:
        """Query a DOM snapshot by selector, delegating to :class:`BrowserDOM`.

        The snapshot supplies the elements and the request the exact selector;
        matching preserves document order and returns a fresh collection. Reads
        only — it never mutates the snapshot or the DOM.
        """
        return self._dom().query(snapshot, request)

    def _dom(self) -> BrowserDOM:
        """Return the injected :class:`BrowserDOM`, or a default stateless one."""
        dom = getattr(self, "browser_dom", None)
        return dom if dom is not None else BrowserDOM()

    # --- interactions (Sprint 15.8 — delegates to BrowserInteraction) ---
    def interact(
        self, request: BrowserInteractionRequest
    ) -> BrowserInteractionResult:
        """Perform an interaction on a BrowserElement, via :class:`BrowserInteraction`.

        Delegates to the injected interaction collaborator, handing it this
        capability's own :class:`BrowserDriver` (the single Playwright-facing layer)
        and timeout. The interaction operates only on the request's
        :class:`BrowserElement`; provider failures come back as a graceful
        ``FAILED`` result with no provider object.
        """
        return self._interaction().interact(
            request, self.browser_driver, self.timeout_ms
        )

    def _interaction(self) -> BrowserInteraction:
        """Return the injected :class:`BrowserInteraction`, or a default one."""
        interaction = getattr(self, "browser_interaction", None)
        return interaction if interaction is not None else BrowserInteraction()

    # --- workspace (Sprint 15.9 — delegates to BrowserWorkspace) --------
    def create_workspace(self, session: BrowserSession) -> BrowserWorkspaceState:
        """Create a fresh workspace for ``session`` via :class:`BrowserWorkspace`."""
        return self._workspace().create_workspace(session)

    def workspace_action(
        self,
        workspace: BrowserWorkspaceState,
        request: WorkspaceActionRequest,
    ) -> WorkspaceActionResult:
        """Apply a workspace action, delegating to :class:`BrowserWorkspace`.

        Tab actions transform the workspace deterministically; driver actions run
        through this capability's own :class:`BrowserDriver` (the single
        Playwright-facing layer) and come back as a graceful ``FAILED`` on any
        provider failure, with no provider object.
        """
        return self._workspace().execute(
            workspace, request, self.browser_driver, self.timeout_ms
        )

    def _workspace(self) -> BrowserWorkspace:
        """Return the injected :class:`BrowserWorkspace`, or a default one."""
        workspace = getattr(self, "browser_workspace", None)
        return workspace if workspace is not None else BrowserWorkspace()

    # --- deterministic helpers ------------------------------------------
    @staticmethod
    def _derive_session_id(seed: str) -> str:
        """Derive a stable session id from ``seed`` (deterministic, no clock/uuid)."""
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return f"browser-{digest[:16]}"

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Return whether ``url`` is a well-formed ``http``/``https`` url."""
        try:
            parsed = urlparse(url)
        except (ValueError, TypeError):
            return False
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)

    def _failed(
        self, request: BrowserNavigationRequest, error: str
    ) -> BrowserNavigationResult:
        """Build a graceful ``FAILED`` result that preserves the session id."""
        session = BrowserSession(
            session_id=request.session_id,
            current_url=None,
            page_title=None,
            page_loaded=False,
            browser_metadata={"engine": "chromium", "error": error},
        )
        return BrowserNavigationResult(
            session=session,
            page_content=None,
            navigation_status=NavigationStatus.FAILED.value,
            navigation_metadata={
                "session_id": request.session_id,
                "target_url": request.target_url,
                "navigation_status": NavigationStatus.FAILED.value,
                "error": error,
            },
        )
