"""Unit tests for the Sprint 15.9 Browser Workspace layer.

Covers deterministic browser workspace management end to end without any real
browser, network, SDK, or Playwright import — tab actions are pure state
transformations and driver actions use an injected fake :class:`BrowserDriver`
whose ``perform_workspace_action`` returns a plain dict (or raises).

Covers:

* the immutable :class:`BrowserTab` / :class:`BrowserWorkspaceState` /
  :class:`WorkspaceActionRequest` / :class:`WorkspaceActionResult` DTOs and the
  :class:`WorkspaceActionType` / :class:`WorkspaceActionStatus` enums (defaults,
  frozen immutability);
* :class:`BrowserWorkspace` — new/close/switch tab, screenshot, PDF, download,
  upload, cookie save/load, tab ordering, active-tab uniqueness, graceful
  failures, no Playwright leakage, provider independence, and stateless
  behaviour;
* the :class:`BrowserCapability` delegation and the composition-root wiring
  (``get_browser_workspace`` / ``BrowserWorkspaceDep``, injected into the
  capability); and
* regression that the Sprint 15.6–15.8 browser behaviour and prior seams are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_browser_workspace
"""

import sys
import unittest

from pydantic import BaseModel, ValidationError

from app.services.runtime.browser_capability import (
    BrowserCapability,
    BrowserDriver,
    LoadedPage,
)
from app.services.runtime.browser_capability_models import BrowserSession
from app.services.runtime.browser_workspace import BrowserWorkspace
from app.services.runtime.browser_workspace_models import (
    BrowserTab,
    BrowserWorkspaceState,
    WorkspaceActionRequest,
    WorkspaceActionResult,
    WorkspaceActionStatus,
    WorkspaceActionType,
)


# =====================================================================
# Fake driver (records workspace actions or raises — never a real browser)
# =====================================================================
class _FakeWorkspaceDriver(BrowserDriver):
    def __init__(self, result=None, exc: Exception = None) -> None:
        self.result = result if result is not None else {"ok": True}
        self.exc = exc
        self.calls = []

    def load_page(self, url, timeout_ms):
        return LoadedPage(title="T", content="<html></html>")

    def perform_workspace_action(self, action, url, payload, timeout_ms):
        self.calls.append({"action": action, "url": url, "payload": payload})
        if self.exc is not None:
            raise self.exc
        return self.result


def _session(**overrides) -> BrowserSession:
    data = dict(session_id="s-1", current_url="https://example.com", page_loaded=True)
    data.update(overrides)
    return BrowserSession(**data)


def _request(action_type, session=None, **payload) -> WorkspaceActionRequest:
    return WorkspaceActionRequest(
        session=session or _session(),
        action_type=action_type,
        action_payload=payload,
    )


def _apply(actions, driver=None, session=None):
    """Apply a sequence of (action_type, payload) to a fresh workspace."""
    workspace_manager = BrowserWorkspace()
    driver = driver or _FakeWorkspaceDriver()
    session = session or _session()
    workspace = workspace_manager.create_workspace(session)
    result = None
    for action_type, payload in actions:
        result = workspace_manager.execute(
            workspace,
            WorkspaceActionRequest(
                session=session, action_type=action_type, action_payload=payload
            ),
            driver,
        )
        workspace = result.updated_workspace
    return workspace, result


def _ids(workspace):
    return [tab.tab_id for tab in workspace.tabs]


def _active_count(workspace):
    return sum(1 for tab in workspace.tabs if tab.is_active)


# =====================================================================
# DTOs
# =====================================================================
class WorkspaceDtoTests(unittest.TestCase):
    def test_action_type_values(self):
        self.assertEqual(
            [t.value for t in WorkspaceActionType],
            [
                "NEW_TAB", "CLOSE_TAB", "SWITCH_TAB", "SCREENSHOT", "PDF",
                "DOWNLOAD", "UPLOAD", "SAVE_COOKIES", "LOAD_COOKIES",
            ],
        )

    def test_status_values(self):
        self.assertEqual(WorkspaceActionStatus.SUCCESS.value, "SUCCESS")
        self.assertEqual(WorkspaceActionStatus.FAILED.value, "FAILED")

    def test_tab_defaults(self):
        tab = BrowserTab(tab_id="tab-0")
        self.assertIsNone(tab.url)
        self.assertIsNone(tab.title)
        self.assertFalse(tab.is_active)
        self.assertEqual(tab.workspace_metadata, {})

    def test_tab_is_immutable(self):
        tab = BrowserTab(tab_id="tab-0")
        with self.assertRaises(ValidationError):
            tab.is_active = True

    def test_workspace_state_defaults(self):
        state = BrowserWorkspaceState(session=_session())
        self.assertEqual(state.tabs, [])
        self.assertIsNone(state.active_tab_id)
        self.assertTrue(state.cookies_enabled)

    def test_workspace_state_is_immutable(self):
        state = BrowserWorkspaceState(session=_session())
        with self.assertRaises(ValidationError):
            state.active_tab_id = "tab-0"
        with self.assertRaises(ValidationError):
            state.tabs = []

    def test_action_result_is_immutable(self):
        _, result = _apply([("NEW_TAB", {})])
        with self.assertRaises(ValidationError):
            result.action_status = "FAILED"
        with self.assertRaises(ValidationError):
            result.action_metadata = {}


