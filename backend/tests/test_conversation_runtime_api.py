"""Endpoint tests for the Conversation Runtime API (Sprint 7.5, Sprint 8.3).

Two layers of tests:

* ``ConversationRuntimeAPITests`` mocks the whole ``ConversationRuntimeService``
  to cover pure HTTP concerns — success, request validation, ownership errors,
  provider failures, auth, and error-to-status mapping.
* ``ConversationRuntimeApiPersistenceTests`` (Sprint 8.3) mocks only the
  runtime service's collaborators and lets the real ``ConversationRuntimeService``
  run, proving the endpoint triggers memory persistence exactly once, after
  generation, and propagates persistence failures.

Both run in isolation via FastAPI dependency overrides — no database, provider,
or network is involved.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_conversation_runtime_api
"""

import unittest
import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_ai_context_engine_service,
    get_ai_orchestrator_service,
    get_conversation_runtime_service,
    get_current_user,
    get_memory_persistence_service,
    get_runtime_prompt_builder_service,
)
from app.main import app
from app.schemas.ai_response import AIResponse, AIResponseMetadata
from app.services.conversation_service import ConversationNotFoundError
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
)
from app.services.providers import (
    ConversationGenerationError,
    ConversationGenerationTimeoutError,
)


class ConversationRuntimeAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.conversation_id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.user = MagicMock(name="User")
        self.user.id = uuid.uuid4()

        self.ai_response = AIResponse(
            content="Hello there!",
            metadata=AIResponseMetadata(
                provider="test-provider",
                language="en",
                employee_id=self.employee_id,
                conversation_id=self.conversation_id,
                prompt_message_count=2,
            ),
        )
        self.service = MagicMock()
        self.service.execute.return_value = self.ai_response

        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_conversation_runtime_service] = (
            lambda: self.service
        )
        self.client = TestClient(app)
        self.url = f"/api/v1/conversations/{self.conversation_id}/runtime"

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _post(self, body=None):
        if body is None:
            body = {
                "employee_id": str(self.employee_id),
                "message": "What's next?",
            }
        return self.client.post(self.url, json=body)

    # --- success ---------------------------------------------------------
    def test_success_returns_200_and_ai_response(self):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["content"], "Hello there!")
        self.assertEqual(data["metadata"]["provider"], "test-provider")
        self.assertEqual(data["metadata"]["language"], "en")

    def test_success_delegates_to_service_once_with_args(self):
        self._post()
        self.service.execute.assert_called_once_with(
            self.user, self.employee_id, self.conversation_id, "What's next?"
        )

    # --- validation (422) ------------------------------------------------
    def test_empty_message_returns_422(self):
        response = self._post(
            {"employee_id": str(self.employee_id), "message": ""}
        )
        self.assertEqual(response.status_code, 422)
        self.service.execute.assert_not_called()

    def test_missing_employee_id_returns_422(self):
        response = self._post({"message": "hi"})
        self.assertEqual(response.status_code, 422)
        self.service.execute.assert_not_called()

    def test_invalid_employee_id_returns_422(self):
        response = self._post(
            {"employee_id": "not-a-uuid", "message": "hi"}
        )
        self.assertEqual(response.status_code, 422)
        self.service.execute.assert_not_called()

    # --- ownership / domain errors --------------------------------------
    def test_employee_not_found_returns_404(self):
        self.service.execute.side_effect = EmployeeNotFoundError("x")
        self.assertEqual(self._post().status_code, 404)

    def test_employee_access_denied_returns_403(self):
        self.service.execute.side_effect = EmployeeAccessDeniedError("x")
        self.assertEqual(self._post().status_code, 403)

    def test_conversation_not_found_returns_404(self):
        self.service.execute.side_effect = ConversationNotFoundError("x")
        self.assertEqual(self._post().status_code, 404)

    # --- provider failures ----------------------------------------------
    def test_provider_timeout_returns_504(self):
        self.service.execute.side_effect = ConversationGenerationTimeoutError(
            "slow"
        )
        self.assertEqual(self._post().status_code, 504)

    def test_provider_error_returns_502(self):
        self.service.execute.side_effect = ConversationGenerationError("boom")
        self.assertEqual(self._post().status_code, 502)

    # --- router contract -------------------------------------------------
    def test_unauthenticated_returns_401(self):
        # Remove the auth override so the real bearer scheme rejects the call.
        app.dependency_overrides.pop(get_current_user, None)
        response = self.client.post(
            self.url,
            json={"employee_id": str(self.employee_id), "message": "hi"},
        )
        self.assertEqual(response.status_code, 401)
        self.service.execute.assert_not_called()

    def test_openapi_exposes_runtime_endpoint(self):
        schema = app.openapi()
        path = "/api/v1/conversations/{conversation_id}/runtime"
        self.assertIn(path, schema["paths"])
        self.assertIn("post", schema["paths"][path])

    def test_persistence_failure_propagates_via_mocked_service(self):
        # A persistence error is not a domain/provider error, so the router does
        # not convert it — it propagates (surfaced as a 500 to the client).
        self.service.execute.side_effect = RuntimeError("db write failed")
        with self.assertRaises(RuntimeError):
            self._post()


