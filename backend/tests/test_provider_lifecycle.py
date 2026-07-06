"""H1 production-hardening tests — application-scoped provider lifecycle.

Verifies the ownership model introduced to eliminate the Sprint 12.15 HIGH
finding: the Gemini Live session provider (and its background event loop) is a
single application-scoped instance, shared across requests, with graceful
shutdown — no duplicate providers, no duplicate loops, no thread/task leaks.

Everything is driven with fakes / a mocked SDK client and trivial coroutines on
the provider's REAL background loop — no network, no google-genai, no API key.
No product behavior is exercised differently; only lifetime/ownership is under
test.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_provider_lifecycle
"""

import asyncio
import threading
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.core.dependencies import (
    build_app_session_provider,
    get_app_session_provider,
    get_conversation_runtime,
)
from app.services.multimodal_ai.providers import ProviderConfig
from app.services.runtime import ConversationRuntime
from app.services.session import SessionService
from app.services.session.providers.gemini_live_provider import (
    GeminiLiveSessionProvider,
)


def _make_provider():
    """A provider with a mocked SDK client (no network, no real Live calls)."""
    client = MagicMock(name="genai_client")
    config = ProviderConfig(provider_name="gemini", default_model="gemini-2.5-flash")
    return GeminiLiveSessionProvider(client, config)


async def _echo(value):
    return value


def _live_loop_threads():
    return [
        t
        for t in threading.enumerate()
        if t.name == "gemini-live-session-loop" and t.is_alive()
    ]


# =====================================================================
# Background event loop: starts once, reused, shuts down cleanly
# =====================================================================
class BackgroundLoopLifecycleTests(unittest.TestCase):
    def test_loop_starts_lazily_not_at_construction(self):
        provider = _make_provider()
        self.assertIsNone(provider._loop)
        self.assertIsNone(provider._loop_thread)

    def test_loop_starts_once_and_is_reused(self):
        provider = _make_provider()
        try:
            self.assertEqual(provider._run_async(_echo(1), 5), 1)
            loop_after_first = provider._loop
            thread_after_first = provider._loop_thread
            self.assertTrue(thread_after_first.is_alive())
            # Many further operations reuse the SAME loop + thread.
            for n in range(20):
                self.assertEqual(provider._run_async(_echo(n), 5), n)
            self.assertIs(provider._loop, loop_after_first)
            self.assertIs(provider._loop_thread, thread_after_first)
        finally:
            provider.shutdown()

    def test_shutdown_stops_loop_and_joins_thread(self):
        provider = _make_provider()
        provider._run_async(_echo(1), 5)
        thread = provider._loop_thread
        loop = provider._loop
        self.assertTrue(thread.is_alive())
        provider.shutdown()
        self.assertFalse(thread.is_alive(), "background thread must be reclaimed")
        self.assertIsNone(provider._loop)
        self.assertIsNone(provider._loop_thread)
        self.assertTrue(loop.is_closed(), "event loop must be closed")

    def test_shutdown_is_idempotent(self):
        provider = _make_provider()
        provider._run_async(_echo(1), 5)
        provider.shutdown()
        provider.shutdown()  # no raise, no-op
        provider.shutdown()
        self.assertTrue(provider._closed)

    def test_shutdown_without_ever_starting_loop_is_safe(self):
        provider = _make_provider()
        provider.shutdown()  # never ran an operation; no loop to reclaim
        self.assertTrue(provider._closed)
        self.assertIsNone(provider._loop)

    def test_no_new_loop_after_shutdown(self):
        provider = _make_provider()
        provider._run_async(_echo(1), 5)
        provider.shutdown()
        coro = _echo(2)
        try:
            with self.assertRaises(RuntimeError):
                provider._run_async(coro, 5)
        finally:
            coro.close()  # never scheduled (loop is down) — close to silence warning

    def test_shutdown_closes_remaining_live_sessions(self):
        # A fake open session record must be torn down by shutdown via the
        # single cleanup path (no leaked SDK handle).
        provider = _make_provider()
        provider._run_async(_echo(1), 5)
        cleaned = []
        original_cleanup = provider._cleanup_session

        def _tracking_cleanup(record):
            cleaned.append(record)
            return original_cleanup(record)

        provider._cleanup_session = _tracking_cleanup
        record = SimpleNamespace(handle=None, session=object())
        provider._sessions[uuid.uuid4()] = record
        provider.shutdown()
        self.assertIn(record, cleaned)

    def test_no_thread_leak_across_create_and_shutdown_cycles(self):
        before = len(_live_loop_threads())
        for _ in range(5):
            provider = _make_provider()
            provider._run_async(_echo(1), 5)
            provider.shutdown()
        after = len(_live_loop_threads())
        self.assertEqual(after, before, "no gemini-live loop thread may leak")


