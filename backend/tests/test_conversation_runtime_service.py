"""Unit tests for the Sprint 7.4 Conversation Runtime Service.

Every collaborator is mocked (context engine, prompt builder, orchestrator), so
no database, network, or real service is involved. The tests verify that
``execute`` coordinates context -> prompt -> orchestrator (each exactly once, in
order), returns the orchestrator's ``AIResponse`` unchanged, propagates
collaborator exceptions, holds no state, and is DI-constructible.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_conversation_runtime_service
"""

import unittest
import uuid
from unittest.mock import MagicMock

from app.schemas.ai_response import AIResponse, AIResponseMetadata
from app.services.employee_service import EmployeeAccessDeniedError
from app.services.providers import ConversationGenerationError
from app.services.runtime.conversation_runtime_service import (
    ConversationRuntimeService,
)


class ConversationRuntimeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = MagicMock(name="User")
        self.employee_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.user_input = "What's my next meeting?"

        # Opaque intermediates (the runtime service passes them through).
        self.context = MagicMock(name="RuntimeAIContext")
        self.package = MagicMock(name="PromptPackage")
        self.response = AIResponse(
            content="ok",
            metadata=AIResponseMetadata(
                provider="test-provider",
                language="en",
                employee_id=self.employee_id,
                conversation_id=self.conversation_id,
                prompt_message_count=1,
            ),
        )

        self.context_engine = MagicMock()
        self.context_engine.build_context.return_value = self.context
        self.prompt_builder = MagicMock()
        self.prompt_builder.build.return_value = self.package
        self.orchestrator = MagicMock()
        self.orchestrator.run.return_value = self.response
        self.memory_persistence = MagicMock()

        self.runtime = ConversationRuntimeService(
            self.context_engine,
            self.prompt_builder,
            self.orchestrator,
            self.memory_persistence,
        )

    def _execute(self) -> AIResponse:
        return self.runtime.execute(
            self.owner,
            self.employee_id,
            self.conversation_id,
            self.user_input,
        )

    # --- return value ----------------------------------------------------
    def test_returns_orchestrator_response_unchanged(self):
        result = self._execute()
        self.assertIsInstance(result, AIResponse)
        self.assertIs(result, self.response)

    # --- each collaborator called exactly once, with right args ----------
    def test_calls_context_engine_once_with_args(self):
        self._execute()
        self.context_engine.build_context.assert_called_once_with(
            self.owner, self.employee_id, self.conversation_id, self.user_input
        )

    def test_calls_prompt_builder_once_with_context(self):
        self._execute()
        self.prompt_builder.build.assert_called_once_with(self.context)

    def test_calls_orchestrator_once_with_context(self):
        self._execute()
        self.orchestrator.run.assert_called_once_with(self.context)

    def test_each_collaborator_called_exactly_once(self):
        self._execute()
        self.assertEqual(self.context_engine.build_context.call_count, 1)
        self.assertEqual(self.prompt_builder.build.call_count, 1)
        self.assertEqual(self.orchestrator.run.call_count, 1)

    # --- call order ------------------------------------------------------
    def test_call_order_context_then_prompt_then_orchestrator(self):
        order = []
        self.context_engine.build_context.side_effect = (
            lambda *a, **k: order.append("context") or self.context
        )
        self.prompt_builder.build.side_effect = (
            lambda *a, **k: order.append("prompt") or self.package
        )
        self.orchestrator.run.side_effect = (
            lambda *a, **k: order.append("orchestrator") or self.response
        )
        self._execute()
        self.assertEqual(order, ["context", "prompt", "orchestrator"])

    def test_builder_and_orchestrator_receive_same_context(self):
        self._execute()
        ctx_to_builder = self.prompt_builder.build.call_args[0][0]
        ctx_to_orchestrator = self.orchestrator.run.call_args[0][0]
        self.assertIs(ctx_to_builder, self.context)
        self.assertIs(ctx_to_orchestrator, self.context)

    # --- exception propagation (and short-circuit) -----------------------
    def test_context_engine_exception_propagates(self):
        self.context_engine.build_context.side_effect = (
            EmployeeAccessDeniedError("denied")
        )
        with self.assertRaises(EmployeeAccessDeniedError):
            self._execute()
        self.prompt_builder.build.assert_not_called()
        self.orchestrator.run.assert_not_called()

    def test_prompt_builder_exception_propagates(self):
        self.prompt_builder.build.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self._execute()
        self.orchestrator.run.assert_not_called()

    def test_orchestrator_exception_propagates(self):
        self.orchestrator.run.side_effect = ConversationGenerationError("boom")
        with self.assertRaises(ConversationGenerationError):
            self._execute()

    # --- statelessness / no writes / no repos ----------------------------
    def test_service_is_stateless_no_session_or_repository(self):
        # Holds only the injected collaborators — no session, no repo.
        self.assertEqual(
            set(vars(self.runtime)),
            {
                "context_engine",
                "prompt_builder",
                "orchestrator",
                "memory_persistence",
            },
        )

    def test_reuses_injected_collaborators(self):
        self.assertIs(self.runtime.context_engine, self.context_engine)
        self.assertIs(self.runtime.prompt_builder, self.prompt_builder)
        self.assertIs(self.runtime.orchestrator, self.orchestrator)

    # --- dependency injection -------------------------------------------
    def test_di_provider_constructs_service(self):
        from app.core.dependencies import get_conversation_runtime_service

        service = get_conversation_runtime_service(
            self.context_engine,
            self.prompt_builder,
            self.orchestrator,
            self.memory_persistence,
        )
        self.assertIsInstance(service, ConversationRuntimeService)
        self.assertIs(service.context_engine, self.context_engine)
        self.assertIs(service.prompt_builder, self.prompt_builder)
        self.assertIs(service.orchestrator, self.orchestrator)
        self.assertIs(service.memory_persistence, self.memory_persistence)


if __name__ == "__main__":
    unittest.main()
