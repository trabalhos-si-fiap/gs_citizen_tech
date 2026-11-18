import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

from app.infrastructure.job_queue import InMemoryJobQueue
from app.models.reports import NewReport
from app.infrastructure.repositories import InMemoryReportRepository, ReportNotOwner
from app.services.photo_service import PhotoService


class PhotoServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report_id = uuid4()
        self.repository = InMemoryReportRepository()
        self.repository.create(
            NewReport(
                id=self.report_id,
                description=None,
                has_photo=True,
                category=None,
                latitude=-23.55,
                longitude=-46.63,
                location_accuracy_m=None,
                anonymous=True,
                client_created_at=datetime.now(timezone.utc),
                correlation_id=uuid4(),
                user_id=None,
                requester_user_id=23,
            )
        )
        self.storage = Mock()
        self.queue = InMemoryJobQueue()
        self.service = PhotoService(
            self.repository,
            self.storage,
            self.queue,
        )

    def test_completion_enqueues_photo_processing_after_checksum_validation(self) -> None:
        checksum = "a" * 64

        self.service.complete(self.report_id, 23, checksum)

        self.storage.register_completion.assert_called_once_with(
            self.report_id,
            checksum,
        )
        job = self.queue.reserve_next("worker", lease_seconds=30)
        self.assertEqual(job.report_id, self.report_id)
        self.assertEqual(job.stage, "process_photo")

    def test_non_owner_cannot_complete_upload(self) -> None:
        with self.assertRaises(ReportNotOwner):
            self.service.complete(self.report_id, 24, "a" * 64)

        self.storage.register_completion.assert_not_called()
        self.assertIsNone(self.queue.reserve_next("worker", lease_seconds=30))
