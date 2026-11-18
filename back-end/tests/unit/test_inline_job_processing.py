import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import settings
from app.main import app
from tests.unit.test_reports_api import JWT_SECRET, create_access_token


class InlineJobProcessingTests(unittest.IsolatedAsyncioTestCase):
    """Com worker dedicado (container próprio), a API só enfileira jobs."""

    async def asyncSetUp(self) -> None:
        self.previous = (settings.jwt_secret, settings.inline_job_processing)
        settings.jwt_secret = SecretStr(JWT_SECRET)
        self.run_once = patch.object(app.state.report_worker, "run_once").start()
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        patch.stopall()
        # A fila em memória é compartilhada pelo app; não deixar jobs pendentes.
        while app.state.report_worker.run_once():
            pass
        settings.jwt_secret, settings.inline_job_processing = self.previous

    async def create_report(self) -> int:
        response = await self.client.post(
            "/v1/reports",
            json={
                "id": str(uuid4()),
                "description": "Buraco na via",
                "lat": -23.55,
                "lon": -46.63,
                "client_created_at": datetime.now(timezone.utc).isoformat(),
            },
            headers={"Authorization": f"Bearer {create_access_token(9101)}"},
        )
        return response.status_code

    async def test_api_processes_jobs_inline_by_default(self) -> None:
        settings.inline_job_processing = True

        self.assertEqual(await self.create_report(), 201)
        self.run_once.assert_called()

    async def test_api_only_enqueues_when_inline_processing_is_disabled(self) -> None:
        settings.inline_job_processing = False

        self.assertEqual(await self.create_report(), 201)
        self.run_once.assert_not_called()


if __name__ == "__main__":
    unittest.main()
