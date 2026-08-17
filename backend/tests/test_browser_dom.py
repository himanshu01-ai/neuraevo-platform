"""Unit tests for the Sprint 15.7 Browser DOM & Element layer.

Covers deterministic, provider-independent DOM discovery end to end without any
real browser, network, SDK, or Playwright import — :class:`BrowserDOM` parses plain
HTML strings with the standard library.

Covers:

* the immutable :class:`BrowserElement` / :class:`BrowserDOMSnapshot` /
  :class:`BrowserQueryRequest` / :class:`BrowserQueryResult` DTOs (defaults,
  frozen immutability);
* :class:`BrowserDOM` — empty DOM, DOM extraction, deterministic ids, selector
  matching (tag / ``#id`` / ``.class`` / empty), document-order preservation,
  fresh immutable collections, no Playwright leakage, and stateless behaviour;
* the :class:`BrowserCapability` delegation and the composition-root wiring
  (``get_browser_dom`` / ``BrowserDOMDep``, ``BrowserDOM`` injected into the
  capability); and
* regression that the Sprint 15.6 browser behaviour and prior seams are unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_browser_dom
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
from app.services.runtime.browser_dom import BrowserDOM
from app.services.runtime.browser_dom_models import (
    BrowserDOMSnapshot,
    BrowserElement,
    BrowserQueryRequest,
    BrowserQueryResult,
)

_HTML = (
    "<html><head><title>Doc</title></head><body>"
    '<div id="main" class="container box">'
    "<h1>Title</h1>"
    '<a href="https://example.com" class="link">Home</a>'
    '<a href="https://example.com/about" class="link">About</a>'
    '<input type="text" name="q">'
    "<span hidden>secret</span>"
    "</div></body></html>"
)
# Document order: html, head, title, body, div, h1, a, a, input, span
_EXPECTED_TAGS = ["html", "head", "title", "body", "div", "h1", "a", "a", "input", "span"]


def _session(session_id="s-1") -> BrowserSession:
    return BrowserSession(session_id=session_id)


def _snapshot(html=_HTML) -> BrowserDOMSnapshot:
    return BrowserDOM().build_snapshot(_session(), html)


def _query(snapshot, selector):
    return BrowserDOM().query(
        snapshot, BrowserQueryRequest(session=snapshot.session, selector=selector)
    )


def _ids(result):
    return [e.element_id for e in result.matched_elements]


class _FakeBrowserDriver(BrowserDriver):
    def load_page(self, url, timeout_ms):
        return LoadedPage(title="T", content=_HTML)


# =====================================================================
# DTOs
# =====================================================================
class BrowserDomDtoTests(unittest.TestCase):
    def test_element_defaults(self):
        element = BrowserElement(element_id="e", tag_name="div")
        self.assertEqual(element.text, "")
        self.assertEqual(element.attributes, {})
        self.assertTrue(element.is_visible)
        self.assertEqual(element.browser_metadata, {})

    def test_element_is_immutable(self):
        element = BrowserElement(element_id="e", tag_name="div")
        with self.assertRaises(ValidationError):
            element.tag_name = "span"
        with self.assertRaises(ValidationError):
            element.attributes = {"x": 1}

    def test_snapshot_is_immutable(self):
        snap = _snapshot()
        with self.assertRaises(ValidationError):
            snap.elements = []
        with self.assertRaises(ValidationError):
            snap.dom_metadata = {}

    def test_query_request_defaults_and_immutable(self):
        req = BrowserQueryRequest(session=_session())
        self.assertEqual(req.selector, "")
        with self.assertRaises(ValidationError):
            req.selector = "a"

    def test_query_result_is_immutable(self):
        result = _query(_snapshot(), "a")
        with self.assertRaises(ValidationError):
            result.query_count = 0
        with self.assertRaises(ValidationError):
            result.matched_elements = []


# =====================================================================
# DOM extraction
# =====================================================================
class BrowserDomExtractionTests(unittest.TestCase):
    def test_empty_dom(self):
        for html in ("", "   ", "\n\t"):
            snap = _snapshot(html)
            self.assertEqual(snap.elements, [])
            self.assertEqual(snap.dom_metadata["element_count"], 0)

    def test_extracts_all_elements_in_document_order(self):
        snap = _snapshot()
        self.assertEqual([e.tag_name for e in snap.elements], _EXPECTED_TAGS)
        self.assertEqual(snap.dom_metadata["element_count"], len(_EXPECTED_TAGS))

    def test_extracts_text_and_attributes(self):
        elements = {e.tag_name: e for e in _snapshot().elements if e.tag_name != "a"}
        self.assertEqual(elements["h1"].text, "Title")
        self.assertEqual(elements["div"].attributes["id"], "main")
        self.assertEqual(elements["div"].attributes["class"], "container box")
        self.assertEqual(elements["input"].attributes["type"], "text")

    def test_valueless_attribute_becomes_empty_string(self):
        span = [e for e in _snapshot().elements if e.tag_name == "span"][0]
        self.assertEqual(span.attributes.get("hidden"), "")

    def test_static_visibility_heuristic(self):
        by_tag = {}
        for e in _snapshot().elements:
            by_tag.setdefault(e.tag_name, e)
        self.assertFalse(by_tag["head"].is_visible)
        self.assertFalse(by_tag["title"].is_visible)
        self.assertFalse(by_tag["span"].is_visible)  # hidden attribute
        self.assertTrue(by_tag["div"].is_visible)
        self.assertTrue(by_tag["a"].is_visible)

    def test_style_display_none_is_not_visible(self):
        snap = _snapshot('<div style="display: none">x</div><p>y</p>')
        self.assertFalse(snap.elements[0].is_visible)
        self.assertTrue(snap.elements[1].is_visible)

    # --- deterministic ids ----------------------------------------------
    def test_ids_are_positional_and_deterministic(self):
        snap = _snapshot()
        self.assertEqual(
            [e.element_id for e in snap.elements],
            [f"element-{i}" for i in range(len(_EXPECTED_TAGS))],
        )

    def test_repeated_extraction_is_equal(self):
        self.assertEqual(_snapshot(), _snapshot())


# =====================================================================
# Query / selectors
# =====================================================================
class BrowserDomQueryTests(unittest.TestCase):
    def test_empty_selector_returns_all(self):
        snap = _snapshot()
        result = _query(snap, "")
        self.assertEqual(result.query_count, len(_EXPECTED_TAGS))
        self.assertEqual(len(result.matched_elements), len(snap.elements))

    def test_tag_selector(self):
        self.assertEqual(_ids(_query(_snapshot(), "a")), ["element-6", "element-7"])

    def test_id_selector(self):
        self.assertEqual(_ids(_query(_snapshot(), "#main")), ["element-4"])

    def test_class_selector(self):
        self.assertEqual(_ids(_query(_snapshot(), ".link")), ["element-6", "element-7"])

    def test_class_selector_is_exact_token(self):
        # ".box" matches the "box" token within "container box".
        self.assertEqual(_ids(_query(_snapshot(), ".box")), ["element-4"])
        # A partial token does not match.
        self.assertEqual(_ids(_query(_snapshot(), ".bo")), [])

    def test_no_match_is_empty(self):
        result = _query(_snapshot(), "footer")
        self.assertEqual(result.matched_elements, [])
        self.assertEqual(result.query_count, 0)

    def test_query_preserves_document_order(self):
        # The two <a> elements must come back in source order.
        result = _query(_snapshot(), "a")
        self.assertEqual([e.text for e in result.matched_elements], ["Home", "About"])

    def test_query_metadata_is_deterministic(self):
        result = _query(_snapshot(), "a")
        self.assertEqual(result.query_metadata["selector"], "a")
        self.assertEqual(result.query_metadata["query_count"], 2)
        self.assertEqual(result.query_metadata["total_elements"], len(_EXPECTED_TAGS))
        self.assertEqual(result.query_metadata["session_id"], "s-1")


# =====================================================================
# Fresh immutable collections / provider independence / no leakage
# =====================================================================
class BrowserDomShapeTests(unittest.TestCase):
    def test_each_query_returns_a_fresh_list(self):
        snap = _snapshot()
        self.assertIsNot(
            _query(snap, "").matched_elements, _query(snap, "").matched_elements
        )

    def test_mutating_result_does_not_affect_snapshot(self):
        snap = _snapshot()
        result = _query(snap, "a")
        result.matched_elements.clear()
        self.assertEqual(_query(snap, "a").query_count, 2)
        self.assertEqual(len(snap.elements), len(_EXPECTED_TAGS))

    def test_elements_are_plain_dtos_only(self):
        for element in _snapshot().elements:
            self.assertIsInstance(element, BrowserElement)
            self.assertIsInstance(element, BaseModel)

    def test_no_playwright_object_leakage(self):
        # Every field is plain data — no browser/SDK object can appear.
        for element in _snapshot().elements:
            self.assertIsInstance(element.tag_name, str)
            self.assertIsInstance(element.text, str)
            self.assertIsInstance(element.attributes, dict)
            self.assertIsInstance(element.is_visible, bool)
            for value in element.attributes.values():
                self.assertIsInstance(value, str)
        # BrowserDOM parses strings only; Playwright is never imported.
        self.assertNotIn("playwright", sys.modules)


# =====================================================================
# Stateless behaviour
# =====================================================================
class BrowserDomStatelessTests(unittest.TestCase):
    def test_dom_holds_no_state(self):
        self.assertEqual(vars(BrowserDOM()), {})

    def test_dom_has_no_mutating_surface(self):
        for attr in ("click", "type", "scroll", "submit", "evaluate", "write"):
            self.assertFalse(hasattr(BrowserDOM, attr))

    def test_instances_are_independent(self):
        a = BrowserDOM().build_snapshot(_session(), _HTML)
        b = BrowserDOM().build_snapshot(_session(), "<p>x</p>")
        self.assertEqual(len(a.elements), len(_EXPECTED_TAGS))
        self.assertEqual(len(b.elements), 1)


# =====================================================================
# BrowserCapability delegation
# =====================================================================
class BrowserCapabilityDomDelegationTests(unittest.TestCase):
    def test_capture_dom_delegates(self):
        cap = BrowserCapability(_FakeBrowserDriver(), browser_dom=BrowserDOM())
        snap = cap.capture_dom(_session(), _HTML)
        self.assertEqual(len(snap.elements), len(_EXPECTED_TAGS))

    def test_capture_dom_works_without_injected_dom(self):
        # Sprint 15.6-style construction (no BrowserDOM) still discovers the DOM.
        cap = BrowserCapability(_FakeBrowserDriver())
        self.assertEqual(len(cap.capture_dom(_session(), _HTML).elements), len(_EXPECTED_TAGS))

    def test_query_dom_delegates(self):
        cap = BrowserCapability(_FakeBrowserDriver(), browser_dom=BrowserDOM())
        snap = cap.capture_dom(_session(), _HTML)
        result = cap.query_dom(
            snap, BrowserQueryRequest(session=snap.session, selector="a")
        )
        self.assertEqual(result.query_count, 2)

    def test_navigation_result_content_feeds_dom(self):
        # The HTML BrowserCapability retrieves is exactly what BrowserDOM parses.
        from app.services.runtime.browser_capability_models import (
            BrowserNavigationRequest,
        )

        cap = BrowserCapability(_FakeBrowserDriver())
        nav = cap.navigate(
            BrowserNavigationRequest(session_id="s", target_url="https://example.com")
        )
        snap = cap.capture_dom(nav.session, nav.page_content)
        self.assertEqual([e.tag_name for e in snap.elements], _EXPECTED_TAGS)


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class BrowserDomDependencyInjectionTests(unittest.TestCase):
    def test_get_browser_dom_returns_dom(self):
        from app.core.dependencies import get_browser_dom

        self.assertIsInstance(get_browser_dom(), BrowserDOM)

    def test_browser_dom_dep_is_wired(self):
        from app.core.dependencies import BrowserDOMDep

        self.assertIn(BrowserDOM, getattr(BrowserDOMDep, "__args__", ()))

    def test_browser_capability_has_dom_injected(self):
        from app.core.dependencies import get_browser_capability

        cap = get_browser_capability()
        self.assertIsInstance(cap, BrowserCapability)
        # DOM discovery works on the DI-wired capability.
        self.assertEqual(
            len(cap.capture_dom(_session(), _HTML).elements), len(_EXPECTED_TAGS)
        )


# =====================================================================
# Regression — Sprint 15.6 and prior seams unchanged
# =====================================================================
class BrowserDomRegressionTests(unittest.TestCase):
    def test_sprint_15_6_navigation_unchanged(self):
        from app.services.runtime.browser_capability_models import (
            BrowserNavigationRequest,
            NavigationStatus,
        )

        cap = BrowserCapability(_FakeBrowserDriver())
        result = cap.navigate(
            BrowserNavigationRequest(session_id="s", target_url="https://example.com")
        )
        self.assertEqual(result.navigation_status, NavigationStatus.SUCCESS.value)

    def test_sprint_14_execution_capability_seam_unchanged(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_sprint_15_1_registry_seam_unchanged(self):
        from app.core.dependencies import get_capability_registry

        self.assertEqual(get_capability_registry().snapshot().capability_count, 0)


if __name__ == "__main__":
    unittest.main()
