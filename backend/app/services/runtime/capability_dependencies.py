"""What each capability needs from the machine it runs on (Sprint 18.9).

Sprint 18.8 gave the builder and the runtime one contract for a step's *inputs*.
This is the other half of "will it run": the packages, binaries and directories a
capability needs from its deployment, and whether they are actually there.

The problem it solves is a specific one. Five capabilities need nothing but the
standard library, so they work anywhere the service starts. The Browser
capability needs Playwright *and* a Chromium build, and until now a deployment
missing either produced a workflow step that failed with ``No module named
'playwright'`` buried in a navigation error — a message that tells an operator
nothing about what to install. Availability is now something the service can be
asked, at startup and over HTTP, instead of something discovered by running a
workflow and reading the wreckage.

Probing is deliberately cheap and side-effect free: a module is looked up, not
imported; a browser is located on disk, not launched. Calling this never starts
anything, and never reports a path, a credential or an environment value — an
operator learns *what is missing and how to fix it*, and nothing about the host.
"""

import importlib.util
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Callable, Dict, List, Optional, Tuple

from app.utils.logger import get_logger

logger = get_logger(__name__)


class CapabilityStatus(str, Enum):
    """How ready a capability is to run.

    ``AVAILABLE`` — everything it needs is present. ``UNAVAILABLE`` — a required
    package is missing, so it cannot run at all. ``MISCONFIGURED`` — the package
    is installed but something it depends on is not, which is the more confusing
    case and the reason this distinction exists: Playwright installed without a
    Chromium build looks fine until the moment a page is loaded.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    MISCONFIGURED = "misconfigured"


@dataclass(frozen=True)
class CapabilityReport:
    """One capability's readiness, in terms an operator can act on."""

    capability: str
    status: CapabilityStatus
    #: What is true right now, in one sentence.
    detail: str
    #: What to do about it. Empty when there is nothing to do.
    remedy: str = ""
    #: Distribution names this capability needs, for documentation and reporting.
    required_packages: Tuple[str, ...] = ()
    #: External binaries or assets, named but never located.
    required_binaries: Tuple[str, ...] = ()

    @property
    def is_available(self) -> bool:
        return self.status is CapabilityStatus.AVAILABLE


@dataclass(frozen=True)
class CapabilityRequirement:
    """What one capability needs, and how to find out whether it has it."""

    capability: str
    summary: str
    packages: Tuple[str, ...] = ()
    binaries: Tuple[str, ...] = ()
    #: Extra check for anything a package listing cannot answer. Returns a
    #: ``(status, detail, remedy)`` triple, or ``None`` when satisfied.
    probe: Optional[Callable[[], Optional[Tuple[CapabilityStatus, str, str]]]] = None
    notes: str = ""
    #: Import names, where they differ from the distribution name.
    modules: Tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------


def _module_missing(module: str) -> bool:
    """Whether ``module`` cannot be imported, without importing it.

    ``find_spec`` raises for a module whose *parent* is absent, which for our
    purposes is the same answer as "not there".
    """
    try:
        return importlib.util.find_spec(module) is None
    except (ImportError, ModuleNotFoundError, ValueError):
        return True


#: How long to wait for Playwright to say where its browser is. Generous: the
#: driver process is slow to start, and a probe that gives up early would report
#: a browser as missing on a loaded machine.
_CHROMIUM_PROBE_TIMEOUT_SECONDS = 30.0


