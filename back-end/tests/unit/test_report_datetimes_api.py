"""Datas de reporte saem da API com fuso (UTC) quando vêm do Oracle.

O driver Oracle devolve TIMESTAMP sem fuso; sem a marcação de UTC no
repositório, a API serializava "2026-11-19T23:29:25.789511" e o app mostrava
o horário 3 h adiantado. Aqui o repositório Oracle (com banco falso) fica atrás
das rotas reais, para conferir o JSON de ponta a ponta.
"""

import unittest
from datetime import datetime
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.api.routes import me as me_routes
from app.api.routes import reports as report_routes
from app.api.routes import staff as staff_routes
from app.core.config import settings
from app.infrastructure.repositories import (
    InMemoryAuthRepository,
    OracleReportRepository,
)
from app.main import app
from app.models.staff import StaffContext
from app.services.report_service import ReportService
from app.services.staff_service import StaffService
from test_oracle_repository import (
    ADDRESS,
    NAIVE_RECEIVED_AT,
    FakeDatabase,
    scripted_cursor,
)
from test_reports_api import JWT_SECRET, create_access_token

REPORT_ID = "8d11c206-f849-4631-9c0f-d27a23fc7634"
UTC_JSON = "2026-11-19T23:29:25.789511Z"


class _NoPhotos:
    def read_url(self, report_id: UUID) -> None:
        return None


class OracleReportDatetimesApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.previous_jwt_secret = settings.jwt_secret
        settings.jwt_secret = SecretStr(JWT_SECRET)
        self.database = FakeDatabase()
        repository = OracleReportRepository(self.database)
        report_service = ReportService(repository, None)
        self.overrides = {
            me_routes.get_report_service: lambda: report_service,
            report_routes.get_report_service: lambda: report_service,
            report_routes.get_photo_service: lambda: _NoPhotos(),
            staff_routes.get_staff_service: lambda: StaffService(
                InMemoryAuthRepository(), repository
            ),
            staff_routes.get_staff_context: lambda: StaffContext(
                user_id=1, email=None, role="manager", agency_id=None
            ),
        }
        app.dependency_overrides.update(self.overrides)
        self.client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )
        self.citizen = {"Authorization": f"Bearer {create_access_token(23)}"}

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        for dependency in self.overrides:
            app.dependency_overrides.pop(dependency, None)
        settings.jwt_secret = self.previous_jwt_secret

    async def test_my_reports_received_at_has_utc_offset(self) -> None:
        scripted_cursor(self.database, fetchall=[[(
            REPORT_ID, "RPT-2026-4KQ7TD", "recebido", "risco_urbano",
            -23.573806, -46.623157, NAIVE_RECEIVED_AT, "12", 0,
            "Buraco", None, ADDRESS,
        )]])

        response = await self.client.get("/v1/me/reports", headers=self.citizen)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["items"][0]["received_at"], UTC_JSON)

    async def test_report_detail_datetimes_have_utc_offset(self) -> None:
        scripted_cursor(
            self.database,
            fetchone=[(
                REPORT_ID, "RPT-2026-4KQ7TD", "encaminhado", "risco_urbano",
                "Buraco", -23.573806, -46.623157, NAIVE_RECEIVED_AT, 23, 0,
                "confirmed", "12", 0, REPORT_ID, ADDRESS,
            )],
            fetchall=[
                [(1, "recebido", "system", None, NAIVE_RECEIVED_AT)],
                [(
                    "encaminhado",
                    '{"agency_id": "saneamento-demo", "agency_name": "Saneamento"}',
                    datetime(2026, 11, 22, 23, 29, 25, 789511),
                    "system",
                )],
            ],
        )

        response = await self.client.get(
            f"/v1/reports/{REPORT_ID}", headers=self.citizen
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["received_at"], UTC_JSON)
        self.assertEqual(body["timeline"][0]["created_at"], UTC_JSON)
        self.assertEqual(body["deadline"], "2026-11-22T23:29:25.789511Z")
        self.assertEqual(body["address"], ADDRESS)

    async def test_staff_list_received_at_has_utc_offset(self) -> None:
        scripted_cursor(self.database, fetchall=[[(
            REPORT_ID, "RPT-2026-4KQ7TD", "encaminhado", "risco_urbano",
            "alta", "false", "Buraco", -23.573806, -46.623157,
            NAIVE_RECEIVED_AT, None, "saneamento-demo", "Saneamento", 0, ADDRESS,
        )]])

        response = await self.client.get("/v1/staff/reports")

        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["items"][0]
        self.assertEqual(item["received_at"], UTC_JSON)
        self.assertEqual(item["address"], ADDRESS)


if __name__ == "__main__":
    unittest.main()