# =====================================================================
# Application-scoped ownership (app.state, not a module global)
# =====================================================================
class AppScopedProviderTests(unittest.TestCase):
    def _request_with(self, provider):
        return SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(session_provider=provider))
        )

    def test_accessor_returns_the_app_scoped_instance(self):
        provider = _make_provider()
        try:
            request = self._request_with(provider)
            # Every call returns the SAME instance — no per-request construction.
            self.assertIs(get_app_session_provider(request), provider)
            self.assertIs(get_app_session_provider(request), provider)
        finally:
            provider.shutdown()

    def test_accessor_raises_503_when_unconfigured(self):
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
        with self.assertRaises(HTTPException) as ctx:
            get_app_session_provider(request)
        self.assertEqual(ctx.exception.status_code, 503)

    def test_builder_returns_none_without_gemini_key(self):
        # With no GEMINI_API_KEY, get_genai_client raises; the builder tolerates
        # it and returns None so the app still boots.
        with patch(
            "app.core.dependencies.get_genai_client",
            side_effect=ValueError("GEMINI_API_KEY is not set"),
        ):
            self.assertIsNone(build_app_session_provider())

    def test_builder_uses_injected_client_and_config(self):
        fake_client = MagicMock(name="client")
        with patch(
            "app.core.dependencies.get_genai_client", return_value=fake_client
        ):
            provider = build_app_session_provider()
        self.assertIsInstance(provider, GeminiLiveSessionProvider)
        self.assertIs(provider.client, fake_client)

    def test_no_module_global_provider_state(self):
        # The provider is never stored on the dependencies module — ownership
        # lives only on app.state. Guards against reintroducing a singleton.
        import app.core.dependencies as deps

        for name in vars(deps):
            self.assertNotIsInstance(
                getattr(deps, name), GeminiLiveSessionProvider
            )


# =====================================================================
# Runtime shares the ONE app-scoped provider across requests
# =====================================================================
class RuntimeSharesAppProviderTests(unittest.TestCase):
    def test_both_seams_bind_to_the_single_provider(self):
        provider = _make_provider()
        try:
            runtime = get_conversation_runtime(provider, MagicMock(), MagicMock())
            self.assertIsInstance(runtime, ConversationRuntime)
            self.assertIs(runtime.live_messaging, provider)
            self.assertIsInstance(runtime.session_service, SessionService)
            self.assertIs(runtime.session_service.provider, provider)
        finally:
            provider.shutdown()

    def test_many_requests_reuse_the_same_provider_and_loop(self):
        # Simulate N requests: each builds a (cheap) per-request runtime around
        # the ONE shared app-scoped provider. One provider, one loop. Measured
        # as a delta over the process baseline so unrelated tests' loop threads
        # never affect the assertion.
        baseline = len(_live_loop_threads())
        provider = _make_provider()
        try:
            runtimes = [
                get_conversation_runtime(provider, MagicMock(), MagicMock())
                for _ in range(50)
            ]
            providers = {id(r.live_messaging) for r in runtimes}
            self.assertEqual(len(providers), 1)
            self.assertIs(runtimes[0].live_messaging, provider)
            # Drive the shared loop from all "requests" — still one thread.
            for _ in range(50):
                provider._run_async(_echo(1), 5)
            self.assertEqual(len(_live_loop_threads()) - baseline, 1)
            self.assertTrue(provider._loop_thread.is_alive())
        finally:
            provider.shutdown()
        self.assertEqual(len(_live_loop_threads()) - baseline, 0)


# =====================================================================
# Concurrency: one shared provider + loop under many threads
# =====================================================================
class ConcurrentSharedProviderTests(unittest.TestCase):
    def test_concurrent_operations_share_one_loop_no_errors(self):
        baseline = len(_live_loop_threads())
        provider = _make_provider()
        errors = []
        results = []
        barrier = threading.Barrier(40)

        def worker(idx):
            try:
                barrier.wait()
                for _ in range(25):
                    results.append(provider._run_async(_echo(idx), 5))
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
        try:
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            self.assertEqual(len(results), 40 * 25)
            # Exactly one background loop (this provider's) served every
            # concurrent caller — measured as a delta over the baseline.
            self.assertEqual(len(_live_loop_threads()) - baseline, 1)
        finally:
            provider.shutdown()
        self.assertEqual(len(_live_loop_threads()) - baseline, 0)


# =====================================================================
# Application lifecycle: startup creates once, shutdown disposes once
# =====================================================================
class ApplicationLifecycleTests(unittest.TestCase):
    def test_lifespan_builds_once_and_shuts_down_once(self):
        from app.main import app, lifespan

        fake_provider = MagicMock(name="app_scoped_provider")
        with patch(
            "app.main.build_app_session_provider", return_value=fake_provider
        ) as builder:

            async def drive():
                async with lifespan(app):
                    # Built exactly once at startup and exposed on app.state.
                    self.assertIs(app.state.session_provider, fake_provider)
                # Disposed exactly once at shutdown; state cleared.
                fake_provider.shutdown.assert_called_once()
                self.assertIsNone(app.state.session_provider)

            asyncio.run(drive())
            builder.assert_called_once()

    def test_lifespan_tolerates_unconfigured_provider(self):
        from app.main import app, lifespan

        with patch("app.main.build_app_session_provider", return_value=None):

            async def drive():
                async with lifespan(app):
                    self.assertIsNone(app.state.session_provider)
                # No provider => shutdown path is a safe no-op (no crash).

            asyncio.run(drive())


if __name__ == "__main__":
    unittest.main()