# =====================================================================
# Tab management
# =====================================================================
class WorkspaceTabTests(unittest.TestCase):
    def test_create_workspace_is_empty(self):
        workspace = BrowserWorkspace().create_workspace(_session())
        self.assertEqual(workspace.tabs, [])
        self.assertIsNone(workspace.active_tab_id)
        self.assertTrue(workspace.cookies_enabled)

    def test_new_tab(self):
        workspace, result = _apply([("NEW_TAB", {"url": "https://a.com"})])
        self.assertEqual(result.action_status, "SUCCESS")
        self.assertEqual(_ids(workspace), ["tab-0"])
        self.assertEqual(workspace.tabs[0].url, "https://a.com")
        self.assertEqual(workspace.active_tab_id, "tab-0")
        self.assertTrue(workspace.tabs[0].is_active)

    def test_new_tabs_follow_creation_order(self):
        workspace, _ = _apply([("NEW_TAB", {}), ("NEW_TAB", {}), ("NEW_TAB", {})])
        self.assertEqual(_ids(workspace), ["tab-0", "tab-1", "tab-2"])

    def test_new_tab_makes_the_new_tab_active_uniquely(self):
        workspace, _ = _apply([("NEW_TAB", {}), ("NEW_TAB", {}), ("NEW_TAB", {})])
        self.assertEqual(workspace.active_tab_id, "tab-2")
        self.assertEqual(_active_count(workspace), 1)

    def test_switch_tab(self):
        workspace, result = _apply(
            [("NEW_TAB", {}), ("NEW_TAB", {}), ("SWITCH_TAB", {"tab_id": "tab-0"})]
        )
        self.assertEqual(result.action_status, "SUCCESS")
        self.assertEqual(workspace.active_tab_id, "tab-0")
        self.assertEqual(_active_count(workspace), 1)
        self.assertTrue(workspace.tabs[0].is_active)
        self.assertFalse(workspace.tabs[1].is_active)

    def test_close_tab(self):
        workspace, result = _apply(
            [("NEW_TAB", {}), ("NEW_TAB", {}), ("CLOSE_TAB", {"tab_id": "tab-0"})]
        )
        self.assertEqual(result.action_status, "SUCCESS")
        self.assertEqual(_ids(workspace), ["tab-1"])

    def test_closing_active_tab_activates_another(self):
        # tab-2 active; close it -> a remaining tab becomes the unique active.
        workspace, _ = _apply(
            [("NEW_TAB", {}), ("NEW_TAB", {}), ("NEW_TAB", {}), ("CLOSE_TAB", {"tab_id": "tab-2"})]
        )
        self.assertEqual(_ids(workspace), ["tab-0", "tab-1"])
        self.assertEqual(workspace.active_tab_id, "tab-1")
        self.assertEqual(_active_count(workspace), 1)

    def test_closing_inactive_tab_keeps_active(self):
        workspace, _ = _apply(
            [("NEW_TAB", {}), ("NEW_TAB", {}), ("CLOSE_TAB", {"tab_id": "tab-0"})]
        )
        # tab-1 was active and stays active; still unique.
        self.assertEqual(workspace.active_tab_id, "tab-1")
        self.assertEqual(_active_count(workspace), 1)

    def test_closing_last_tab_leaves_no_active(self):
        workspace, _ = _apply([("NEW_TAB", {}), ("CLOSE_TAB", {"tab_id": "tab-0"})])
        self.assertEqual(workspace.tabs, [])
        self.assertIsNone(workspace.active_tab_id)

    # --- graceful failures ----------------------------------------------
    def test_close_missing_tab_fails_gracefully(self):
        workspace, result = _apply([("NEW_TAB", {}), ("CLOSE_TAB", {"tab_id": "nope"})])
        self.assertEqual(result.action_status, "FAILED")
        self.assertIn("tab not found", result.action_metadata["error"])
        self.assertEqual(_ids(workspace), ["tab-0"])  # unchanged

    def test_switch_missing_tab_fails_gracefully(self):
        _, result = _apply([("NEW_TAB", {}), ("SWITCH_TAB", {"tab_id": "nope"})])
        self.assertEqual(result.action_status, "FAILED")

    def test_unsupported_action_fails_gracefully(self):
        driver = _FakeWorkspaceDriver()
        _, result = _apply([("FLY", {})], driver=driver)
        self.assertEqual(result.action_status, "FAILED")
        self.assertIn("unsupported", result.action_metadata["error"])
        self.assertEqual(driver.calls, [])