def _chromium_executable() -> Tuple[Optional[str], Optional[BaseException]]:
    """Ask Playwright where its Chromium is, on a thread of its own.

    The thread is not an optimisation. Playwright's sync API refuses to run
    inside a running asyncio event loop, and the service's startup hook is
    ``async`` — asking there raises, and a probe that read that as "no browser"
    would report a perfectly good deployment as broken. Running it off the loop
    makes the answer the same whoever asks.

    Returns the path, or the exception that prevented finding one. Never raises,
    and never launches the browser.
    """
    import threading

    outcome: Dict[str, object] = {}

    def query() -> None:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                outcome["path"] = playwright.chromium.executable_path
        except BaseException as exc:  # noqa: BLE001 - reported, never raised
            outcome["error"] = exc

    thread = threading.Thread(target=query, name="chromium-probe", daemon=True)
    thread.start()
    thread.join(timeout=_CHROMIUM_PROBE_TIMEOUT_SECONDS)

    if thread.is_alive():
        return None, TimeoutError("Playwright did not respond in time.")
    error = outcome.get("error")
    if isinstance(error, BaseException):
        return None, error
    path = outcome.get("path")
    return (path if isinstance(path, str) else None), None


@lru_cache(maxsize=1)
def _probe_chromium() -> Optional[Tuple[CapabilityStatus, str, str]]:
    """Whether a Chromium build is installed for Playwright to drive.

    ``pip install playwright`` installs the client library only; the browser
    itself is a separate download, and skipping it is the easiest deployment
    mistake to make. Playwright is asked where its Chromium is and whether that
    file exists — the browser is never launched.

    Answered once and remembered. Asking Playwright starts its driver process,
    which costs seconds — far too long for a health request, and pointless to
    repeat: what is installed on the host does not change while this process
    runs, and a package installed afterwards would not be importable without a
    restart anyway. :func:`reset_probe_cache` exists for the same reason tests
    need it.
    """
    if _module_missing("playwright"):
        return None  # the package check already reported this

    executable, error = _chromium_executable()

    if error is not None:
        return (
            CapabilityStatus.MISCONFIGURED,
            "Playwright is installed but its browser could not be located.",
            f"Run `python -m playwright install chromium`. ({type(error).__name__})",
        )

    import pathlib

    if not executable or not pathlib.Path(executable).exists():
        return (
            CapabilityStatus.MISCONFIGURED,
            "Playwright is installed but no Chromium build is present.",
            "Run `python -m playwright install chromium`.",
        )
    return None


# ---------------------------------------------------------------------
# The requirements
# ---------------------------------------------------------------------
#
# Established by reading every capability's imports and running each one: five
# of the six reach nothing outside the standard library, which is why only
# Browser carries packages here.

_PLAYWRIGHT_REMEDY = (
    "Install it with `pip install -r requirements.txt`, then download the "
    "browser with `python -m playwright install chromium`."
)

REQUIREMENTS: Tuple[CapabilityRequirement, ...] = (
    CapabilityRequirement(
        capability="python",
        summary="Runs Python in a restricted in-process sandbox.",
        notes=(
            "Standard library only. `numpy`, `pandas`, `openpyxl` and "
            "`matplotlib` are offered to authored code when installed and simply "
            "absent when not, so none is required for the capability to run — "
            "though a step whose code imports one will fail without it. They are "
            "left out of `requirements.txt` deliberately: they are conveniences "
            "for authored code, not requirements of the capability."
        ),
    ),
    CapabilityRequirement(
        capability="filesystem",
        summary="Reads and writes files in a managed workspace.",
        notes="Standard library only. Needs a writable temporary directory.",
    ),
    CapabilityRequirement(
        capability="email",
        summary="Composes and files mail in a local workspace.",
        notes=(
            "Standard library only, and offline: it opens no SMTP or IMAP "
            "connection and holds no mail credentials. The SMTP settings in "
            "`config.py` belong to account email (verification, password reset), "
            "not to this capability."
        ),
    ),
    CapabilityRequirement(
        capability="calendar",
        summary="Creates and queries events in a local workspace.",
        notes="Standard library only. No calendar service or credentials.",
    ),
    CapabilityRequirement(
        capability="github",
        summary="Creates and inspects repositories in a local workspace.",
        notes=(
            "Standard library only. Local repository state, not the GitHub API — "
            "no access token is used or needed."
        ),
    ),
    CapabilityRequirement(
        capability="browser",
        summary="Loads a web page in headless Chromium.",
        packages=("playwright",),
        binaries=("chromium",),
        probe=_probe_chromium,
        notes=(
            "The one capability with requirements beyond the standard library, "
            "and the one with two of them: the Playwright package and a Chromium "
            "build, downloaded separately. On a slim Linux image Chromium also "
            "needs its shared libraries — `python -m playwright install-deps "
            "chromium` installs them."
        ),
    ),
)

