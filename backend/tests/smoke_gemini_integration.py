"""MANUAL / INTEGRATION smoke test — real Gemini API (NOT a unit test).

This is a production verification test, not part of the automated unit suite:

* The filename does NOT match the suite's discovery pattern (``test_*.py``), so
  ``python -m unittest discover -s tests -p "test_*.py"`` never collects it.
* It requires a real ``GEMINI_API_KEY`` and makes ONE real ``generate_content``
  call through the entire dependency-injection chain
  (MultimodalAIService → GeminiProvider → GeminiAdapter → google-genai SDK →
  Gemini API). If the key is absent it skips gracefully.
* It uses ONLY the default ``ProviderConfig`` — the model is never overridden.

No retries, no streaming, no planner, no runtime, no tool execution.

Run it manually (from ``backend/``):
    PYTHONPATH=. python -m unittest tests.smoke_gemini_integration
"""

import os
import unittest
import uuid
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


@unittest.skipUnless(
    _HAS_KEY, "GEMINI_API_KEY not set — skipping manual Gemini integration smoke test"
)
class GeminiIntegrationSmokeTest(unittest.TestCase):
    """One real end-to-end call proving the live Gemini integration works."""

    def test_real_generate_content_through_di_chain(self):
        from app.core.dependencies import (
            get_genai_client,
            get_gemini_adapter,
            get_provider_config,
            get_gemini_provider,
        )
        from app.services.multimodal_ai import MultimodalAIService
        from app.services.multimodal_ai.models import MultimodalAIRequest
        from app.services.multimodal_ai.adapters.gemini_adapter import (
            MODEL_METADATA_KEY,
        )
        from app.services.interaction.models import InteractionType

        # Real DI chain — no manual adapter construction, no bypass.
        client = get_genai_client()
        adapter = get_gemini_adapter(client)
        config = get_provider_config()
        provider = get_gemini_provider(adapter, config)
        service = MultimodalAIService(provider)

        # Count SDK calls (real method still runs) to assert exactly one call.
        calls = {"n": 0}
        original = client.models.generate_content

        def _counting(*args, **kwargs):
            calls["n"] += 1
            return original(*args, **kwargs)

        client.models.generate_content = _counting

        # ONLY the default ProviderConfig model — never overridden.
        request = MultimodalAIRequest(
            interaction_type=InteractionType.TEXT,
            normalized_content="Reply only with:\n\nSmoke Test Successful",
            conversation_id=uuid.uuid4(),
            employee_id=uuid.uuid4(),
            metadata={MODEL_METADATA_KEY: config.default_model},
        )

        result = service.generate_response(request)

        # Response mapping works: a provider-independent DTO with real text.
        from app.services.multimodal_ai.models import MultimodalAIResponse

        self.assertIsInstance(result, MultimodalAIResponse)
        self.assertTrue(
            result.response_text.strip(), "expected a non-empty Gemini response"
        )
        self.assertEqual(result.metadata, {})
        # Exactly one SDK call — no retries, no duplication.
        self.assertEqual(calls["n"], 1)

        print(
            "\n[SMOKE] model="
            + config.default_model
            + " | response_text="
            + repr(result.response_text)
            + " | sdk_calls="
            + str(calls["n"])
        )


if __name__ == "__main__":
    unittest.main()
