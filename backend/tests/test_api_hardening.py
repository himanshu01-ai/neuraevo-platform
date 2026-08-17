"""API hardening tests (Sprint 24).

Prove the cross-cutting production-readiness guarantees without touching any
domain: every error path returns the one ``{"detail": ...}`` JSON contract, every
response carries a correlation id and a timing header, pagination is bounded, the
OpenAPI document is complete, and token responses are non-cacheable.

    PYTHONPATH=. python -m unittest tests.test_api_hardening
"""

import unittest

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.cache import no_store
from app.api.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PaginationDep
from app.core.request_context import REQUEST_ID_HEADER
from app.main import app, create_app


class ErrorContractTests(unittest.TestCase):
    """Every failure path returns the one JSON contract with a correlation id."""

    def setUp(self):
        # raise_server_exceptions=False so a 500 is returned (as in production)
        # rather than re-raised into the test.
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_404_is_json_detail_with_request_id(self):
        r = self.client.get("/api/v1/this-route-does-not-exist")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(r.headers["content-type"].startswith("application/json"))
        self.assertIn("detail", r.json())
        self.assertTrue(r.headers.get(REQUEST_ID_HEADER))

    def test_401_keeps_detail_and_www_authenticate(self):
        r = self.client.get("/api/v1/tasks")  # protected, no token
        self.assertEqual(r.status_code, 401)
        self.assertIn("detail", r.json())
        # The HTTPException's own headers survive the custom handler.
        self.assertIn("WWW-Authenticate", r.headers)
        self.assertTrue(r.headers.get(REQUEST_ID_HEADER))

    def test_422_keeps_fastapi_field_list_shape(self):
        r = self.client.post("/api/v1/auth/login", json={})
        self.assertEqual(r.status_code, 422)
        detail = r.json()["detail"]
        self.assertIsInstance(detail, list)
        self.assertIn("loc", detail[0])
        self.assertIn("msg", detail[0])
        self.assertIn("type", detail[0])

    def test_unhandled_exception_is_json_500_without_leaking(self):
        fresh = create_app()

        @fresh.get("/api/v1/_boom")
        def _boom():
            raise RuntimeError("secret internal detail")

        client = TestClient(fresh, raise_server_exceptions=False)
        r = client.get("/api/v1/_boom")
        self.assertEqual(r.status_code, 500)
        self.assertTrue(r.headers["content-type"].startswith("application/json"))
        body = r.json()
        self.assertIn("detail", body)
        # The internals are logged server-side, never returned.
        self.assertNotIn("secret", str(body))
        self.assertTrue(r.headers.get(REQUEST_ID_HEADER))


class RequestContextTests(unittest.TestCase):
    """Correlation id + timing on every response."""

    def setUp(self):
        self.client = TestClient(app)

    def test_request_id_is_generated_when_absent(self):
        r = self.client.get("/api/v1/health")
        self.assertTrue(r.headers.get(REQUEST_ID_HEADER))

    def test_supplied_request_id_is_echoed(self):
        r = self.client.get("/api/v1/health", headers={REQUEST_ID_HEADER: "trace-abc-123"})
        self.assertEqual(r.headers[REQUEST_ID_HEADER], "trace-abc-123")

    def test_malicious_request_id_is_replaced(self):
        # A header with disallowed characters is not echoed back verbatim.
        r = self.client.get("/api/v1/health", headers={REQUEST_ID_HEADER: "bad id\nwith spaces"})
        self.assertNotEqual(r.headers[REQUEST_ID_HEADER], "bad id\nwith spaces")

    def test_timing_header_present(self):
        r = self.client.get("/api/v1/health")
        self.assertIn("X-Response-Time-ms", r.headers)


class HealthTests(unittest.TestCase):
    def test_health_is_typed_and_ok(self):
        r = TestClient(app).get("/api/v1/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("service", body)
        self.assertIn("environment", body)


class PaginationBoundsTests(unittest.TestCase):
    """The shared bounded pagination dependency, in isolation."""

    def setUp(self):
        mini = FastAPI()

        @mini.get("/items")
        def items(pagination: PaginationDep):
            return {"skip": pagination.skip, "limit": pagination.limit}

        self.client = TestClient(mini)

    def test_defaults(self):
        self.assertEqual(
            self.client.get("/items").json(),
            {"skip": 0, "limit": DEFAULT_PAGE_SIZE},
        )

    def test_valid_values_pass(self):
        self.assertEqual(
            self.client.get("/items?skip=5&limit=10").json(),
            {"skip": 5, "limit": 10},
        )

    def test_negative_skip_is_422(self):
        self.assertEqual(self.client.get("/items?skip=-1").status_code, 422)

    def test_zero_limit_is_422(self):
        self.assertEqual(self.client.get("/items?limit=0").status_code, 422)

    def test_over_max_limit_is_422(self):
        self.assertEqual(
            self.client.get(f"/items?limit={MAX_PAGE_SIZE + 1}").status_code, 422
        )

    def test_paginated_endpoints_keep_skip_and_limit_params(self):
        # The dependency preserves the public parameter names, so the contract is
        # unchanged for existing clients.
        schema = app.openapi()
        for path in (
            "/api/v1/tasks/{task_id}/executions",
            "/api/v1/workflows/{workflow_id}/executions",
        ):
            params = {p["name"] for p in schema["paths"][path]["get"]["parameters"]}
            self.assertIn("skip", params, path)
            self.assertIn("limit", params, path)


class CacheControlTests(unittest.TestCase):
    def test_no_store_dependency_sets_header(self):
        mini = FastAPI()

        @mini.get("/token", dependencies=[Depends(no_store)])
        def token():
            return {"ok": True}

        r = TestClient(mini).get("/token")
        self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_login_and_refresh_declare_no_store(self):
        # The token-bearing routes carry the no-store dependency, so their
        # successful (token) responses are never cached. Asserted on the auth
        # router's own routes so the guarantee holds without a live login (or DB).
        from app.api.v1 import auth as auth_module

        def _dependency_calls(suffix: str):
            for route in auth_module.router.routes:
                if getattr(route, "path", "").endswith(suffix):
                    return {dep.call for dep in route.dependant.dependencies}
            return set()

        self.assertIn(no_store, _dependency_calls("/login"))
        self.assertIn(no_store, _dependency_calls("/refresh"))


class OpenApiTests(unittest.TestCase):
    def setUp(self):
        self.schema = app.openapi()

    def test_metadata_present(self):
        info = self.schema["info"]
        self.assertEqual(info["version"], "1.0.0")
        self.assertTrue(info.get("description"))
        self.assertGreaterEqual(len(self.schema.get("tags", [])), 20)

    def test_error_response_schema_documented(self):
        self.assertIn("ErrorResponse", self.schema["components"]["schemas"])

    def test_500_documented_on_endpoints(self):
        # The universal 500 response is advertised against ErrorResponse.
        responses = self.schema["paths"]["/api/v1/health"]["get"]["responses"]
        self.assertIn("500", responses)


if __name__ == "__main__":
    unittest.main()
