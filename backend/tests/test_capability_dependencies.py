"""Runtime dependency tests (Sprint 18.9 — deployment readiness).

Sprint 18.8 ended with a Browser step that failed saying ``No module named
'playwright'``, which told an operator nothing. These cover what replaced that:

* ``RequirementTests`` — the audit itself: every routable capability is
  accounted for, and only Browser claims anything beyond the standard library.
* ``ProbeTests`` — availability reporting, including the two failure modes
  (package absent, browser absent) simulated rather than waited for.
* ``BrowserDependencyErrorTests`` — a missing dependency produces an actionable
  message and reaches the person who ran the workflow.
* ``HealthEndpointTests`` — the report over HTTP, and that it describes no host.
* ``StartupValidationTests`` — startup says what can run and never refuses to
  boot over what cannot.

Runnable with stdlib unittest:
    PYTHONPATH=. python -m unittest tests.test_capability_dependencies
"""

import dataclasses
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.dependencies import get_capability_router
from app.main import app
from app.services.runtime.browser_capability import (
    BrowserCapability,
    BrowserDependencyError,
    BrowserDriver,
    _import_playwright,
)
from app.services.runtime.browser_capability_models import BrowserNavigationRequest
from app.services.runtime.capability_dependencies import (
    REQUIREMENT_BY_CAPABILITY,
    CapabilityStatus,
    log_startup_report,
    probe_all,
    probe_capability,
    reset_probe_cache,
    unavailable_capabilities,
)
from app.services.runtime.execution_capability_models import CapabilityExecutionRequest

MODULE = "app.services.runtime.capability_dependencies"


def _browser_probe(probe):
    """Swap the browser's Chromium check for one that answers immediately.

    The requirement holds the probe as a value captured when the module loaded,
    so patching the module attribute would not reach it — and the real probe
    starts Playwright's driver, which is seconds a test should not spend.
    """
    replacement = dataclasses.replace(REQUIREMENT_BY_CAPABILITY["browser"], probe=probe)
    return patch.dict(REQUIREMENT_BY_CAPABILITY, {"browser": replacement})


# --- the audit -----------------------------------------------------------


class RequirementTests(unittest.TestCase):
    def test_every_routable_capability_is_audited(self):
        """Nothing the router can dispatch to is missing from the audit."""
        router = get_capability_router()
        for capability in REQUIREMENT_BY_CAPABILITY:
            with self.subTest(capability):
                self.assertTrue(router.is_available(capability))

        # And the other direction: six capabilities, six audit entries.
        self.assertEqual(len(REQUIREMENT_BY_CAPABILITY), 6)

    def test_browser_is_the_only_capability_needing_a_package(self):
        needing = {
            name
            for name, requirement in REQUIREMENT_BY_CAPABILITY.items()
            if requirement.packages or requirement.binaries
        }
        self.assertEqual(needing, {"browser"})

    def test_browser_names_both_of_its_requirements(self):
        """The package and the browser are separate installs; both are recorded."""
        browser = REQUIREMENT_BY_CAPABILITY["browser"]
        self.assertIn("playwright", browser.packages)
        self.assertIn("chromium", browser.binaries)

    def test_every_requirement_explains_itself(self):
        for name, requirement in REQUIREMENT_BY_CAPABILITY.items():
            with self.subTest(name):
                self.assertTrue(requirement.summary.strip())
                self.assertTrue(requirement.notes.strip())


# --- probing -------------------------------------------------------------


