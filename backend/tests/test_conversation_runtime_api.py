"""Endpoint tests for the Sprint 7.5 Conversation Runtime API.

The router is tested in isolation via FastAPI dependency overrides: the current
user and the ``ConversationRuntimeService`` are replaced with test doubles, so
no database, provider, or real service runs. These cover success, request
validation, ownership errors, and provider failures, and confirm the router
delegates (no business logic) and maps domain errors to HTTP status codes.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_conversation_runtime_api
"""

import unittest
import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_conversation_runtime_service,
    get_current_user,
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


if __name__ == "__main__":
    unittest.main()
