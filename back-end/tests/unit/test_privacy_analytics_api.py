import base64
import hashlib
import hmac
import json
import time
import unittest
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import settings
from app.main import app
from app.models.auth import AuthUser


JWT_SECRET = "privacy-test-secret-that-is-at-least-32-bytes"


def access_token(user_id: int = 44) -> str:
    def segment(value: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(value, separators=(",", ":")).encode("utf-8")
        ).rstrip(b"=").decode("ascii")

    header = segment({"alg": "HS256", "typ": "JWT"})
    payload = segment(
        {
            "sub": str(user_id),
            "role": "citizen",
            "exp": int(time.time()) + 60,
        }
    )
    signing_input = f"{header}.{payload}"
    signature = hmac.new(
        JWT_SECRET.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    )
    signature_segment = base64.urlsafe_b64encode(signature.digest())
    return f"{signing_input}.{signature_segment.rstrip(b'=').decode('ascii')}"


class PrivacyAnalyticsApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.previous_jwt_secret = settings.jwt_secret
        settings.jwt_secret = SecretStr(JWT_SECRET)
        self.auth_repository = app.state.auth_service._repository
        self.auth_repository._lock.acquire()
        try:
            self.auth_repository._users_by_email.clear()
            self.auth_repository._users_by_id.clear()
            self.auth_repository._users_by_google_sub.clear()
            self.auth_repository._google_sub_by_user.clear()
            self.auth_repository._challenges.clear()
            self.auth_repository._refresh_tokens.clear()
            self.auth_repository._next_user_id = 1
        finally:
            self.auth_repository._lock.release()
        self.auth_repository._users_by_id[44] = AuthUser(
            id=44,
            email="cidadao@example.com",
            role="citizen",
            consent_version="v1",
            created_at=datetime.now(timezone.utc),
        )
        self.auth_repository._users_by_email["cidadao@example.com"] = (
            self.auth_repository._users_by_id[44]
        )
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )
        self.headers = {"Authorization": f"Bearer {access_token()}"}

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        settings.jwt_secret = self.previous_jwt_secret

    async def test_account_get_update_export_and_delete(self) -> None:
        response = await self.client.get("/v1/me", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "cidadao@example.com")

        response = await self.client.patch(
            "/v1/me",
            json={"email": "corrigido@example.com"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "corrigido@example.com")

        response = await self.client.get("/v1/me/export", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["account"]["email"],
            "corrigido@example.com",
        )
        self.assertIn("reports", response.json())
        self.assertIn("notification_devices", response.json())

        response = await self.client.delete("/v1/me", headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "deletion_started")

    async def test_public_metrics_support_json_csv_and_period_validation(self) -> None:
        response = await self.client.get("/v1/public/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("totals", response.json())
        self.assertIn("by_agency", response.json())

        response = await self.client.get(
            "/v1/public/metrics",
            params={"format": "csv"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/csv"))
        self.assertIn("agency_id", response.text)

        response = await self.client.get(
            "/v1/public/metrics",
            params={"from": "2026-12-01", "to": "2026-11-01"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
