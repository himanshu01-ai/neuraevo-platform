"""Unit tests for the Sprint 15.6 Browser Capability foundation.

Covers the first real :class:`ExecutionCapability` end to end without touching any
real browser, network, SDK, or database: every test injects a fake
:class:`BrowserDriver`, so navigation is deterministic and offline. No Playwright
is imported.

Covers:

* the immutable :class:`BrowserSession` / :class:`BrowserNavigationRequest` /
  :class:`BrowserNavigationResult` DTOs and the :class:`NavigationStatus` enum
  (defaults, required fields, frozen immutability);
* the :class:`BrowserCapability` — deterministic session creation, successful
  navigation, invalid urls, graceful navigation failures, DOM retrieval, session
  preservation, the Sprint 14.3 ``execute`` bridge, provider independence, and
  stateless behaviour;
* the composition-root wiring (``get_browser_capability`` through the
  ExecutionCapability interface, ``BrowserCapabilityDep``); and
* regression that the Sprint 14.3 seam stays unfulfilled and the Sprint 15.1–15.5
  seams are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_browser_capability
"""

import unittest

from pydantic import BaseModel, ValidationError

from app.services.runtime.browser_capability import (
    BrowserCapability,
    BrowserDriver,
    LoadedPage,
)
from app.services.runtime.browser_capability_models import (
    BrowserNavigationRequest,
    BrowserNavigationResult,
    BrowserSession,
    NavigationStatus,
)
from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionStatus,
)


# =====================================================================
# Fake driver (NOT a real browser — deterministic, offline, no SDK)
# =====================================================================
class _FakeBrowserDriver(BrowserDriver):
    """Records calls and returns a fixed page, or raises a fixed exception."""

    def __init__(self, page: LoadedPage = None, exc: Exception = None) -> None:
        self.page = page or LoadedPage(
            title="Example Domain", content="<html><body>Example</body></html>"
        )
        self.exc = exc
        self.calls = []

    def load_page(self, url: str, timeout_ms: int) -> LoadedPage:
        self.calls.append((url, timeout_ms))
        if self.exc is not None:
            raise self.exc
        return self.page


def _capability(page=None, exc=None, timeout_ms=5000) -> BrowserCapability:
    return BrowserCapability(_FakeBrowserDriver(page=page, exc=exc), timeout_ms=timeout_ms)


def _nav(session_id="s-1", target_url="https://example.com") -> BrowserNavigationRequest:
    return BrowserNavigationRequest(session_id=session_id, target_url=target_url)


# =====================================================================
# DTOs
# =====================================================================
class BrowserDtoTests(unittest.TestCase):
    def test_navigation_status_values(self):
        self.assertEqual(NavigationStatus.SUCCESS.value, "SUCCESS")
        self.assertEqual(NavigationStatus.FAILED.value, "FAILED")

    def test_session_defaults(self):
        session = BrowserSession(session_id="s")
        self.assertIsNone(session.current_url)
        self.assertIsNone(session.page_title)
        self.assertFalse(session.page_loaded)
        self.assertEqual(session.browser_metadata, {})

    def test_session_is_immutable(self):
        session = BrowserSession(session_id="s")
        with self.assertRaises(ValidationError):
            session.session_id = "other"
        with self.assertRaises(ValidationError):
            session.page_loaded = True

    def test_navigation_request_requires_fields(self):
        with self.assertRaises(ValidationError):
            BrowserNavigationRequest(session_id="s")  # missing target_url
        with self.assertRaises(ValidationError):
            BrowserNavigationRequest(target_url="https://x.com")  # missing session_id

    def test_navigation_request_is_immutable(self):
        req = _nav()
        with self.assertRaises(ValidationError):
            req.target_url = "https://other.com"

    def test_navigation_result_is_immutable(self):
        result = BrowserNavigationResult(
            session=BrowserSession(session_id="s"), navigation_status="FAILED"
        )
        with self.assertRaises(ValidationError):
            result.navigation_status = "SUCCESS"
        with self.assertRaises(ValidationError):
            result.page_content = "<html></html>"


