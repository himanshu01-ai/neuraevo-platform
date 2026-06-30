"""Unit tests for the Sprint 7.3 AI Orchestrator.

Every collaborator is mocked (prompt builder, provider factory, provider), so
no database, network, or real provider is involved. The tests verify that the
orchestrator wires context -> prompt -> provider -> AIResponse correctly,
returns provider-agnostic DTOs, performs no post-processing, and propagates
provider errors.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_ai_orchestrator_service
"""

import unittest
import uuid
from unittest.mock import MagicMock

from app.schemas.ai_response import AIResponse
from app.schemas.prompt_package import (
    PromptMessage,
    PromptMetadata,
    PromptPackage,
)
from app.services.orchestrator.ai_orchestrator_service import (
    AIOrchestratorService,
)
from app.services.providers import (
    ConversationGenerationError,
    ConversationGenerationTimeoutError,
)


class AIOrchestratorServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.employee_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.package = PromptPackage(
            system_prompt="SYSTEM BLOCK",
            messages=[
                PromptMessage(role="user", content="Hi"),
                PromptMessage(role="assistant", content="Hello!"),
                PromptMessage(role="user", content="What's next?"),
            ],
            language="en",
            metadata=PromptMetadata(
                employee_id=self.employee_id,
                conversation_id=self.conversation_id,
                memory_count=1,
                message_count=2,
            ),
        )

        # Mocked collaborators.
        self.prompt_builder = MagicMock()
        self.prompt_builder.build.return_value = self.package
        self.provider = MagicMock()
        self.provider.name = "test-provider"
        self.provider.generate_reply.return_value = "Generated reply."
        self.provider_factory = MagicMock()
        self.provider_factory.get_provider.return_value = self.provider

        self.orchestrator = AIOrchestratorService(
            self.prompt_builder, self.provider_factory
        )
        # Context is opaque to the orchestrator (passed straight to the builder).
        self.context = MagicMock(name="RuntimeAIContext")

    def _run(self) -> AIResponse:
        return self.orchestrator.run(self.context)

    # --- happy path / wiring --------------------------------------------
    def test_run_returns_ai_response(self):
        self.assertIsInstance(self._run(), AIResponse)

    def test_builds_prompt_from_context(self):
        self._run()
        self.prompt_builder.build.assert_called_once_with(self.context)

    def test_resolves_provider_from_factory(self):
        self._run()
        self.provider_factory.get_provider.assert_called_once_with()

    def test_calls_provider_with_a_string_prompt(self):
        self._run()
        self.provider.generate_reply.assert_called_once()
        (arg,), _ = self.provider.generate_reply.call_args
        self.assertIsInstance(arg, str)

    def test_content_is_provider_output(self):
        self.assertEqual(self._run().content, "Generated reply.")

    # --- provider-agnostic metadata -------------------------------------
    def test_metadata_provider_name(self):
        self.assertEqual(self._run().metadata.provider, "test-provider")

    def test_metadata_language_from_package(self):
        self.assertEqual(self._run().metadata.language, "en")

    def test_metadata_ids_from_package(self):
        meta = self._run().metadata
        self.assertEqual(meta.employee_id, self.employee_id)
        self.assertEqual(meta.conversation_id, self.conversation_id)

    def test_metadata_prompt_message_count(self):
        self.assertEqual(self._run().metadata.prompt_message_count, 3)

    # --- prompt adapter --------------------------------------------------
    def test_rendered_prompt_contains_system_and_all_messages(self):
        self._run()
        (prompt,), _ = self.provider.generate_reply.call_args
        self.assertIn("SYSTEM BLOCK", prompt)
        self.assertIn("Hi", prompt)
        self.assertIn("Hello!", prompt)
        self.assertIn("What's next?", prompt)

    # --- error propagation ----------------------------------------------
    def test_provider_error_propagates(self):
        self.provider.generate_reply.side_effect = ConversationGenerationError(
            "boom"
        )
        with self.assertRaises(ConversationGenerationError):
            self._run()

    def test_provider_timeout_propagates(self):
        self.provider.generate_reply.side_effect = (
            ConversationGenerationTimeoutError("slow")
        )
        with self.assertRaises(ConversationGenerationTimeoutError):
            self._run()

    # --- no post-processing / no side effects ---------------------------
    def test_content_returned_verbatim_no_post_processing(self):
        self.provider.generate_reply.return_value = "  raw\noutput  "
        self.assertEqual(self._run().content, "  raw\noutput  ")

    def test_orchestrator_holds_only_injected_collaborators(self):
        # No session / repository — orchestration only.
        self.assertEqual(
            set(vars(self.orchestrator)), {"prompt_builder", "provider_factory"}
        )

    def test_reuses_injected_collaborators(self):
        self.assertIs(self.orchestrator.prompt_builder, self.prompt_builder)
        self.assertIs(
            self.orchestrator.provider_factory, self.provider_factory
        )

    def test_single_generation_per_run(self):
        self._run()
        self.assertEqual(self.prompt_builder.build.call_count, 1)
        self.assertEqual(self.provider_factory.get_provider.call_count, 1)
        self.assertEqual(self.provider.generate_reply.call_count, 1)


if __name__ == "__main__":
    unittest.main()