class ProbeTests(unittest.TestCase):
    def test_stdlib_capabilities_are_always_available(self):
        for capability in ("python", "filesystem", "email", "calendar", "github"):
            with self.subTest(capability):
                report = probe_capability(capability)
                self.assertEqual(report.status, CapabilityStatus.AVAILABLE)
                self.assertEqual(report.remedy, "")

    def test_probe_all_covers_every_capability(self):
        self.assertEqual(
            [r.capability for r in probe_all()],
            list(REQUIREMENT_BY_CAPABILITY),
        )

    def test_unknown_capability_makes_no_claims(self):
        report = probe_capability("teleport")
        self.assertEqual(report.status, CapabilityStatus.AVAILABLE)
        self.assertEqual(report.required_packages, ())

    def test_missing_package_reports_unavailable_with_a_remedy(self):
        with patch(f"{MODULE}._module_missing", return_value=True):
            report = probe_capability("browser")
        self.assertEqual(report.status, CapabilityStatus.UNAVAILABLE)
        self.assertIn("playwright", report.detail.lower())
        self.assertIn("playwright install chromium", report.remedy)

    def test_missing_browser_binary_reports_misconfigured(self):
        """Installed package, no Chromium — the mistake a deployment makes."""
        problem = (
            CapabilityStatus.MISCONFIGURED,
            "Playwright is installed but no Chromium build is present.",
            "Run `python -m playwright install chromium`.",
        )
        with _browser_probe(lambda: problem), patch(
            f"{MODULE}._module_missing", return_value=False
        ):
            report = probe_capability("browser")

        self.assertEqual(report.status, CapabilityStatus.MISCONFIGURED)
        self.assertIn("Chromium", report.detail)
        self.assertIn("playwright install chromium", report.remedy)

    def test_unavailable_list_is_empty_when_everything_is_present(self):
        with _browser_probe(lambda: None), patch(
            f"{MODULE}._module_missing", return_value=False
        ):
            self.assertEqual(unavailable_capabilities(), [])

    def test_unavailable_list_names_only_what_is_broken(self):
        with patch(f"{MODULE}._module_missing", return_value=True):
            broken = unavailable_capabilities()
        self.assertEqual([r.capability for r in broken], ["browser"])

    def test_probing_never_reports_a_filesystem_path(self):
        """Reports are for operators, not a description of the host."""
        for report in probe_all():
            text = f"{report.detail} {report.remedy}"
            with self.subTest(report.capability):
                self.assertNotIn(":\\", text)
                self.assertNotIn("/home/", text)
                self.assertNotIn("AppData", text)


# --- actionable errors ---------------------------------------------------


class _MissingDependencyDriver(BrowserDriver):
    """A driver standing in for a deployment with no browser installed."""

    def load_page(self, url, timeout_ms):
        raise BrowserDependencyError(
            "The Browser capability requires Playwright, which isn't installed. "
            "Install the backend requirements, then run "
            "`python -m playwright install chromium`."
        )


class _BrokenDriver(BrowserDriver):
    """A driver whose page genuinely fails to load."""

    def load_page(self, url, timeout_ms):
        raise TimeoutError("timed out")


class BrowserDependencyErrorTests(unittest.TestCase):
    def test_import_helper_raises_an_actionable_error(self):
        with patch.dict("sys.modules", {"playwright.sync_api": None}):
            with self.assertRaises(BrowserDependencyError) as caught:
                _import_playwright()

        message = str(caught.exception)
        self.assertIn("Browser capability requires Playwright", message)
        self.assertIn("playwright install chromium", message)
        self.assertNotIn("No module named", message)

    def test_dependency_failure_reaches_the_navigation_result_verbatim(self):
        capability = BrowserCapability(_MissingDependencyDriver())
        result = capability.navigate(
            BrowserNavigationRequest(session_id="s1", target_url="https://example.com")
        )

        self.assertEqual(result.navigation_status, "FAILED")
        error = result.navigation_metadata["error"]
        self.assertIn("requires Playwright", error)
        # Not dressed up as a page that wouldn't load.
        self.assertNotIn("navigation error", error)

    def test_ordinary_navigation_failure_is_still_labelled_as_one(self):
        capability = BrowserCapability(_BrokenDriver())
        result = capability.navigate(
            BrowserNavigationRequest(session_id="s1", target_url="https://example.com")
        )
        self.assertIn("navigation error", result.navigation_metadata["error"])

    def test_the_reason_reaches_the_person_who_ran_the_step(self):
        """A failed browser step used to show its outcome and no reason at all."""
        capability = BrowserCapability(_MissingDependencyDriver())
        result = capability.execute(
            CapabilityExecutionRequest(
                runtime_id="r",
                execution_id="e",
                execution_unit_id="s1",
                capability_name="browser",
                capability_inputs={"target_url": "https://example.com"},
            )
        )

        self.assertEqual(result.execution_status, "FAILED")
        self.assertIn("requires Playwright", result.capability_outputs["error"])

    def test_a_successful_step_carries_no_error(self):
        class _WorkingDriver(BrowserDriver):
            def load_page(self, url, timeout_ms):
                from app.services.runtime.browser_capability import LoadedPage

                return LoadedPage(title="Example", content="<html></html>")

        result = BrowserCapability(_WorkingDriver()).execute(
            CapabilityExecutionRequest(
                runtime_id="r",
                execution_id="e",
                execution_unit_id="s1",
                capability_name="browser",
                capability_inputs={"target_url": "https://example.com"},
            )
        )
        self.assertEqual(result.execution_status, "COMPLETED")
        self.assertNotIn("error", result.capability_outputs)