# =====================================================================
# Driver actions (screenshot / pdf / download / upload / cookies)
# =====================================================================
class WorkspaceDriverActionTests(unittest.TestCase):
    def _run(self, action, result=None, exc=None, **payload):
        driver = _FakeWorkspaceDriver(result=result, exc=exc)
        manager = BrowserWorkspace()
        workspace = manager.create_workspace(_session())
        return driver, manager.execute(workspace, _request(action, **payload), driver)

    def test_screenshot(self):
        driver, result = self._run("SCREENSHOT", result={"path": "/tmp/s.png"}, path="/tmp/s.png")
        self.assertEqual(result.action_status, "SUCCESS")
        self.assertEqual(result.action_metadata["result"], {"path": "/tmp/s.png"})
        self.assertEqual(driver.calls[0]["action"], "SCREENSHOT")
        self.assertEqual(
            result.updated_workspace.workspace_metadata["last_action"], "SCREENSHOT"
        )

    def test_pdf(self):
        _, result = self._run("PDF", result={"path": "/tmp/p.pdf"})
        self.assertEqual(result.action_status, "SUCCESS")

    def test_download_coordination(self):
        driver, result = self._run("DOWNLOAD", result={"coordinated": True}, url="https://f/x.zip")
        self.assertEqual(result.action_status, "SUCCESS")
        self.assertEqual(driver.calls[0]["payload"]["url"], "https://f/x.zip")

    def test_upload_coordination(self):
        _, result = self._run("UPLOAD", result={"coordinated": True}, path="/tmp/f.txt")
        self.assertEqual(result.action_status, "SUCCESS")

    def test_save_cookies(self):
        _, result = self._run("SAVE_COOKIES", result={"count": 3})
        self.assertEqual(result.action_status, "SUCCESS")
        self.assertEqual(result.action_metadata["result"]["count"], 3)

    def test_load_cookies(self):
        _, result = self._run("LOAD_COOKIES", result={"loaded": 2}, cookies=[{"n": "a"}, {"n": "b"}])
        self.assertEqual(result.action_status, "SUCCESS")

    def test_driver_exception_is_graceful_no_leak(self):
        class _Provider(Exception):
            pass

        _, result = self._run("SCREENSHOT", exc=_Provider("secret"))
        self.assertEqual(result.action_status, "FAILED")
        self.assertEqual(result.action_metadata["error"], "workspace error: _Provider")
        self.assertNotIn("secret", str(result.action_metadata))


# =====================================================================
# Determinism / immutability / provider independence / no leakage
# =====================================================================
class WorkspaceShapeTests(unittest.TestCase):
    def test_session_is_never_mutated(self):
        session = _session()
        before = session.model_dump()
        workspace, _ = _apply([("NEW_TAB", {})], session=session)
        self.assertEqual(session.model_dump(), before)
        self.assertEqual(workspace.session.session_id, "s-1")

    def test_repeated_action_is_deterministic(self):
        manager = BrowserWorkspace()
        base = manager.create_workspace(_session())
        driver = _FakeWorkspaceDriver()
        req = _request("NEW_TAB", url="https://a.com")
        self.assertEqual(
            manager.execute(base, req, driver),
            manager.execute(base, req, driver),
        )

    def test_results_are_plain_dtos(self):
        workspace, result = _apply([("NEW_TAB", {})])
        self.assertIsInstance(result, WorkspaceActionResult)
        self.assertIsInstance(workspace, BrowserWorkspaceState)
        for tab in workspace.tabs:
            self.assertIsInstance(tab, BrowserTab)

    def test_no_playwright_leakage(self):
        _apply([("NEW_TAB", {})])
        self.assertNotIn("playwright", sys.modules)

    def test_workspace_holds_no_state(self):
        self.assertEqual(vars(BrowserWorkspace()), {})

    def test_tabs_list_is_fresh_each_action(self):
        manager = BrowserWorkspace()
        base = manager.create_workspace(_session())
        driver = _FakeWorkspaceDriver()
        r1 = manager.execute(base, _request("NEW_TAB"), driver)
        r2 = manager.execute(base, _request("NEW_TAB"), driver)
        self.assertIsNot(r1.updated_workspace.tabs, r2.updated_workspace.tabs)


