"""Worker durável para jobs de processamento de reportes."""

import logging
import socket
import time
from uuid import UUID, uuid4

from app.infrastructure.classifiers import build_classifier
from app.core.config import settings
from app.infrastructure.database import OracleDatabase
from app.infrastructure.job_queue import InMemoryJobQueue, JobQueue, OracleJobQueue
from app.infrastructure.mailer import SmtpAgencyMailer
from app.infrastructure.photo_storage import LocalPhotoStorage
from app.infrastructure.push import build_push_sender
from app.infrastructure.repositories import (
    InMemoryReportRepository,
    OracleReportRepository,
    ReportRepository,
)
from app.services.classification_service import ClassificationService
from app.services.notification_service import (
    AgencyNotificationService,
    CitizenNotificationService,
)
from app.services.photo_service import PhotoService

logger = logging.getLogger(__name__)


class ReportJobWorker:
    def __init__(
        self,
        queue: JobQueue,
        repository: ReportRepository,
        classification_service: ClassificationService,
        *,
        worker_id: str | None = None,
        poll_seconds: float | None = None,
        lease_seconds: int | None = None,
        max_attempts: int | None = None,
        photo_storage: LocalPhotoStorage | None = None,
        notification_service: AgencyNotificationService | None = None,
        citizen_notification_service: CitizenNotificationService | None = None,
    ) -> None:
        self._queue = queue
        self._repository = repository
        self._classification_service = classification_service
        self._photo_storage = photo_storage
        self._notification_service = notification_service
        self._citizen_notification_service = citizen_notification_service
        self._worker_id = worker_id or f"{socket.gethostname()}:{uuid4()}"
        self._poll_seconds = (
            settings.report_job_poll_seconds
            if poll_seconds is None
            else poll_seconds
        )
        self._lease_seconds = (
            settings.report_job_lease_seconds
            if lease_seconds is None
            else lease_seconds
        )
        self._max_attempts = (
            settings.report_job_max_attempts
            if max_attempts is None
            else max_attempts
        )

    def enqueue(self, report_id: UUID, stage: str = "classificar") -> None:
        self._queue.enqueue(report_id, stage)

    def run_once(self) -> bool:
        job = self._queue.reserve_next(
            self._worker_id,
            self._lease_seconds,
        )
        if job is None:
            return False

        try:
            if job.stage == "classificar":
                classification_input = self._repository.classification_input(
                    job.report_id
                )
                result = self._classification_service.classify(classification_input)
                self._repository.record_classification(job.report_id, result)
            elif job.stage == "process_photo" and self._photo_storage is not None:
                photo_key = self._photo_storage.process_upload(job.report_id)
                self._repository.set_photo_key(job.report_id, photo_key)
                self._photo_storage.discard_upload(job.report_id)
            elif job.stage == "notify_agency" and self._notification_service is not None:
                self._notification_service.notify_agency(job.report_id)
            elif (
                job.stage.startswith("notify_status_")
                and self._citizen_notification_service is not None
            ):
                event_id = int(job.stage.removeprefix("notify_status_"))
                self._citizen_notification_service.notify_status(
                    job.report_id,
                    event_id,
                )
            elif (
                job.stage == "notify_overdue"
                and self._citizen_notification_service is not None
            ):
                self._citizen_notification_service.notify_overdue(job.report_id)
            else:
                raise RuntimeError(f"Etapa de job não suportada: {job.stage}")
            self._queue.complete(job.id, self._worker_id)
        except Exception as error:
            logger.error(
                "Falha no job %s, tentativa %s (%s).",
                job.id,
                job.attempts,
                type(error).__name__,
            )
            exhausted = self._queue.fail(
                job.id,
                self._worker_id,
                type(error).__name__,
                self._max_attempts,
            )
            if (
                exhausted
                and job.stage in {"classificar", "notify_agency"}
                and not self._queue.handles_terminal_failure
            ):
                self._repository.mark_for_moderation(job.report_id)
        return True

    def run_forever(self) -> None:
        while True:
            if not self.run_once():
                time.sleep(self._poll_seconds)


def main() -> None:
    if settings.report_repository != "oracle":
        raise RuntimeError(
            "O processo worker separado exige REPORT_REPOSITORY=oracle."
        )

    database = OracleDatabase(settings)
    database.open()
    try:
        repository = OracleReportRepository(database)
        queue = OracleJobQueue(database)
        photo_storage = LocalPhotoStorage()
        photo_service = PhotoService(repository, photo_storage, queue)
        notification_service = AgencyNotificationService(
            repository,
            SmtpAgencyMailer(settings),
            photo_service,
        )
        citizen_notification_service = CitizenNotificationService(
            repository,
            build_push_sender(settings),
        )
        worker = ReportJobWorker(
            queue,
            repository,
            ClassificationService(build_classifier(settings)),
            photo_storage=photo_storage,
            notification_service=notification_service,
            citizen_notification_service=citizen_notification_service,
        )
        logger.info("Worker de reportes iniciado.")
        worker.run_forever()
    except KeyboardInterrupt:
        logger.info("Worker de reportes encerrado.")
    finally:
        database.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