# =====================================================================
# Session creation / deterministic ids
# =====================================================================
class BrowserSessionCreationTests(unittest.TestCase):
    def test_create_session_is_fresh(self):
        session = _capability().create_session("user-1")
        self.assertIsNone(session.current_url)
        self.assertIsNone(session.page_title)
        self.assertFalse(session.page_loaded)
        self.assertEqual(session.browser_metadata["engine"], "chromium")

    def test_session_ids_are_deterministic(self):
        cap = _capability()
        self.assertEqual(
            cap.create_session("user-1").session_id,
            cap.create_session("user-1").session_id,
        )

    def test_different_seeds_produce_different_ids(self):
        cap = _capability()
        self.assertNotEqual(
            cap.create_session("user-1").session_id,
            cap.create_session("user-2").session_id,
        )

    def test_session_ids_stable_across_capability_instances(self):
        self.assertEqual(
            _capability().create_session("seed").session_id,
            _capability().create_session("seed").session_id,
        )

    def test_creating_a_session_does_not_touch_the_browser(self):
        driver = _FakeBrowserDriver()
        BrowserCapability(driver).create_session("user-1")
        self.assertEqual(driver.calls, [])


# =====================================================================
# Navigation
# =====================================================================
class BrowserNavigationTests(unittest.TestCase):
    # --- successful navigation ------------------------------------------
    def test_successful_navigation(self):
        result = _capability().navigate(_nav(target_url="https://example.com"))
        self.assertEqual(result.navigation_status, NavigationStatus.SUCCESS.value)
        self.assertTrue(result.session.page_loaded)
        self.assertEqual(result.session.current_url, "https://example.com")
        self.assertEqual(result.session.page_title, "Example Domain")

    def test_navigation_passes_configured_timeout_to_driver(self):
        driver = _FakeBrowserDriver()
        BrowserCapability(driver, timeout_ms=1234).navigate(_nav())
        self.assertEqual(driver.calls, [("https://example.com", 1234)])

    def test_https_and_http_are_accepted(self):
        cap = _capability()
        for url in ("http://example.com", "https://example.com/path?q=1"):
            self.assertEqual(
                cap.navigate(_nav(target_url=url)).navigation_status,
                NavigationStatus.SUCCESS.value,
            )

    # --- DOM retrieval --------------------------------------------------
    def test_dom_is_retrieved_on_success(self):
        page = LoadedPage(title="T", content="<html><body><h1>Hi</h1></body></html>")
        result = _capability(page=page).navigate(_nav())
        self.assertEqual(result.page_content, "<html><body><h1>Hi</h1></body></html>")
        self.assertEqual(
            result.navigation_metadata["content_length"], len(page.content)
        )

    # --- invalid urls ---------------------------------------------------
    def test_invalid_urls_fail_without_touching_browser(self):
        for bad in ("", "not-a-url", "ftp://x.com", "javascript:alert(1)", "example.com"):
            driver = _FakeBrowserDriver()
            result = BrowserCapability(driver).navigate(_nav(target_url=bad))
            self.assertEqual(
                result.navigation_status, NavigationStatus.FAILED.value, bad
            )
            self.assertIsNone(result.page_content)
            self.assertEqual(driver.calls, [], bad)

    # --- graceful navigation failures -----------------------------------
    def test_driver_exception_is_graceful_failure(self):
        result = _capability(exc=RuntimeError("load timeout")).navigate(_nav())
        self.assertEqual(result.navigation_status, NavigationStatus.FAILED.value)
        self.assertIsNone(result.page_content)
        self.assertFalse(result.session.page_loaded)
        self.assertIn("load timeout", result.navigation_metadata["error"])

    def test_failure_preserves_session_id(self):
        result = _capability(exc=ValueError("boom")).navigate(
            _nav(session_id="keep-me")
        )
        self.assertEqual(result.session.session_id, "keep-me")

    # --- session preservation -------------------------------------------
    def test_session_id_preserved_on_success(self):
        result = _capability().navigate(_nav(session_id="session-42"))
        self.assertEqual(result.session.session_id, "session-42")

    def test_created_session_id_threads_through_navigation(self):
        cap = _capability()
        session = cap.create_session("user-1")
        result = cap.navigate(_nav(session_id=session.session_id))
        self.assertEqual(result.session.session_id, session.session_id)

    # --- deterministic output -------------------------------------------
    def test_navigation_is_deterministic(self):
        cap = _capability()
        self.assertEqual(cap.navigate(_nav()), cap.navigate(_nav()))