# --- health --------------------------------------------------------------


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_liveness_check_is_unchanged(self):
        """The cheap probe stays cheap; the audit lives at its own path."""
        body = self.client.get("/api/v1/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertNotIn("capabilities", body)

    def test_capability_report_covers_every_capability(self):
        body = self.client.get("/api/v1/health/capabilities").json()
        self.assertEqual(body["total_count"], len(REQUIREMENT_BY_CAPABILITY))
        self.assertEqual(
            [c["capability"] for c in body["capabilities"]],
            list(REQUIREMENT_BY_CAPABILITY),
        )

    def test_report_is_degraded_when_something_is_missing(self):
        with patch(f"{MODULE}._module_missing", return_value=True):
            body = self.client.get("/api/v1/health/capabilities").json()

        self.assertEqual(body["status"], "degraded")
        self.assertEqual(body["available_count"], body["total_count"] - 1)
        browser = next(c for c in body["capabilities"] if c["capability"] == "browser")
        self.assertEqual(browser["status"], "unavailable")
        self.assertIn("playwright install chromium", browser["remedy"])

    def test_report_is_ok_when_everything_is_present(self):
        with _browser_probe(lambda: None), patch(
            f"{MODULE}._module_missing", return_value=False
        ):
            body = self.client.get("/api/v1/health/capabilities").json()

        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["available_count"], body["total_count"])

    def test_report_is_cheap_enough_to_poll(self):
        """Asking Playwright starts its driver; a health check must not wait."""
        import time

        self.client.get("/api/v1/health/capabilities")  # warm the probe
        started = time.perf_counter()
        self.client.get("/api/v1/health/capabilities")
        self.assertLess(time.perf_counter() - started, 0.5)

    def test_report_exposes_no_secrets_or_paths(self):
        from app.core.config import settings

        raw = self.client.get("/api/v1/health/capabilities").text
        for secret in (settings.JWT_SECRET_KEY, settings.ANTHROPIC_API_KEY or "\0"):
            self.assertNotIn(secret, raw)
        for path_marker in (":\\", "/home/", "AppData", "/usr/"):
            self.assertNotIn(path_marker, raw)

    def test_report_needs_no_authentication(self):
        """An operator checking a deployment has no account on it."""
        self.assertEqual(self.client.get("/api/v1/health/capabilities").status_code, 200)


# --- startup -------------------------------------------------------------


class StartupValidationTests(unittest.TestCase):
    def test_startup_reports_every_capability(self):
        self.assertEqual(len(log_startup_report()), len(REQUIREMENT_BY_CAPABILITY))

    def test_startup_warns_about_what_is_missing(self):
        with patch(f"{MODULE}._module_missing", return_value=True):
            with self.assertLogs("app.services.runtime.capability_dependencies", "WARNING") as logs:
                log_startup_report()

        warning = " ".join(logs.output)
        self.assertIn("browser", warning)
        self.assertIn("playwright install chromium", warning)

    def test_startup_does_not_fail_when_a_capability_is_missing(self):
        """A degraded feature must not become an outage."""
        with patch(f"{MODULE}._module_missing", return_value=True):
            reports = log_startup_report()  # must not raise
        self.assertTrue(any(not r.is_available for r in reports))

    def test_application_starts_with_a_capability_missing(self):
        with patch(f"{MODULE}._module_missing", return_value=True):
            with TestClient(app) as client:  # runs the lifespan
                self.assertEqual(client.get("/api/v1/health").status_code, 200)

    def test_startup_is_not_confused_by_the_event_loop(self):
        """The probe must answer the same on the loop as off it.

        Playwright's sync API refuses to run inside a running asyncio loop, and
        the startup hook is async. Probing there raised, which read as "no
        browser" — reporting a working deployment as misconfigured, which is
        worse than not checking at all.
        """
        reset_probe_cache()
        with TestClient(app):  # runs the async lifespan, which probes
            pass
        from_startup = probe_capability("browser")

        reset_probe_cache()
        off_the_loop = probe_capability("browser")

        self.assertEqual(from_startup.status, off_the_loop.status)
        self.assertEqual(from_startup.detail, off_the_loop.detail)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
