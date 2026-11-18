import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.api.errors import http_error_handler
from app.api.routes.auth import router
from app.infrastructure.repositories import InMemoryAuthRepository
from app.services.auth_service import AuthService
from tests.unit.test_auth_service import FakeOtpMailer


class AuthApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_verification_and_refresh_contract(self) -> None:
        mailer = FakeOtpMailer()
        service = AuthService(InMemoryAuthRepository(), mailer)
        app = FastAPI()
        app.state.auth_service = service
        app.add_exception_handler(401, http_error_handler)
        app.include_router(router)

        with patch(
            "app.services.auth_service.settings",
            SimpleNamespace(
                jwt_secret=SecretStr("a-test-secret-long-enough-for-hs256")
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                otp_response = await client.post(
                    "/v1/auth/login",
                    json={
                        "email": "person@example.com",
                        "consent": {
                            "version": "2026-01",
                            "accepted_age": True,
                        },
                    },
                )
                self.assertEqual(otp_response.status_code, 202)
                self.assertEqual(otp_response.json()["status"], "otp_sent")

                _, code = mailer.sent[-1]
                login_response = await client.post(
                    "/v1/auth/login",
                    json={"email": "person@example.com", "code": code},
                )
                self.assertEqual(login_response.status_code, 200)
                tokens = login_response.json()
                self.assertIn("access_token", tokens)

                refresh_response = await client.post(
                    "/v1/auth/refresh",
                    json={"refresh_token": tokens["refresh_token"]},
                )
                self.assertEqual(refresh_response.status_code, 200)
                self.assertNotEqual(
                    refresh_response.json()["refresh_token"],
                    tokens["refresh_token"],
                )

                reused_response = await client.post(
                    "/v1/auth/refresh",
                    json={"refresh_token": tokens["refresh_token"]},
                )
                self.assertEqual(reused_response.status_code, 401)

    async def test_google_login_returns_tokens(self) -> None:
        service = AuthService(InMemoryAuthRepository(), FakeOtpMailer())
        app = FastAPI()
        app.state.auth_service = service
        app.include_router(router)

        with (
            patch(
                "app.services.auth_service.settings",
                SimpleNamespace(
                    jwt_secret=SecretStr(
                        "a-test-secret-long-enough-for-hs256"
                    ),
                    google_client_id="test-google-client",
                ),
            ),
            patch.object(
                service,
                "_verify_google_token",
                side_effect=lambda token, client_id: {
                    "sub": token,
                    "email": "person@example.com",
                    "email_verified": True,
                },
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/v1/auth/login",
                    json={
                        "google_id_token": "google-sub-1",
                        "consent": {
                            "version": "2026-01",
                            "accepted_age": True,
                        },
                    },
                )
                conflict_response = await client.post(
                    "/v1/auth/login",
                    json={"google_id_token": "google-sub-2"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())
        self.assertEqual(conflict_response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
