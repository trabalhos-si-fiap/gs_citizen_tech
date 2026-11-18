import json
import unittest
from uuid import UUID

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from app.api.errors import validation_error_handler
from app.api.middleware import correlation_id_middleware
from app.main import app


class ApiFoundationTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_endpoint_matches_openapi_contract(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        UUID(response.headers["X-Correlation-ID"])

    async def test_legacy_health_endpoint_remains_available(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    async def test_valid_correlation_id_is_returned(self) -> None:
        correlation_id = "8d11c206-f849-4631-9c0f-d27a23fc7634"
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/health",
                headers={"X-Correlation-ID": correlation_id},
            )

        self.assertEqual(response.headers["X-Correlation-ID"], correlation_id)

    async def test_invalid_correlation_id_is_replaced(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/health",
                headers={"X-Correlation-ID": "invalid value"},
            )

        self.assertNotEqual(response.headers["X-Correlation-ID"], "invalid value")
        UUID(response.headers["X-Correlation-ID"])

    async def test_http_errors_use_standard_error_shape(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/route-that-does-not-exist")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")
        self.assertIn("correlation_id", response.json()["error"])

    async def test_validation_error_uses_standard_error_shape(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/auth/login",
                "headers": [],
                "query_string": b"",
                "server": ("test", 80),
                "client": ("test", 1234),
                "scheme": "http",
            }
        )
        request.state.correlation_id = "8d11c206-f849-4631-9c0f-d27a23fc7634"
        exception = RequestValidationError(
            [
                {
                    "type": "missing",
                    "loc": ("body", "email"),
                    "msg": "Field required",
                }
            ]
        )

        response = await validation_error_handler(request, exception)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            json.loads(response.body),
            {
                "error": {
                    "code": "validation_error",
                    "message": "A requisição contém dados inválidos.",
                    "field": "email",
                    "correlation_id": request.state.correlation_id,
                }
            },
        )


if __name__ == "__main__":
    unittest.main()
