import hashlib
import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from PIL import Image
from pydantic import SecretStr

from app.core.config import settings
from app.infrastructure.classifiers import FakeClassifier
from app.infrastructure.job_queue import InMemoryJobQueue
from app.main import app
from app.infrastructure.photo_storage import LocalPhotoStorage
from app.infrastructure.repositories import InMemoryReportRepository
from app.services.classification_service import ClassificationService
from app.services.photo_service import PhotoService
from app.services.report_service import ReportService
from app.infrastructure.worker import ReportJobWorker
from tests.unit.test_reports_api import create_access_token


class PhotoUploadApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_jwt_secret = settings.jwt_secret
        settings.jwt_secret = SecretStr(
            "unit-test-secret-that-is-at-least-32-bytes"
        )
        self.previous_services = (
            app.state.report_service,
            app.state.photo_service,
            app.state.report_worker,
        )
        repository = InMemoryReportRepository()
        queue = InMemoryJobQueue()
        storage = LocalPhotoStorage(
            storage_dir=Path(self.temp_dir.name),
            base_url="http://test",
            secret="photo-upload-test-secret-with-at-least-32-bytes",
            max_bytes=settings.photo_max_bytes,
        )
        app.state.report_service = ReportService(repository, storage)
        app.state.photo_service = PhotoService(repository, storage, queue)
        app.state.report_worker = ReportJobWorker(
            queue,
            repository,
            ClassificationService(FakeClassifier()),
            photo_storage=storage,
            worker_id="api-test-worker",
        )
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        (
            app.state.report_service,
            app.state.photo_service,
            app.state.report_worker,
        ) = self.previous_services
        settings.jwt_secret = self.previous_jwt_secret
        self.temp_dir.cleanup()

    async def test_signed_upload_complete_and_read_flow(self) -> None:
        image_buffer = io.BytesIO()
        Image.new("RGB", (20, 20), color="red").save(
            image_buffer,
            format="JPEG",
        )
        image_bytes = image_buffer.getvalue()
        report_id = uuid4()
        access_token = create_access_token(23)
        headers = {"Authorization": f"Bearer {access_token}"}

        created = await self.client.post(
            "/v1/reports",
            json={
                "id": str(report_id),
                "description": "Buraco na via",
                "has_photo": True,
                "lat": -23.55,
                "lon": -46.63,
                "client_created_at": datetime.now(timezone.utc).isoformat(),
            },
            headers=headers,
        )
        self.assertEqual(created.status_code, 201)
        upload_url = created.json()["upload"]["url"]

        uploaded = await self.client.put(upload_url, content=image_bytes)
        completed = await self.client.post(
            f"/v1/reports/{report_id}/photo/complete",
            json={"sha256": hashlib.sha256(image_bytes).hexdigest()},
            headers=headers,
        )
        self.assertEqual(uploaded.status_code, 204)
        self.assertEqual(completed.status_code, 202)

        detail = await self.client.get(
            f"/v1/reports/{report_id}",
            headers=headers,
        )
        self.assertEqual(detail.status_code, 200)
        photo = await self.client.get(detail.json()["photo_url"])

        self.assertEqual(photo.status_code, 200)
        self.assertEqual(photo.headers["content-type"], "image/jpeg")
        self.assertEqual(photo.headers["x-content-type-options"], "nosniff")
