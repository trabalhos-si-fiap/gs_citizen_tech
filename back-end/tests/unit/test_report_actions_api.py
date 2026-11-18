import base64
import hashlib
import hmac
import json
import time
import unittest
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import settings
from app.main import app
from app.models.reports import ReportStatus


JWT_SECRET = "actions-test-secret-that-is-at-least-32-bytes"


def access_token(user_id: int = 72, role: str = "citizen") -> str:
    def segment(value: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(value, separators=(",", ":")).encode("utf-8")
        ).rstrip(b"=").decode("ascii")

    header = segment({"alg": "HS256", "typ": "JWT"})
    payload = segment(
        {"sub": str(user_id), "role": role, "exp": int(time.time()) + 60}
    )
    signing_input = f"{header}.{payload}"
    signature = hmac.new(
        JWT_SECRET.encode("ascii"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    )
    encoded_signature = base64.urlsafe_b64encode(signature.digest())
    return f"{signing_input}.{encoded_signature.rstrip(b'=').decode('ascii')}"


class ReportActionsApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.previous_jwt_secret = settings.jwt_secret
        settings.jwt_secret = SecretStr(JWT_SECRET)
        self.previous_keys = settings.agency_api_keys
        settings.agency_api_keys = "test-agency-key"
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        settings.jwt_secret = self.previous_jwt_secret
        settings.agency_api_keys = self.previous_keys

    async def test_flag_moves_report_to_moderation_and_is_idempotent_per_user(self) -> None:
        from datetime import datetime, timezone
        from app.models.reports import NewReport
        from app.models.taxonomy import ReportCategory

        report_id = uuid4()
        repository = app.state.report_service._repository
        repository.create(
            NewReport(
                id=report_id,
                description="Buraco",
                has_photo=False,
                category=ReportCategory.URBAN_RISK,
                latitude=-23.55,
                longitude=-46.63,
                location_accuracy_m=None,
                anonymous=False,
                client_created_at=datetime.now(timezone.utc),
                correlation_id=uuid4(),
                user_id=72,
                requester_user_id=72,
            )
        )
        headers = {"Authorization": f"Bearer {access_token()}"}
        response = await self.client.post(
            f"/v1/reports/{report_id}/flag",
            json={"reason": "falso", "note": "Dados inconsistentes"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 202)
        detail = repository.get_detail(report_id)
        self.assertEqual(detail.triage_state.value, "in_moderation")

        response = await self.client.post(
            f"/v1/reports/{report_id}/flag",
            json={"reason": "falso"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 409)

    async def test_agency_status_requires_api_key_and_justification(self) -> None:
        report_id = uuid4()
        response = await self.client.post(
            f"/v1/agency/reports/{report_id}/status",
            json={"action": "resolved", "justification": "Serviço concluído"},
        )
        self.assertEqual(response.status_code, 403)

        response = await self.client.post(
            f"/v1/agency/reports/{report_id}/status",
            json={"action": "resolved"},
            headers={"X-API-Key": "test-agency-key"},
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
