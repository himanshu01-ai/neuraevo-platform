"""Unit tests for the Sprint 15.8 Browser Interaction layer.

Covers deterministic user interactions end to end without any real browser,
network, SDK, or Playwright import — every test injects a fake
:class:`BrowserDriver` whose ``perform_interaction`` records the call (or raises to
simulate a provider failure).

Covers:

* the immutable :class:`BrowserInteractionRequest` / :class:`BrowserInteraction
  Result` DTOs and the :class:`InteractionType` / :class:`InteractionStatus` enums
  (defaults, frozen immutability);
* :class:`BrowserInteraction` — click, type, scroll, focus, select, unsupported
  interaction, graceful failures (no provider-object leakage), BrowserElement /
  session non-mutation, provider independence, and stateless behaviour;
* the :class:`BrowserCapability` delegation and the composition-root wiring
  (``get_browser_interaction`` / ``BrowserInteractionDep``, injected into the
  capability); and
* regression that the Sprint 15.6/15.7 browser behaviour and prior seams are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_browser_interaction
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
from app.services.runtime.browser_dom_models import BrowserElement
from app.services.runtime.browser_interaction import BrowserInteraction
from app.services.runtime.browser_interaction_models import (
    BrowserInteractionRequest,
    BrowserInteractionResult,
    InteractionStatus,
    InteractionType,
)


# =====================================================================
# Fake driver (NOT a real browser — records interactions or raises)
# =====================================================================
class _FakeInteractionDriver(BrowserDriver):
    def __init__(self, exc: Exception = None) -> None:
        self.exc = exc
        self.calls = []

    def load_page(self, url, timeout_ms):
        return LoadedPage(title="T", content="<html></html>")

    def perform_interaction(self, url, action, target, value, timeout_ms):
        self.calls.append(
            {"url": url, "action": action, "target": target, "value": value}
        )
        if self.exc is not None:
            raise self.exc


def _session(**overrides) -> BrowserSession:
    data = dict(
        session_id="s-1",
        current_url="https://example.com",
        page_loaded=True,
        browser_metadata={"engine": "chromium"},
    )
    data.update(overrides)
    return BrowserSession(**data)


def _element(**overrides) -> BrowserElement:
    data = dict(element_id="element-4", tag_name="button", attributes={"id": "go"})
    data.update(overrides)
    return BrowserElement(**data)


def _request(interaction_type="CLICK", value="", session=None, element=None):
    return BrowserInteractionRequest(
        session=session or _session(),
        element=element or _element(),
        interaction_type=interaction_type,
        interaction_value=value,
    )


def _interact(interaction_type="CLICK", value="", driver=None, session=None, element=None):
    return BrowserInteraction().interact(
        _request(interaction_type, value, session, element),
        driver or _FakeInteractionDriver(),
    )


# =====================================================================
# DTOs
# =====================================================================
class InteractionDtoTests(unittest.TestCase):
    def test_interaction_type_values(self):
        self.assertEqual(
            [t.value for t in InteractionType],
            ["CLICK", "TYPE", "SCROLL", "FOCUS", "SELECT"],
        )

    def test_status_values(self):
        self.assertEqual(InteractionStatus.SUCCESS.value, "SUCCESS")
        self.assertEqual(InteractionStatus.FAILED.value, "FAILED")

    def test_request_defaults(self):
        req = BrowserInteractionRequest(
            session=_session(), element=_element(), interaction_type="CLICK"
        )
        self.assertEqual(req.interaction_value, "")
        self.assertEqual(req.interaction_metadata, {})

    def test_request_is_immutable(self):
        req = _request()
        with self.assertRaises(ValidationError):
            req.interaction_type = "TYPE"
        with self.assertRaises(ValidationError):
            req.interaction_value = "x"

    def test_result_is_immutable(self):
        result = _interact()
        with self.assertRaises(ValidationError):
            result.interaction_status = "FAILED"
        with self.assertRaises(ValidationError):
            result.interaction_metadata = {}


# =====================================================================
# Interaction behaviour
# =====================================================================
class BrowserInteractionTests(unittest.TestCase):
    # --- the five supported interactions --------------------------------
    def test_click(self):
        driver = _FakeInteractionDriver()
        result = _interact("CLICK", driver=driver)
        self.assertEqual(result.interaction_status, InteractionStatus.SUCCESS.value)
        self.assertEqual(driver.calls[0]["action"], "CLICK")

    def test_type(self):
        driver = _FakeInteractionDriver()
        result = _interact("TYPE", value="hello", driver=driver)
        self.assertEqual(result.interaction_status, "SUCCESS")
        self.assertEqual(driver.calls[0]["value"], "hello")

    def test_scroll(self):
        self.assertEqual(_interact("SCROLL").interaction_status, "SUCCESS")

    def test_focus(self):
        self.assertEqual(_interact("FOCUS").interaction_status, "SUCCESS")

    def test_select(self):
        driver = _FakeInteractionDriver()
        result = _interact("SELECT", value="opt-2", driver=driver)
        self.assertEqual(result.interaction_status, "SUCCESS")
        self.assertEqual(driver.calls[0]["value"], "opt-2")

    def test_driver_receives_plain_element_descriptor(self):
        driver = _FakeInteractionDriver()
        _interact("CLICK", driver=driver)
        target = driver.calls[0]["target"]
        self.assertEqual(target["element_id"], "element-4")
        self.assertEqual(target["tag_name"], "button")
        self.assertEqual(target["attributes"], {"id": "go"})
        self.assertNotIsInstance(target, BaseModel)

    def test_success_records_last_interaction_on_session(self):
        result = _interact("CLICK")
        self.assertEqual(
            result.updated_session.browser_metadata["last_interaction"], "CLICK"
        )
        self.assertEqual(result.updated_session.session_id, "s-1")
        self.assertEqual(result.updated_session.browser_metadata["engine"], "chromium")

    # --- unsupported interaction ----------------------------------------
    def test_unsupported_interaction_fails_without_driver_call(self):
        driver = _FakeInteractionDriver()
        result = _interact("HOVER", driver=driver)
        self.assertEqual(result.interaction_status, InteractionStatus.FAILED.value)
        self.assertIn("unsupported", result.interaction_metadata["error"])
        self.assertEqual(driver.calls, [])

    def test_no_loaded_page_fails_gracefully(self):
        result = _interact("CLICK", session=BrowserSession(session_id="s-2"))
        self.assertEqual(result.interaction_status, "FAILED")
        self.assertEqual(result.interaction_metadata["error"], "no loaded page")

    # --- graceful failure / no provider leakage -------------------------
    def test_provider_exception_is_graceful(self):
        result = _interact("CLICK", driver=_FakeInteractionDriver(exc=RuntimeError("boom")))
        self.assertEqual(result.interaction_status, "FAILED")
        self.assertEqual(
            result.interaction_metadata["error"], "interaction error: RuntimeError"
        )

    def test_provider_object_never_leaks(self):
        class _ProviderError(Exception):
            pass

        result = _interact("CLICK", driver=_FakeInteractionDriver(exc=_ProviderError("secret")))
        # Only plain strings appear anywhere in the result.
        self.assertNotIn("secret", str(result.interaction_metadata))
        for value in result.interaction_metadata.values():
            self.assertIsInstance(value, str)

    # --- non-mutation ---------------------------------------------------
    def test_element_is_never_mutated(self):
        element = _element()
        before = element.model_dump()
        _interact("CLICK", element=element)
        self.assertEqual(element.model_dump(), before)

    def test_input_session_is_never_mutated(self):
        session = _session()
        before = session.model_dump()
        result = _interact("CLICK", session=session)
        self.assertEqual(session.model_dump(), before)
        # The updated session is a distinct object.
        self.assertIsNot(result.updated_session, session)

    # --- determinism ----------------------------------------------------
    def test_repeated_interaction_is_equal(self):
        bi = BrowserInteraction()
        req = _request("CLICK")
        self.assertEqual(
            bi.interact(req, _FakeInteractionDriver()),
            bi.interact(req, _FakeInteractionDriver()),
        )


# =====================================================================
# Provider independence / stateless behaviour / no leakage
# =====================================================================
class BrowserInteractionShapeTests(unittest.TestCase):
    def test_result_is_plain_dto(self):
        result = _interact("CLICK")
        self.assertIsInstance(result, BrowserInteractionResult)
        self.assertIsInstance(result.updated_session, BrowserSession)

    def test_no_playwright_leakage(self):
        _interact("CLICK")
        self.assertNotIn("playwright", sys.modules)

    def test_interaction_holds_no_state(self):
        self.assertEqual(vars(BrowserInteraction()), {})

    def test_interaction_has_no_dom_or_html_surface(self):
        for attr in ("query", "build_snapshot", "parse", "evaluate"):
            self.assertFalse(hasattr(BrowserInteraction, attr))


# =====================================================================
# BrowserCapability delegation
# =====================================================================
class BrowserCapabilityInteractionDelegationTests(unittest.TestCase):
    def test_capability_delegates_interaction(self):
        driver = _FakeInteractionDriver()
        cap = BrowserCapability(driver, browser_interaction=BrowserInteraction())
        result = cap.interact(_request("CLICK"))
        self.assertEqual(result.interaction_status, "SUCCESS")
        self.assertEqual(driver.calls[0]["action"], "CLICK")

    def test_capability_uses_its_own_driver(self):
        # The interaction runs through the capability's driver (the single
        # Playwright-facing layer), not a separate one.
        driver = _FakeInteractionDriver(exc=ValueError("x"))
        cap = BrowserCapability(driver)
        self.assertEqual(cap.interact(_request("CLICK")).interaction_status, "FAILED")

    def test_interaction_works_without_injected_collaborator(self):
        cap = BrowserCapability(_FakeInteractionDriver())
        self.assertEqual(cap.interact(_request("CLICK")).interaction_status, "SUCCESS")

    def test_capability_constructor_contract_preserved(self):
        # Sprint 15.6 contract: driver + timeout only when no collaborators given.
        cap = BrowserCapability(_FakeInteractionDriver(), timeout_ms=1000)
        self.assertEqual(set(vars(cap)), {"browser_driver", "timeout_ms"})


# =====================================================================
# Composition-root dependency injection
# =====================================================================
class BrowserInteractionDependencyInjectionTests(unittest.TestCase):
    def test_get_browser_interaction_returns_interaction(self):
        from app.core.dependencies import get_browser_interaction

        self.assertIsInstance(get_browser_interaction(), BrowserInteraction)

    def test_browser_interaction_dep_is_wired(self):
        from app.core.dependencies import BrowserInteractionDep

        self.assertIn(
            BrowserInteraction, getattr(BrowserInteractionDep, "__args__", ())
        )

    def test_browser_capability_has_interaction_injected(self):
        from app.core.dependencies import get_browser_capability

        cap = get_browser_capability()
        # An unsupported type fails deterministically before any driver call, so
        # this proves the interaction collaborator is wired without needing a real
        # browser (the DI-wired capability uses the real Playwright driver).
        result = cap.interact(_request("HOVER", session=_session()))
        self.assertIsInstance(result, BrowserInteractionResult)
        self.assertEqual(result.interaction_status, "FAILED")
        self.assertIn("unsupported", result.interaction_metadata["error"])


# =====================================================================
# Regression — Sprint 15.6/15.7 and prior seams unchanged
# =====================================================================
class BrowserInteractionRegressionTests(unittest.TestCase):
    def test_sprint_15_6_navigation_unchanged(self):
        from app.services.runtime.browser_capability_models import (
            BrowserNavigationRequest,
            NavigationStatus,
        )

        cap = BrowserCapability(_FakeInteractionDriver())
        result = cap.navigate(
            BrowserNavigationRequest(session_id="s", target_url="https://example.com")
        )
        self.assertEqual(result.navigation_status, NavigationStatus.SUCCESS.value)

    def test_sprint_15_7_dom_unchanged(self):
        cap = BrowserCapability(_FakeInteractionDriver())
        snap = cap.capture_dom(_session(), "<div><a>x</a></div>")
        self.assertEqual([e.tag_name for e in snap.elements], ["div", "a"])

    def test_sprint_14_execution_capability_seam_unchanged(self):
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_sprint_15_1_registry_seam_unchanged(self):
        from app.core.dependencies import get_capability_registry

        self.assertEqual(get_capability_registry().snapshot().capability_count, 0)


if __name__ == "__main__":
    unittest.main()