# =====================================================================
# BrowserCapability delegation
# =====================================================================
class BrowserCapabilityWorkspaceDelegationTests(unittest.TestCase):
    def test_capability_creates_and_acts_on_workspace(self):
        cap = BrowserCapability(
            _FakeWorkspaceDriver(), browser_workspace=BrowserWorkspace()
        )
        workspace = cap.create_workspace(_session())
        result = cap.workspace_action(workspace, _request("NEW_TAB", url="https://a.com"))
        self.assertEqual(result.action_status, "SUCCESS")
        self.assertEqual(_ids(result.updated_workspace), ["tab-0"])

    def test_capability_uses_its_own_driver_for_io(self):
        driver = _FakeWorkspaceDriver(exc=ValueError("x"))
        cap = BrowserCapability(driver)
        workspace = cap.create_workspace(_session())
        result = cap.workspace_action(workspace, _request("SCREENSHOT"))
        self.assertEqual(result.action_status, "FAILED")

    def test_workspace_works_without_injected_collaborator(self):
        cap = BrowserCapability(_FakeWorkspaceDriver())
        workspace = cap.create_workspace(_session())
        result = cap.workspace_action(workspace, _request("NEW_TAB"))
        self.assertEqual(result.action_status, "SUCCESS")

    def test_capability_constructor_contract_preserved(self):
        cap = BrowserCapability(_FakeWorkspaceDriver(), timeout_ms=1000)
        self.assertEqual(set(vars(cap)), {"browser_driver", "timeout_ms"})


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class BrowserWorkspaceDependencyInjectionTests(unittest.TestCase):
    def test_get_browser_workspace_returns_workspace(self):
        from app.core.dependencies import get_browser_workspace

        self.assertIsInstance(get_browser_workspace(), BrowserWorkspace)

    def test_browser_workspace_dep_is_wired(self):
        from app.core.dependencies import BrowserWorkspaceDep

        self.assertIn(BrowserWorkspace, getattr(BrowserWorkspaceDep, "__args__", ()))

    def test_browser_capability_has_workspace_injected(self):
        from app.core.dependencies import get_browser_capability

        cap = get_browser_capability()
        workspace = cap.create_workspace(_session())
        # A pure tab action needs no real browser and proves the wiring.
        result = cap.workspace_action(workspace, _request("NEW_TAB"))
        self.assertEqual(result.action_status, "SUCCESS")


# =====================================================================
# Regression — Sprint 15.6–15.8 and prior seams unchanged
# =====================================================================
class BrowserWorkspaceRegressionTests(unittest.TestCase):
    def test_sprint_15_6_navigation_unchanged(self):
        from app.services.runtime.browser_capability_models import (
            BrowserNavigationRequest,
            NavigationStatus,
        )

        cap = BrowserCapability(_FakeWorkspaceDriver())
        result = cap.navigate(
            BrowserNavigationRequest(session_id="s", target_url="https://example.com")
        )
        self.assertEqual(result.navigation_status, NavigationStatus.SUCCESS.value)

    def test_sprint_15_7_dom_unchanged(self):
        cap = BrowserCapability(_FakeWorkspaceDriver())
        snap = cap.capture_dom(_session(), "<div><a>x</a></div>")
        self.assertEqual([e.tag_name for e in snap.elements], ["div", "a"])

    def test_sprint_15_8_interaction_unchanged(self):
        from app.services.runtime.browser_dom_models import BrowserElement
        from app.services.runtime.browser_interaction_models import (
            BrowserInteractionRequest,
        )

        cap = BrowserCapability(_FakeWorkspaceDriver())
        result = cap.interact(
            BrowserInteractionRequest(
                session=_session(),
                element=BrowserElement(element_id="e", tag_name="button"),
                interaction_type="HOVER",
            )
        )
        self.assertEqual(result.interaction_status, "FAILED")

    def test_sprint_14_execution_capability_seam_unchanged(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_sprint_15_1_registry_seam_unchanged(self):
        from app.core.dependencies import get_capability_registry

        self.assertEqual(get_capability_registry().snapshot().capability_count, 0)


if __name__ == "__main__":
    unittest.main()
