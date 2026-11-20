import random
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import settings
from app.core.geo import haversine_m
from app.main import app
from test_reports_api import JWT_SECRET, create_access_token

PUBLIC_FIELDS = {
    "id",
    "group_id",
    "status",
    "category",
    "subcategory",
    "lat",
    "lon",
    "confirmation_count",
    "received_at",
    "distance_m",
}


class NearbyApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.previous_jwt_secret = settings.jwt_secret
        settings.jwt_secret = SecretStr(JWT_SECRET)
        self.smtp_patcher = patch("app.infrastructure.mailer.smtplib.SMTP")
        self.smtp_patcher.start()
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        # Coordenada isolada por teste: o repositório em memória é compartilhado.
        self.lat = round(random.uniform(-60, 60), 4)
        self.lon = round(random.uniform(-170, 170), 4)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        self.smtp_patcher.stop()
        settings.jwt_secret = self.previous_jwt_secret

    async def create_report(
        self, lat: float, lon: float, address: str | None = None
    ) -> str:
        report_id = str(uuid4())
        response = await self.client.post(
            "/v1/reports",
            json={
                "id": report_id,
                "description": "Buraco na via, perto do meu endereço",
                "category": "risco_urbano",
                "lat": lat,
                "lon": lon,
                "client_created_at": datetime.now(timezone.utc).isoformat(),
                "address": address,
            },
            headers={"Authorization": f"Bearer {create_access_token(51)}"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return report_id

    async def nearby(self, **params: object):
        return await self.client.get(
            "/v1/reports/nearby",
            params={"lat": self.lat, "lon": self.lon, **params},
        )

    async def test_is_public_and_returns_minimal_fields(self) -> None:
        report_id = await self.create_report(self.lat + 0.001, self.lon)

        response = await self.nearby()

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual([item["id"] for item in body["items"]], [report_id])
        item = body["items"][0]
        self.assertLessEqual(set(item), PUBLIC_FIELDS)
        self.assertNotIn("description", item)
        self.assertNotIn("protocol", item)
        self.assertAlmostEqual(item["distance_m"], 111, delta=2)
        self.assertIsNone(body["next_cursor"])

    async def test_address_is_not_exposed_on_the_public_map(self) -> None:
        await self.create_report(
            self.lat + 0.001, self.lon, address="Rua Exemplo, 123 – Bairro, Cidade"
        )

        item = (await self.nearby()).json()["items"][0]

        self.assertNotIn("address", item)
        self.assertLessEqual(set(item), PUBLIC_FIELDS)

    async def test_returns_classified_subcategory(self) -> None:
        report_id = await self.create_report(self.lat + 0.001, self.lon)
        triage = await self.client.post(
            f"/v1/reports/{report_id}/triage",
            json={
                "action": "correct",
                "category": "risco_urbano",
                "subcategory": "buraco_via",
            },
            headers={"Authorization": f"Bearer {create_access_token(51)}"},
        )
        self.assertEqual(triage.status_code, 200, triage.text)

        item = (await self.nearby()).json()["items"][0]

        self.assertEqual(item["subcategory"], "buraco_via")

    async def test_coordinates_are_coarsened_for_privacy(self) -> None:
        await self.create_report(self.lat + 0.0012345, self.lon + 0.0006789)

        item = (await self.nearby()).json()["items"][0]

        self.assertEqual(item["lat"], round(self.lat + 0.0012345, 4))
        self.assertEqual(item["lon"], round(self.lon + 0.0006789, 4))
        self.assertIsInstance(item["distance_m"], int)

    async def test_distance_does_not_leak_exact_position(self) -> None:
        # Distâncias exatas de três pontos permitiriam trilaterar a posição real;
        # por isso a distância é calculada a partir da coordenada publicada.
        await self.create_report(self.lat + 0.00104, self.lon)

        item = (await self.nearby()).json()["items"][0]

        expected = haversine_m(self.lat, self.lon, item["lat"], item["lon"])
        self.assertEqual(item["distance_m"], round(expected))

    async def test_radius_limits_results(self) -> None:
        await self.create_report(self.lat + 0.02, self.lon)  # ~2,2 km

        small = (await self.nearby(radius_m=1000)).json()
        large = (await self.nearby(radius_m=5000)).json()

        self.assertEqual(small["items"], [])
        self.assertEqual(len(large["items"]), 1)

    async def test_paginates_with_next_cursor(self) -> None:
        for step in range(3):
            await self.create_report(self.lat + 0.001 * (step + 1), self.lon)

        first = (await self.nearby(limit=2)).json()
        second = (await self.nearby(limit=2, cursor=first["next_cursor"])).json()

        self.assertEqual(len(first["items"]), 2)
        self.assertEqual(len(second["items"]), 1)
        self.assertIsNone(second["next_cursor"])

    async def test_validates_query_parameters(self) -> None:
        cases = [
            {"radius_m": 10},
            {"radius_m": 5001},
            {"limit": 0},
            {"limit": 101},
            {"category": "inexistente"},
            {"cursor": "invalido!"},
        ]
        for params in cases:
            with self.subTest(params=params):
                response = await self.nearby(**params)
                self.assertEqual(response.status_code, 422, response.text)

        response = await self.client.get("/v1/reports/nearby", params={"lat": 91, "lon": 0})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
