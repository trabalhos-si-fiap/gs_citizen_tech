"""Caso de uso de criação idempotente de reportes."""

from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from app.core.config import settings
from app.models.classification import ClassificationResult, TriageRequest
from app.models.reports import (
    ClientTimestampOutOfRange,
    NewReport,
    ReportDetail,
    ReportComment,
    ReportCreationResult,
    ReportStatus,
    ReportSummary,
    TriageState,
)
from app.infrastructure.repositories import (
    ObjectStorage,
    ReportRepository,
    TriageConflict,
)
from app.services.routing_service import RoutingService

CLIENT_TIMESTAMP_MAX_AGE = timedelta(days=30)
CLIENT_TIMESTAMP_FUTURE_TOLERANCE = timedelta(minutes=1)
UPLOAD_URL_TTL = timedelta(minutes=10)


class ReportService:
    def __init__(
        self,
        repository: ReportRepository,
        object_storage: ObjectStorage,
        *,
        clock: Callable[[], datetime] | None = None,
        routing_service: RoutingService | None = None,
    ) -> None:
        self._repository = repository
        self._object_storage = object_storage
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._routing_service = routing_service or RoutingService(clock=self._clock)

    def create(self, report: NewReport) -> ReportCreationResult:
        self._validate_client_timestamp(report.client_created_at)
        upload = None
        if report.has_photo:
            upload = self._object_storage.create_upload_instruction(
                report.id,
                max_bytes=settings.photo_max_bytes,
                expires_in=UPLOAD_URL_TTL,
            )
        persisted = self._repository.create(report)

        return ReportCreationResult(
            id=persisted.id,
            protocol=persisted.protocol,
            status=persisted.status,
            received_at=persisted.received_at,
            triage_state=persisted.triage_state,
            was_created=persisted.was_created,
            upload=upload,
        )

    def get_detail(self, report_id: UUID) -> ReportDetail:
        return self._repository.get_detail(report_id)

    def apply_triage(
        self,
        report_id: UUID,
        user_id: int,
        request: TriageRequest,
    ) -> ReportDetail:
        detail = self._repository.get_detail(report_id)
        classification = detail.classification
        if classification is None:
            raise TriageConflict
        if detail.triage_state != TriageState.AWAITING_USER:
            raise TriageConflict

        if request.action == "correct":
            classification = ClassificationResult.model_validate(
                {
                    **classification.model_dump(),
                    "category": request.category,
                    "subcategory": request.subcategory,
                    "source": "user",
                }
            )
        route = self._routing_service.find_rule(
            classification.category,
            classification.subcategory,
        )
        deadline = (
            self._clock() + timedelta(hours=route.deadline_hours)
            if route is not None
            else None
        )
        self._repository.apply_triage(
            report_id,
            user_id,
            request.action,
            classification,
            route,
            deadline,
        )
        return self._repository.get_detail(report_id)

    def list_user_reports(
        self,
        user_id: int,
        limit: int,
        cursor: UUID | None,
        status: ReportStatus | None,
    ) -> list[ReportSummary]:
        return self._repository.list_user_reports(
            user_id,
            limit,
            cursor,
            status,
        )

    def add_comment(
        self,
        report_id: UUID,
        user_id: int,
        content: str,
    ) -> ReportComment:
        return self._repository.create_comment(report_id, user_id, content)

    def get_comments(
        self,
        report_id: UUID,
        limit: int,
    ) -> list[ReportComment]:
        return self._repository.list_comments(report_id, limit)

    def confirm(self, report_id: UUID, user_id: int) -> int:
        return self._repository.confirm(report_id, user_id)

    def _validate_client_timestamp(self, client_created_at: datetime) -> None:
        now = self._clock()
        if now.utcoffset() is None:
            raise ValueError("O relógio do serviço deve conter fuso horário.")

        client_created_at = client_created_at.astimezone(timezone.utc)
        now = now.astimezone(timezone.utc)
        if (
            client_created_at > now + CLIENT_TIMESTAMP_FUTURE_TOLERANCE
            or client_created_at < now - CLIENT_TIMESTAMP_MAX_AGE
        ):
            raise ClientTimestampOutOfRange(
                "client_created_at fora da janela permitida."
            )
