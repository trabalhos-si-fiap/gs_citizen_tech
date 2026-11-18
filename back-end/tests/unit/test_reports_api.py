import random
import base64
import hashlib
import hmac
import json
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import settings
from app.main import app

JWT_SECRET = "unit-test-secret-that-is-at-least-32-bytes"


def create_access_token(user_id: int, role: str = "citizen") -> str:
    def encode_segment(value: dict[str, object]) -> str:
        encoded = base64.urlsafe_b64encode(
            json.dumps(value, separators=(",", ":")).encode("utf-8")
        )
        return encoded.rstrip(b"=").decode("ascii")

    header = encode_segment({"alg": "HS256", "typ": "JWT"})
    payload = encode_segment(
        {
            "sub": str(user_id),
            "role": role,
            "exp": int(time.time()) + 60,
        }
    )
    signing_input = f"{header}.{payload}"
    signature = hmac.new(
        JWT_SECRET.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    )
    encoded_signature = base64.urlsafe_b64encode(signature.digest())
    return f"{signing_input}.{encoded_signature.rstrip(b'=').decode('ascii')}"


class ReportApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.previous_jwt_secret = settings.jwt_secret
        settings.jwt_secret = SecretStr(JWT_SECRET)
        self.smtp_patcher = patch("app.infrastructure.mailer.smtplib.SMTP")
        self.smtp_patcher.start()
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        self.smtp_patcher.stop()
        settings.jwt_secret = self.previous_jwt_secret

    def report_payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": str(uuid4()),
            "description": "Buraco na via",
            "lat": round(random.uniform(-60, 60), 5),
            "lon": round(random.uniform(-170, 170), 5),
            "client_created_at": datetime.now(timezone.utc).isoformat(),
        }
        payload.update(overrides)
        return payload

    async def post_report(
        self,
        payload: dict[str, object],
        *,
        user_id: int = 23,
        role: str = "citizen",
        token: str | None = None,
    ):
        access_token = token or create_access_token(user_id, role)
        return await self.client.post(
            "/v1/reports",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    async def test_report_creation_requires_authentication(self) -> None:
        response = await self.client.post(
            "/v1/reports",
            json=self.report_payload(),
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "unauthorized")
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    async def test_device_registration_and_removal_require_authentication(self) -> None:
        token = f"test-device-{uuid4()}"
        headers = {
            "Authorization": f"Bearer {create_access_token(91)}",
        }

        registered = await self.client.put(
            "/v1/me/devices",
            json={"push_token": token, "platform": "ios"},
            headers=headers,
        )
        removed = await self.client.request(
            "DELETE",
            "/v1/me/devices",
            json={"push_token": token, "platform": "ios"},
            headers=headers,
        )
        unauthorized = await self.client.put(
            "/v1/me/devices",
            json={"push_token": token, "platform": "ios"},
        )

        self.assertEqual(registered.status_code, 204)
        self.assertEqual(removed.status_code, 204)
        self.assertEqual(unauthorized.status_code, 401)

    async def test_creation_returns_201_then_200_for_idempotent_retry(self) -> None:
        payload = self.report_payload()

        created = await self.post_report(payload)
        repeated = await self.post_report(payload)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(created.json()["id"], payload["id"])
        self.assertEqual(created.json()["protocol"], repeated.json()["protocol"])
        self.assertEqual(created.json()["status"], "recebido")
        self.assertEqual(
            created.json()["triage_state"],
            "pending_classification",
        )

    async def test_detail_returns_report_and_timeline(self) -> None:
        payload = self.report_payload(
            category="risco_urbano",
            anonymous=True,
        )
        created = await self.post_report(payload, user_id=51)
        report_id = payload["id"]

        detail = await self.client.get(
            f"/v1/reports/{report_id}",
            headers={
                "Authorization": f"Bearer {create_access_token(52)}",
            },
        )
        missing = await self.client.get(
            f"/v1/reports/{uuid4()}",
            headers={
                "Authorization": f"Bearer {create_access_token(52)}",
            },
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], report_id)
        self.assertEqual(detail.json()["category"], "risco_urbano")
        self.assertTrue(detail.json()["anonymous"])
        self.assertEqual(
            detail.json()["timeline"][0]["type"],
            "recebido",
        )
        self.assertEqual(missing.status_code, 404)

    async def test_triage_correction_routes_to_specific_agency(self) -> None:
        payload = self.report_payload(description="Vazamento de esgoto na rua.")
        created = await self.post_report(payload, user_id=71)
        report_id = payload["id"]
        headers = {
            "Authorization": f"Bearer {create_access_token(71)}",
        }

        detail = await self.client.get(
            f"/v1/reports/{report_id}",
            headers=headers,
        )
        triaged = await self.client.post(
            f"/v1/reports/{report_id}/triage",
            json={
                "action": "correct",
                "category": "risco_urbano",
                "subcategory": "esgoto_vazamento",
            },
            headers=headers,
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(
            detail.json()["classification"]["category"],
            "a_classificar",
        )
        self.assertEqual(triaged.status_code, 200)
        self.assertEqual(triaged.json()["status"], "encaminhado")
        self.assertEqual(
            triaged.json()["agency"]["id"],
            "saneamento-demo",
        )
        self.assertEqual(
            triaged.json()["classification"]["source"],
            "user",
        )
        self.assertEqual(
            triaged.json()["timeline"][-1]["type"],
            "encaminhado",
        )
        repeated = await self.client.post(
            f"/v1/reports/{report_id}/triage",
            json={"action": "confirm"},
            headers=headers,
        )
        self.assertEqual(repeated.status_code, 409)

    async def test_only_requester_can_submit_triage(self) -> None:
        payload = self.report_payload()
        await self.post_report(payload, user_id=72)

        response = await self.client.post(
            f"/v1/reports/{payload['id']}/triage",
            json={"action": "confirm"},
            headers={
                "Authorization": f"Bearer {create_access_token(73)}",
            },
        )

        self.assertEqual(response.status_code, 403)

    async def test_my_reports_paginates_and_includes_anonymous_reports(self) -> None:
        owned_ids = []
        for anonymous in (False, True, False):
            payload = self.report_payload(anonymous=anonymous)
            response = await self.post_report(payload, user_id=61)
            self.assertEqual(response.status_code, 201)
            owned_ids.append(payload["id"])
        other_payload = self.report_payload()
        other_response = await self.post_report(other_payload, user_id=62)
        self.assertEqual(other_response.status_code, 201)

        headers = {
            "Authorization": f"Bearer {create_access_token(61)}",
        }
        first_page = await self.client.get(
            "/v1/me/reports",
            params={"limit": 2},
            headers=headers,
        )
        second_page = await self.client.get(
            "/v1/me/reports",
            params={
                "limit": 2,
                "cursor": first_page.json()["next_cursor"],
            },
            headers=headers,
        )

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.json()["items"]), 2)
        self.assertIsNotNone(first_page.json()["next_cursor"])
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(len(second_page.json()["items"]), 1)
        received_ids = {
            item["id"]
            for item in first_page.json()["items"] + second_page.json()["items"]
        }
        self.assertEqual(received_ids, set(owned_ids))
        self.assertNotIn(other_payload["id"], received_ids)
        self.assertIsNone(second_page.json()["next_cursor"])

    async def test_reused_report_id_from_another_user_is_rejected(self) -> None:
        payload = self.report_payload()
        created = await self.post_report(payload, user_id=23)

        conflict = await self.post_report(payload, user_id=24)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(conflict.status_code, 409)

    async def test_non_citizen_role_cannot_create_report(self) -> None:
        response = await self.post_report(
            self.report_payload(),
            role="agency",
        )

        self.assertEqual(response.status_code, 403)

    async def test_photo_storage_failure_does_not_create_report(self) -> None:
        payload = self.report_payload(description=None, has_photo=True)

        failed_upload = await self.post_report(payload)
        payload["description"] = "Buraco na via"
        payload["has_photo"] = False
        retry_without_photo = await self.post_report(payload)

        self.assertEqual(failed_upload.status_code, 503)
        self.assertEqual(retry_without_photo.status_code, 201)

    async def test_comments_are_public_and_require_authentication_to_create(self) -> None:
        payload = self.report_payload()
        created = await self.post_report(payload, user_id=31)
        report_id = payload["id"]

        unauthenticated = await self.client.post(
            f"/v1/reports/{report_id}/comments",
            json={"content": "Vi a situação hoje."},
        )
        self.assertEqual(unauthenticated.status_code, 401)

        posted = await self.client.post(
            f"/v1/reports/{report_id}/comments",
            json={"content": "  Vi a situação hoje.  "},
            headers={
                "Authorization": f"Bearer {create_access_token(32)}",
            },
        )
        listed = await self.client.get(f"/v1/reports/{report_id}/comments")

        self.assertEqual(created.status_code, 201)
        self.assertEqual(posted.status_code, 201)
        self.assertEqual(posted.json()["content"], "Vi a situação hoje.")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["count"], 1)
        self.assertNotIn("user_id", listed.json()["items"][0])

    async def test_vi_isso_confirmation_excludes_author_and_is_unique(self) -> None:
        payload = self.report_payload()
        created = await self.post_report(payload, user_id=41)
        report_id = payload["id"]

        author_confirmation = await self.client.post(
            f"/v1/reports/{report_id}/confirm",
            headers={
                "Authorization": f"Bearer {create_access_token(41)}",
            },
        )
        first_confirmation = await self.client.post(
            f"/v1/reports/{report_id}/confirm",
            headers={
                "Authorization": f"Bearer {create_access_token(42)}",
            },
        )
        repeated_confirmation = await self.client.post(
            f"/v1/reports/{report_id}/confirm",
            headers={
                "Authorization": f"Bearer {create_access_token(42)}",
            },
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(author_confirmation.status_code, 403)
        self.assertEqual(first_confirmation.status_code, 200)
        self.assertEqual(first_confirmation.json()["confirmation_count"], 1)
        self.assertEqual(repeated_confirmation.status_code, 409)


if __name__ == "__main__":
    unittest.main()
