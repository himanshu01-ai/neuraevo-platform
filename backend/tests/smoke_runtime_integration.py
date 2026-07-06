"""MANUAL / INTEGRATION smoke test — Sprint 12.14 Conversation Runtime over a
REAL Gemini Live session (NOT a unit test).

This is the Sprint 12.14 manual integration verification, not part of the
automated unit suite:

* The filename does NOT match the suite's discovery pattern (``test_*.py``), so
  ``python -m unittest discover -s tests -p "test_*.py"`` never collects it.
* It requires a real ``GEMINI_API_KEY`` and opens EXACTLY ONE real Gemini Live
  session through the full architecture:

      ConversationRuntime -> SessionService -> GeminiLiveSessionProvider
                          -> live messaging  -> Gemini Live API
                          -> execute_action  -> Sprint 11 pipeline
                             (planner -> registry -> permission -> tool exec)

  If the key is absent it skips gracefully.

Then it runs ONE continuous conversation — the user never changes modes:

    1. "Hello."                       (TEXT)
    2. "What time is it?"             (ACTION -> get_current_time tool)
    3. "Look at this image."          (VISUAL -> generated PNG)
    4. "Summarize this PDF."          (DOCUMENT -> text document; the Live
                                       API rejects inline application/pdf —
                                       see the step-4 comment)
    5. "Search today's AI news."      (ACTION -> web_search tool)
    6. "Continue talking."            (TEXT)

The runtime coordinates everything; the session stays alive; exactly one
session (and exactly one SDK Live connect) serves all six turns.

The Sprint 11 execution pipeline is driven through the REAL framework services
(PlannerService, ToolRegistry, PermissionService, ToolExecutionService) fed by
TEST-LOCAL providers defined below — a deterministic clock tool and a canned
"web_search" tool (no real web access) — because no production tool providers
exist yet (their composition-root seams are intentionally unfulfilled). Memory
coordination is exercised by the unit suite (it needs a database); this smoke
runs the runtime without memory services, which the runtime tolerates by
design.

The Live model is chosen from ``GEMINI_LIVE_MODEL`` (if set) or a list of
known Live-capable candidates — candidate selection happens once, at session
creation; it is model discovery, not a retry of a failed operation.

Run it manually (from ``backend/``):
    PYTHONPATH=. python -m unittest tests.smoke_runtime_integration
"""

import os
import struct
import time
import unittest
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path

# Best-effort load of the local .env into the process environment, exactly as a
# process manager / Render would (get_genai_client reads os.environ). CI that
# already exports GEMINI_API_KEY is unaffected; a missing .env is fine.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if _ENV_FILE.is_file():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

_HAS_KEY = bool(os.environ.get("GEMINI_API_KEY", "").strip())

# Known Live-capable models (API-key / Google AI Studio surface). Overridable
# without a code change via GEMINI_LIVE_MODEL.
_LIVE_MODEL_CANDIDATES = [
    model
    for model in [
        os.environ.get("GEMINI_LIVE_MODEL", "").strip() or None,
        # Verified live on 2026-07-06; the older gemini-2.0-flash-live-001 /
        # gemini-live-2.5-flash-preview are no longer served for API keys.
        "gemini-2.5-flash-native-audio-preview-09-2025",
        "gemini-2.0-flash-live-001",
        "gemini-live-2.5-flash-preview",
    ]
    if model
]


