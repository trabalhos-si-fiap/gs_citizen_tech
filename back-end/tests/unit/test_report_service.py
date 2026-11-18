import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.models.reports import (
    CreateReportRequest,
    NewReport,
    PersistedReport,
    ReportStatus,
    TriageState,
    UploadInstruction,
    ClientTimestampOutOfRange,
)
from app.services.report_service import (
    ReportService,
)


NOW = datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc)


class FakeReportRepository:
    def __init__(self, *, was_created: bool = True) -> None:
        self.was_created = was_created
        self.created_reports: list[NewReport] = []

    def create(self, report: NewReport) -> PersistedReport:
        self.created_reports.append(report)
        return PersistedReport(
            id=report.id,
            protocol="RPT-2026-4KQ7TD",
            received_at=NOW,
            was_created=self.was_created,
        )


class FakeObjectStorage:
    def __init__(self) -> None:
        self.upload_requests: list[tuple[UUID, int, timedelta]] = []

    def create_upload_instruction(
        self,
        report_id: UUID,
        *,
        max_bytes: int,
        expires_in: timedelta,
    ) -> UploadInstruction:
        self.upload_requests.append((report_id, max_bytes, expires_in))
        return UploadInstruction(
            url="http://localhost:8000/v1/uploads/example-token",
            expires_at=NOW + expires_in,
            max_bytes=max_bytes,
            headers={"Content-Type": "image/jpeg"},
        )


class ReportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeReportRepository()
        self.storage = FakeObjectStorage()
        self.service = ReportService(
            self.repository,
            self.storage,
            clock=lambda: NOW,
        )

    def make_report(
        self,
        *,
        description: str | None = "Buraco na via",
        has_photo: bool = False,
        client_created_at: datetime = NOW,
    ) -> NewReport:
        return NewReport(
            id=uuid4(),
            description=description,
            has_photo=has_photo,
            category=None,
            latitude=-23.55,
            longitude=-46.63,
            location_accuracy_m=None,
            anonymous=False,
            client_created_at=client_created_at,
            correlation_id=uuid4(),
            user_id=1,
            requester_user_id=1,
        )

    def test_create_without_photo_persists_without_upload(self) -> None:
        report = self.make_report()

        result = self.service.create(report)

        self.assertEqual(len(self.repository.created_reports), 1)
        self.assertEqual(result.id, report.id)
        self.assertEqual(result.protocol, "RPT-2026-4KQ7TD")
        self.assertEqual(result.status, ReportStatus.RECEIVED)
        self.assertEqual(result.triage_state, TriageState.PENDING_CLASSIFICATION)
        self.assertTrue(result.was_created)
        self.assertIsNone(result.upload)
        self.assertEqual(self.storage.upload_requests, [])

    def test_create_with_photo_requests_signed_upload(self) -> None:
        report = self.make_report(description=None, has_photo=True)

        result = self.service.create(report)

        self.assertIsNotNone(result.upload)
        self.assertEqual(result.upload.method, "PUT")
        self.assertEqual(
            self.storage.upload_requests[0][0],
            report.id,
        )
        self.assertEqual(
            self.storage.upload_requests[0][1],
            1_000_000,
        )
        self.assertEqual(
            self.storage.upload_requests[0][2],
            timedelta(minutes=10),
        )

    def test_existing_report_is_returned_as_idempotent_result(self) -> None:
        self.repository.was_created = False

        result = self.service.create(self.make_report())

        self.assertFalse(result.was_created)
        self.assertEqual(len(self.repository.created_reports), 1)

    def test_rejects_client_timestamp_outside_allowed_window(self) -> None:
        old_timestamp = NOW - timedelta(days=31)

        with self.assertRaises(ClientTimestampOutOfRange):
            self.service.create(self.make_report(client_created_at=old_timestamp))

        self.assertEqual(self.repository.created_reports, [])

    def test_request_requires_photo_or_nonblank_description(self) -> None:
        with self.assertRaises(ValidationError):
            CreateReportRequest(
                id=uuid4(),
                lat=-23.55,
                lon=-46.63,
                client_created_at=NOW,
                description="  ",
                has_photo=False,
            )

    def test_request_rejects_coordinates_outside_geographic_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            CreateReportRequest(
                id=uuid4(),
                lat=91,
                lon=-46.63,
                client_created_at=NOW,
                description="Buraco na via",
            )


if __name__ == "__main__":
    unittest.main()