# =====================================================================
# ExecutionCapability contract (Sprint 14.3 bridge)
# =====================================================================
class BrowserExecuteBridgeTests(unittest.TestCase):
    def _request(self, **inputs) -> CapabilityExecutionRequest:
        return CapabilityExecutionRequest(
            runtime_id="rt",
            execution_id="ex",
            execution_unit_id="unit-1",
            capability_name="browser",
            capability_inputs=inputs,
        )

    def test_is_execution_capability(self):
        self.assertIsInstance(_capability(), ExecutionCapability)

    def test_execute_success_maps_to_completed(self):
        result = _capability().execute(self._request(target_url="https://example.com"))
        self.assertEqual(
            result.execution_status, CapabilityExecutionStatus.COMPLETED.value
        )
        self.assertEqual(result.capability_outputs["current_url"], "https://example.com")
        self.assertEqual(result.runtime_id, "rt")
        self.assertEqual(result.execution_unit_id, "unit-1")

    def test_execute_invalid_url_maps_to_failed(self):
        result = _capability().execute(self._request(target_url="bad"))
        self.assertEqual(
            result.execution_status, CapabilityExecutionStatus.FAILED.value
        )
        self.assertIsNone(result.capability_outputs["page_content"])

    def test_execute_derives_deterministic_session_when_absent(self):
        cap = _capability()
        r1 = cap.execute(self._request(target_url="https://example.com"))
        r2 = cap.execute(self._request(target_url="https://example.com"))
        self.assertEqual(
            r1.capability_outputs["session_id"], r2.capability_outputs["session_id"]
        )

    def test_execute_outputs_are_plain_data(self):
        result = _capability().execute(self._request(target_url="https://example.com"))
        for value in result.capability_outputs.values():
            self.assertNotIsInstance(value, BaseModel)


# =====================================================================
# Provider independence / stateless behaviour
# =====================================================================
class BrowserCapabilityShapeTests(unittest.TestCase):
    def test_results_are_plain_dtos(self):
        result = _capability().navigate(_nav())
        self.assertIsInstance(result, BaseModel)
        self.assertIsInstance(result.session, BrowserSession)
        self.assertIsInstance(result.page_content, str)

    def test_capability_holds_only_driver_and_timeout(self):
        self.assertEqual(set(vars(_capability())), {"browser_driver", "timeout_ms"})

    def test_capability_has_no_disallowed_actions(self):
        for attr in ("click", "type", "fill", "upload", "download", "screenshot", "evaluate"):
            self.assertFalse(hasattr(BrowserCapability, attr))

    def test_capabilities_are_isolated(self):
        ok = _capability()
        fail = _capability(exc=RuntimeError("x"))
        self.assertEqual(ok.navigate(_nav()).navigation_status, "SUCCESS")
        self.assertEqual(fail.navigate(_nav()).navigation_status, "FAILED")


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class BrowserCapabilityDependencyInjectionTests(unittest.TestCase):
    def test_get_browser_capability_returns_execution_capability(self):
        from app.core.dependencies import get_browser_capability

        capability = get_browser_capability()
        self.assertIsInstance(capability, BrowserCapability)
        self.assertIsInstance(capability, ExecutionCapability)

    def test_wired_capability_creates_deterministic_sessions(self):
        from app.core.dependencies import get_browser_capability

        self.assertEqual(
            get_browser_capability().create_session("seed").session_id,
            get_browser_capability().create_session("seed").session_id,
        )

    def test_browser_capability_dep_is_wired(self):
        from app.core.dependencies import BrowserCapabilityDep

        self.assertIn(
            BrowserCapability, getattr(BrowserCapabilityDep, "__args__", ())
        )


# =====================================================================
# Regression — prior seams unchanged
# =====================================================================
class BrowserCapabilityRegressionTests(unittest.TestCase):
    def test_sprint_14_execution_capability_seam_still_unfulfilled(self):
        # Purely additive: the placeholder seam is left raising, unchanged.
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_sprint_15_1_registry_seam_unchanged(self):
        from app.core.dependencies import get_capability_registry

        self.assertEqual(get_capability_registry().snapshot().capability_count, 0)

    def test_sprint_15_5_validation_seam_unchanged(self):
        from app.core.dependencies import get_capability_validation_manager

        self.assertIsNotNone(get_capability_validation_manager())

    def test_sprint_11_tool_registry_seam_unchanged(self):
        from app.core.dependencies import get_tool_registry

        self.assertEqual(get_tool_registry().list_tools(), [])


if __name__ == "__main__":
    unittest.main()
