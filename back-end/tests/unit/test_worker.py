import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4

from app.infrastructure.classifiers import FakeClassifier
from app.infrastructure.job_queue import InMemoryJobQueue
from app.models.classification import ClassificationInput
from app.models.reports import NewReport, TriageState
from app.infrastructure.repositories import InMemoryReportRepository
from app.services.classification_service import ClassificationService
from app.infrastructure.worker import ReportJobWorker


class WorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        self.clock_value = [self.now]
        self.queue = InMemoryJobQueue(clock=lambda: self.clock_value[0])

    def test_expired_lease_is_reclaimed_after_worker_crash(self) -> None:
        report_id = uuid4()
        self.queue.enqueue(report_id, "classificar")

        first = self.queue.reserve_next("worker-a", lease_seconds=30)
        self.clock_value[0] += timedelta(seconds=31)
        second = self.queue.reserve_next("worker-b", lease_seconds=30)

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.attempts, 1)
        self.assertEqual(second.attempts, 2)
        with self.assertRaises(RuntimeError):
            self.queue.complete(first.id, "worker-a")

    def test_failed_jobs_use_backoff_and_stop_after_max_attempts(self) -> None:
        report_id = uuid4()
        self.queue.enqueue(report_id, "classificar")

        first_attempt = self.queue.reserve_next("worker-a", lease_seconds=30)
        self.assertFalse(
            self.queue.fail(
                first_attempt.id,
                "worker-a",
                "TemporaryError",
                2,
            )
        )
        self.assertIsNone(self.queue.reserve_next("worker-a", lease_seconds=30))

        self.clock_value[0] += timedelta(minutes=1)
        second_attempt = self.queue.reserve_next("worker-a", lease_seconds=30)
        self.assertEqual(second_attempt.attempts, 2)
        self.assertTrue(
            self.queue.fail(
                second_attempt.id,
                "worker-a",
                "TemporaryError",
                2,
            )
        )
        self.assertIsNone(self.queue.reserve_next("worker-a", lease_seconds=30))

    def test_worker_persists_classification_and_completes_job(self) -> None:
        repository = InMemoryReportRepository()
        report = NewReport(
            id=uuid4(),
            description="Vazamento de esgoto na rua.",
            has_photo=False,
            category=None,
            latitude=-23.55,
            longitude=-46.63,
            location_accuracy_m=None,
            anonymous=False,
            client_created_at=self.now,
            correlation_id=uuid4(),
            user_id=11,
            requester_user_id=11,
        )
        repository.create(report)
        self.queue.enqueue(report.id, "classificar")
        worker = ReportJobWorker(
            self.queue,
            repository,
            ClassificationService(FakeClassifier()),
            worker_id="test-worker",
        )

        self.assertTrue(worker.run_once())
        detail = repository.get_detail(report.id)

        self.assertEqual(
            detail.classification.subcategory,
            "esgoto_vazamento",
        )
        self.assertEqual(detail.triage_state, TriageState.AWAITING_USER)
        self.assertFalse(worker.run_once())

    def test_terminal_failure_sends_report_to_moderation(self) -> None:
        report_id = uuid4()
        self.queue.enqueue(report_id, "classificar")
        repository = Mock()
        repository.classification_input.return_value = ClassificationInput(
            text="Reporte",
            user_category=None,
        )
        classifier = Mock()
        classifier.classify.side_effect = RuntimeError("storage unavailable")
        worker = ReportJobWorker(
            self.queue,
            repository,
            classifier,
            worker_id="test-worker",
            max_attempts=1,
        )

        self.assertTrue(worker.run_once())
        repository.mark_for_moderation.assert_called_once_with(report_id)

    def test_terminal_notification_failure_sends_report_to_moderation(self) -> None:
        report_id = uuid4()
        self.queue.enqueue(report_id, "notify_agency")
        repository = Mock()
        notification_service = Mock()
        notification_service.notify_agency.side_effect = RuntimeError(
            "SMTP unavailable"
        )
        worker = ReportJobWorker(
            self.queue,
            repository,
            ClassificationService(FakeClassifier()),
            worker_id="test-worker",
            max_attempts=1,
            notification_service=notification_service,
        )

        self.assertTrue(worker.run_once())

        repository.mark_for_moderation.assert_called_once_with(report_id)

    def test_worker_sanitizes_photo_and_persists_storage_key(self) -> None:
        report_id = uuid4()
        self.queue.enqueue(report_id, "process_photo")
        repository = Mock()
        photo_storage = Mock()
        photo_storage.process_upload.return_value = "objects/photo.jpg"
        worker = ReportJobWorker(
            self.queue,
            repository,
            ClassificationService(FakeClassifier()),
            worker_id="test-worker",
            photo_storage=photo_storage,
        )

        self.assertTrue(worker.run_once())

        photo_storage.process_upload.assert_called_once_with(report_id)
        repository.set_photo_key.assert_called_once_with(
            report_id,
            "objects/photo.jpg",
        )
        photo_storage.discard_upload.assert_called_once_with(report_id)

    def test_worker_sends_agency_notification_job(self) -> None:
        report_id = uuid4()
        self.queue.enqueue(report_id, "notify_agency")
        repository = Mock()
        notification_service = Mock()
        worker = ReportJobWorker(
            self.queue,
            repository,
            ClassificationService(FakeClassifier()),
            worker_id="test-worker",
            notification_service=notification_service,
        )

        self.assertTrue(worker.run_once())

        notification_service.notify_agency.assert_called_once_with(report_id)

    def test_worker_sends_status_notification_job(self) -> None:
        report_id = uuid4()
        self.queue.enqueue(report_id, "notify_status_42")
        repository = Mock()
        citizen_notifications = Mock()
        worker = ReportJobWorker(
            self.queue,
            repository,
            ClassificationService(FakeClassifier()),
            worker_id="test-worker",
            citizen_notification_service=citizen_notifications,
        )

        self.assertTrue(worker.run_once())

        citizen_notifications.notify_status.assert_called_once_with(report_id, 42)

    def test_worker_sends_overdue_notification_job(self) -> None:
        report_id = uuid4()
        self.queue.enqueue(report_id, "notify_overdue")
        repository = Mock()
        citizen_notifications = Mock()
        worker = ReportJobWorker(
            self.queue,
            repository,
            ClassificationService(FakeClassifier()),
            worker_id="test-worker",
            citizen_notification_service=citizen_notifications,
        )

        self.assertTrue(worker.run_once())

        citizen_notifications.notify_overdue.assert_called_once_with(report_id)



class TriageSweepTests(unittest.TestCase):
    def make_worker(self, sweeper, ticks):
        return ReportJobWorker(
            InMemoryJobQueue(),
            InMemoryReportRepository(),
            ClassificationService(FakeClassifier()),
            worker_id=f"test-{uuid4()}",
            triage_sweeper=sweeper,
            sweep_interval_seconds=60,
            monotonic=lambda: ticks[0],
        )

    def test_sweeps_due_triage_at_most_once_per_interval(self) -> None:
        sweeper = Mock(return_value=0)
        ticks = [1000.0]
        worker = self.make_worker(sweeper, ticks)

        worker.run_once()
        ticks[0] += 30
        worker.run_once()
        self.assertEqual(sweeper.call_count, 1)

        ticks[0] += 31
        worker.run_once()
        self.assertEqual(sweeper.call_count, 2)

    def test_sweep_failure_does_not_stop_job_processing(self) -> None:
        sweeper = Mock(side_effect=RuntimeError("banco indisponível"))
        worker = self.make_worker(sweeper, [0.0])

        with self.assertLogs("app.infrastructure.worker", level="ERROR"):
            self.assertFalse(worker.run_once())


if __name__ == "__main__":
    unittest.main()