REQUIREMENT_BY_CAPABILITY: Dict[str, CapabilityRequirement] = {
    requirement.capability: requirement for requirement in REQUIREMENTS
}


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------


def probe_capability(capability: str) -> CapabilityReport:
    """Report whether one capability can run here.

    A capability with no recorded requirements is reported as available: five of
    the six need only the standard library, and inventing a doubt about them
    would be noise.
    """
    requirement = REQUIREMENT_BY_CAPABILITY.get(capability)
    if requirement is None:
        return CapabilityReport(
            capability=capability,
            status=CapabilityStatus.AVAILABLE,
            detail="No additional requirements are recorded for this capability.",
        )

    missing = [
        package
        for package, module in _package_modules(requirement)
        if _module_missing(module)
    ]
    if missing:
        names = ", ".join(missing)
        return CapabilityReport(
            capability=capability,
            status=CapabilityStatus.UNAVAILABLE,
            detail=f"Requires {names}, which {'is' if len(missing) == 1 else 'are'} not installed.",
            remedy=_PLAYWRIGHT_REMEDY if capability == "browser" else
            "Install it with `pip install -r requirements.txt`.",
            required_packages=requirement.packages,
            required_binaries=requirement.binaries,
        )

    if requirement.probe is not None:
        problem = requirement.probe()
        if problem is not None:
            status, detail, remedy = problem
            return CapabilityReport(
                capability=capability,
                status=status,
                detail=detail,
                remedy=remedy,
                required_packages=requirement.packages,
                required_binaries=requirement.binaries,
            )

    return CapabilityReport(
        capability=capability,
        status=CapabilityStatus.AVAILABLE,
        detail=requirement.summary,
        required_packages=requirement.packages,
        required_binaries=requirement.binaries,
    )


def _package_modules(requirement: CapabilityRequirement) -> Tuple[Tuple[str, str], ...]:
    """Pair each distribution name with the module that proves it is installed.

    They match for everything we depend on today; the pairing exists so a
    distribution whose import name differs can be added without special-casing.
    """
    if requirement.modules:
        return tuple(zip(requirement.packages, requirement.modules))
    return tuple((package, package) for package in requirement.packages)


def reset_probe_cache() -> None:
    """Forget what was found, so the next probe looks again.

    Only worth calling when the host has genuinely changed underneath a running
    process — which in practice means a test.
    """
    _probe_chromium.cache_clear()


def probe_all() -> List[CapabilityReport]:
    """Report every capability, in the order they are declared."""
    return [probe_capability(r.capability) for r in REQUIREMENTS]


def unavailable_capabilities() -> List[CapabilityReport]:
    """Only the capabilities that cannot run as this host is set up."""
    return [report for report in probe_all() if not report.is_available]


def log_startup_report() -> List[CapabilityReport]:
    """Log what can and cannot run, once, at startup.

    Nothing here stops the service. A deployment that has not installed an
    optional capability should still serve every other request, and refusing to
    boot over one would turn a degraded feature into an outage. The log line is
    the warning; :func:`probe_all` behind ``/health/capabilities`` is the
    standing answer.
    """
    reports = probe_all()
    ready = [r.capability for r in reports if r.is_available]
    logger.info(
        "Runtime capabilities ready (%d/%d): %s",
        len(ready),
        len(reports),
        ", ".join(ready) or "none",
    )

    for report in reports:
        if report.is_available:
            continue
        logger.warning(
            "Runtime capability '%s' is %s. %s %s",
            report.capability,
            report.status.value,
            report.detail,
            report.remedy,
        )
    return reports