# =====================================================================
# Test-local media builders (deterministic, no external files)
# =====================================================================
def _minimal_png(width=64, height=64, rgb=(200, 30, 30)) -> bytes:
    """Build a valid solid-color RGB PNG in memory."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


@unittest.skipUnless(
    _HAS_KEY,
    "GEMINI_API_KEY not set — skipping manual runtime integration smoke test",
)
class RuntimeLiveIntegrationSmokeTest(unittest.TestCase):
    """One continuous multimodal conversation over exactly one Live session."""

    def test_one_continuous_multimodal_conversation(self):
        from app.core.dependencies import get_genai_client, get_provider_config
        from app.services.permissions import (
            PermissionProvider,
            PermissionRequest,
            PermissionResult,
            PermissionService,
        )
        from app.services.planner import PlannerProvider, PlannerService
        from app.services.planner.models import ExecutionPlan, PlanningStep
        from app.services.runtime import ConversationRuntime, RuntimeRequest
        from app.services.session import SessionService, SessionState
        from app.services.session.providers.gemini_live_provider import (
            ActionRequest,
            DocumentInput,
            DocumentType,
            GeminiLiveSessionProvider,
            VisualInput,
            VisualSource,
        )
        from app.services.tools import (
            ToolExecutionRequest,
            ToolExecutionResult,
            ToolExecutionService,
            ToolProvider,
        )
        from app.services.tools.registry import ToolRegistry

        # ---------------------------------------------------------------
        # Test-local Sprint 11 providers (the framework services are REAL;
        # only these leaf providers are smoke-local — no production tool
        # providers exist yet).
        # ---------------------------------------------------------------
        class _SmokePlanner(PlannerProvider):
            name = "smoke_planner"

            def create_plan(self, user_request: str) -> ExecutionPlan:
                return ExecutionPlan(
                    steps=[
                        PlanningStep(
                            tool_name=user_request,
                            description=f"Execute requested tool {user_request}",
                        )
                    ]
                )

        class _AllowAllPermissions(PermissionProvider):
            name = "smoke_allow_all"

            def check_permission(self, request: PermissionRequest):
                return PermissionResult(approved=True, reason="smoke test")

        class _ClockTool(ToolProvider):
            tool_name = "get_current_time"
            description = "Returns the current UTC time."

            def validate(self, request: ToolExecutionRequest) -> None:
                return None

            def execute(self, request: ToolExecutionRequest):
                now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                return ToolExecutionResult(success=True, output=f"It is {now}.")

        class _SearchTool(ToolProvider):
            tool_name = "web_search"
            description = "Returns canned search results (no real web access)."

            def validate(self, request: ToolExecutionRequest) -> None:
                return None

            def execute(self, request: ToolExecutionRequest):
                query = request.arguments.get("query", "")
                return ToolExecutionResult(
                    success=True,
                    output=(
                        f"Top canned results for '{query}': "
                        "1) AI assistants gain multimodal runtimes. "
                        "2) Voice-first agents reach production."
                    ),
                )

        class _DispatchingToolProvider(ToolProvider):
            """Routes execution to the registered tool named in the request."""

            tool_name = "smoke_dispatcher"
            description = "Dispatches to smoke-local tools by tool_name."

            def __init__(self, tools):
                self._tools = {tool.tool_name: tool for tool in tools}

            def validate(self, request: ToolExecutionRequest) -> None:
                if request.tool_name not in self._tools:
                    raise KeyError(request.tool_name)

            def execute(self, request: ToolExecutionRequest):
                self.validate(request)
                return self._tools[request.tool_name].execute(request)

        # ---------------------------------------------------------------
        # Real DI chain + real provider; ONE runtime for the whole session.
        # ---------------------------------------------------------------
        client = get_genai_client()
        config = get_provider_config()

        connects = {"n": 0}
        original_connect = client.aio.live.connect

        def _counting_connect(*args, **kwargs):
            connects["n"] += 1
            return original_connect(*args, **kwargs)

        client.aio.live.connect = _counting_connect

        tools = [_ClockTool(), _SearchTool()]
        provider = GeminiLiveSessionProvider(
            client,
            config,
            planner=PlannerService(_SmokePlanner()),
            tool_registry=ToolRegistry(tools),
            permissions=PermissionService(_AllowAllPermissions()),
            tool_execution=ToolExecutionService(_DispatchingToolProvider(tools)),
        )
        runtime = ConversationRuntime(
            session_service=SessionService(provider),
            live_messaging=provider,
        )

        conversation_id = uuid.uuid4()
        employee_id = uuid.uuid4()

        def request(**payload):
            return RuntimeRequest(
                conversation_id=conversation_id,
                employee_id=employee_id,
                **payload,
            )

        # ---------------------------------------------------------------
        # Live model discovery: the FIRST turn creates the one session; try
        # the candidates until one connects (selection, not retry — each
        # candidate is attempted exactly once, and later turns never create).
        # ---------------------------------------------------------------
        transcript = []
        first_response = None
        chosen_model = None
        for candidate in _LIVE_MODEL_CANDIDATES:
            started = time.perf_counter()
            try:
                first_response = runtime.execute(
                    request(
                        text="Hello. Please reply with one short sentence.",
                        metadata={"model": candidate},
                    )
                )
            except RuntimeError:
                continue
            chosen_model = candidate
            transcript.append(
                ("1. TEXT  'Hello.'", first_response, time.perf_counter() - started)
            )
            break
        self.assertIsNotNone(
            first_response,
            f"No Live-capable model connected (tried {_LIVE_MODEL_CANDIDATES})",
        )
        session_id = first_response.session_id
        # Each unavailable candidate consumed one (failed) connect attempt;
        # from here on the established session must be the ONLY live one and
        # no further SDK connect may ever happen.
        connects_after_discovery = connects["n"]

        # ---------------------------------------------------------------
        # 2. "What time is it?" — ACTION through the Sprint 11 pipeline.
        # ---------------------------------------------------------------
        started = time.perf_counter()
        time_response = runtime.execute(
            request(action=ActionRequest(tool_name="get_current_time", arguments={}))
        )
        transcript.append(
            ("2. ACTION 'What time is it?'", time_response, time.perf_counter() - started)
        )

        # ---------------------------------------------------------------
        # 3. "Look at this image." — VISUAL over the SAME session.
        # ---------------------------------------------------------------
        started = time.perf_counter()
        visual_response = runtime.execute(
            request(
                visual=VisualInput(
                    payload=_minimal_png(),
                    mime_type="image/png",
                    source=VisualSource.IMAGE,
                    metadata={
                        "prompt": (
                            "Look at this image. In one short sentence, what "
                            "is its dominant color?"
                        )
                    },
                )
            )
        )
        transcript.append(
            ("3. VISUAL 'Look at this image.'", visual_response, time.perf_counter() - started)
        )

        # ---------------------------------------------------------------
        # 4. "Summarize this PDF." — DOCUMENT over the SAME session.
        #
        # Verified live: the Gemini LIVE surface rejects inline
        # ``application/pdf`` (APIError 1007 invalid argument) even though the
        # non-live generate_content API accepts it, so this document turn
        # ships the document as ``text/plain`` — still a DOCUMENT-classified
        # request routed through the Sprint 12.12 document transport. Native
        # PDF over Live remains a provider/model capability question, not a
        # runtime one.
        # ---------------------------------------------------------------
        started = time.perf_counter()
        document_response = runtime.execute(
            request(
                document=DocumentInput(
                    payload=(
                        b"NeuraEvo Product Brief\n\n"
                        b"NeuraEvo builds voice-first AI employees. Every user "
                        b"owns one AI employee created through an "
                        b"interview-driven onboarding process. The employee "
                        b"talks, sees images, reads documents, and executes "
                        b"actions in one continuous conversation."
                    ),
                    mime_type="text/plain",
                    document_type=DocumentType.TXT,
                    metadata={
                        "prompt": "Summarize this document in one short sentence."
                    },
                )
            )
        )
        transcript.append(
            ("4. DOC   'Summarize this PDF.'", document_response, time.perf_counter() - started)
        )

        # ---------------------------------------------------------------
        # 5. "Search today's AI news." — ACTION through the Sprint 11 pipeline.
        # ---------------------------------------------------------------
        started = time.perf_counter()
        search_response = runtime.execute(
            request(
                action=ActionRequest(
                    tool_name="web_search",
                    arguments={"query": "today's AI news"},
                )
            )
        )
        transcript.append(
            ("5. ACTION 'Search today's AI news.'", search_response, time.perf_counter() - started)
        )

        # ---------------------------------------------------------------
        # 6. "Continue talking." — TEXT over the SAME session.
        # ---------------------------------------------------------------
        started = time.perf_counter()
        continue_response = runtime.execute(
            request(text="Continue talking: say goodbye in one short sentence.")
        )
        transcript.append(
            ("6. TEXT  'Continue talking.'", continue_response, time.perf_counter() - started)
        )

        # ---------------------------------------------------------------
        # Verification: one session, one connect, everything coordinated.
        # ---------------------------------------------------------------
        responses = [entry[1] for entry in transcript]
        self.assertEqual(
            connects["n"],
            connects_after_discovery,
            "no SDK Live connect may happen after the session is established",
        )
        for response in responses:
            self.assertEqual(
                response.session_id, session_id, "session must never change"
            )
        self.assertFalse(responses[0].metadata["session_reused"])
        for response in responses[1:]:
            self.assertTrue(response.metadata["session_reused"])

        for label, response, _ in transcript:
            if response.action_result is not None:
                self.assertTrue(response.action_result.success, label)
                self.assertTrue(response.action_result.result.strip(), label)
            else:
                self.assertTrue((response.text or "").strip(), label)

        state = provider.get_session(session_id).session.state
        self.assertEqual(state, SessionState.ACTIVE, "session must stay alive")

        # Coordinated close through the runtime (Session SPI underneath).
        self.assertTrue(runtime.close_conversation(request(text="bye")))
        self.assertEqual(
            provider.get_session(session_id).session.state, SessionState.CLOSED
        )

        # ---------------------------------------------------------------
        # Report.
        # ---------------------------------------------------------------
        print(
            f"\n[SMOKE] live model={chosen_model} | "
            f"sdk_connects={connects['n']} "
            f"({connects_after_discovery - 1} failed discovery attempt(s), "
            f"1 live session, 0 reconnects)"
        )
        print(f"[SMOKE] session_id={session_id} (one session for all turns)")
        for label, response, seconds in transcript:
            output = (
                response.action_result.result
                if response.action_result is not None
                else (response.text or "")
            )
            output = " ".join(output.split())
            if len(output) > 160:
                output = output[:157] + "..."
            print(f"[SMOKE] {label} | {seconds:6.2f}s | {output}")


if __name__ == "__main__":
    unittest.main()