class ConversationRuntimeApiPersistenceTests(unittest.TestCase):
    """Sprint 8.3 integration: HTTP -> real ConversationRuntimeService -> mocks.

    Overrides only the runtime service's collaborators (not the service itself),
    so the real ``execute`` runs end-to-end and the endpoint is proven to trigger
    memory persistence exactly once, after generation.
    """

    def setUp(self) -> None:
        self.conversation_id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.user = MagicMock(name="User")
        self.user.id = uuid.uuid4()
        self.ai_response = AIResponse(
            content="You have a 3pm sync.",
            metadata=AIResponseMetadata(
                provider="test-provider",
                language="en",
                employee_id=self.employee_id,
                conversation_id=self.conversation_id,
                prompt_message_count=2,
            ),
        )

        # Collaborators of the REAL ConversationRuntimeService.
        self.context_engine = MagicMock()
        self.context_engine.build_context.return_value = MagicMock(
            name="RuntimeAIContext"
        )
        self.prompt_builder = MagicMock()
        self.prompt_builder.build.return_value = MagicMock(name="PromptPackage")
        self.orchestrator = MagicMock()
        self.orchestrator.run.return_value = self.ai_response
        self.memory = MagicMock(name="MemoryPersistenceService")

        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_ai_context_engine_service] = (
            lambda: self.context_engine
        )
        app.dependency_overrides[get_runtime_prompt_builder_service] = (
            lambda: self.prompt_builder
        )
        app.dependency_overrides[get_ai_orchestrator_service] = (
            lambda: self.orchestrator
        )
        app.dependency_overrides[get_memory_persistence_service] = (
            lambda: self.memory
        )
        # get_conversation_runtime_service is NOT overridden -> the real service
        # is built from the mocked collaborators above.
        self.client = TestClient(app)
        self.url = f"/api/v1/conversations/{self.conversation_id}/runtime"
        self.body = {
            "employee_id": str(self.employee_id),
            "message": "What's next?",
        }

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_success_returns_200_ai_response(self):
        response = self.client.post(self.url, json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "You have a 3pm sync.")

    def test_messages_persisted_exactly_once(self):
        self.client.post(self.url, json=self.body)
        self.memory.persist.assert_called_once()

    def test_no_duplicate_persistence(self):
        self.client.post(self.url, json=self.body)
        self.assertEqual(self.memory.persist.call_count, 1)

    def test_persist_receives_expected_arguments(self):
        self.client.post(self.url, json=self.body)
        args = self.memory.persist.call_args.args
        self.assertIs(args[0], self.user)  # owner
        self.assertEqual(args[1], self.employee_id)
        self.assertEqual(args[2], self.conversation_id)
        self.assertEqual(args[3], "What's next?")  # current user input
        self.assertIs(args[4], self.ai_response)  # AIResponse instance

    def test_persistence_runs_after_generation(self):
        order = []
        self.orchestrator.run.side_effect = (
            lambda *a, **k: order.append("run") or self.ai_response
        )
        self.memory.persist.side_effect = lambda *a, **k: order.append("persist")
        self.client.post(self.url, json=self.body)
        self.assertEqual(order, ["run", "persist"])

    def test_persistence_failure_propagates(self):
        self.memory.persist.side_effect = RuntimeError("db write failed")
        with self.assertRaises(RuntimeError):
            self.client.post(self.url, json=self.body)

    def test_generation_failure_skips_persistence(self):
        self.orchestrator.run.side_effect = ConversationGenerationError("boom")
        response = self.client.post(self.url, json=self.body)
        self.assertEqual(response.status_code, 502)
        self.memory.persist.assert_not_called()


if __name__ == "__main__":
    unittest.main()
