"""Caso de uso de criação idempotente de reportes."""

import base64
import binascii
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from app.core.config import settings
from app.core.geo import bounding_box, haversine_m
from app.models.classification import ClassificationResult, TriageRequest
from app.models.reports import (
    ClientTimestampOutOfRange,
    NearbyPage,
    NearbyQuery,
    NearbyReport,
    NewReport,
    ReportDetail,
    ReportComment,
    ReportCreationResult,
    ReportStatus,
    ReportSummary,
    TriageState,
)
from app.infrastructure.repositories import (
    InvalidReportCursor,
    ObjectStorage,
    ReportRepository,
    TriageConflict,
)
from app.services.routing_service import RoutingService

CLIENT_TIMESTAMP_MAX_AGE = timedelta(days=30)
CLIENT_TIMESTAMP_FUTURE_TOLERANCE = timedelta(minutes=1)
UPLOAD_URL_TTL = timedelta(minutes=10)
# Teto de candidatos lidos do banco por consulta de proximidade. Com raio de até
# 5 km é folgado para o volume esperado; acima disso a busca mostra os mais recentes.
NEARBY_CANDIDATE_LIMIT = 1000
# Casas decimais publicadas no mapa (4 casas ~ 11 m): localiza a ocorrência sem
# expor a posição exata de quem reportou. Raio e distância usam essa coordenada,
# senão variar o raio ou consultar de três pontos revelaria a posição real.
PUBLIC_COORDINATE_DECIMALS = 4


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

    def nearby(self, query: NearbyQuery) -> NearbyPage:
        """Ocorrências públicas no raio, uma por grupo, da mais próxima à mais distante."""
        offset = _decode_offset(query.cursor)
        candidates = self._repository.list_in_area(
            bounding_box(query.latitude, query.longitude, query.radius_m),
            NEARBY_CANDIDATE_LIMIT,
        )

        closest_by_group: dict[str, NearbyReport] = {}
        for candidate in candidates:
            summary = replace(
                candidate,
                latitude=round(candidate.latitude, PUBLIC_COORDINATE_DECIMALS),
                longitude=round(candidate.longitude, PUBLIC_COORDINATE_DECIMALS),
            )
            if query.category is not None and summary.category != query.category:
                continue
            if query.status is not None and summary.status != query.status:
                continue
            distance = haversine_m(
                query.latitude, query.longitude, summary.latitude, summary.longitude
            )
            if distance > query.radius_m:
                continue
            current = closest_by_group.get(summary.group_id)
            if current is None or distance < current.distance_m:
                closest_by_group[summary.group_id] = NearbyReport(summary, distance)

        ordered = sorted(
            closest_by_group.values(),
            key=lambda item: (item.distance_m, str(item.summary.id)),
        )
        page = ordered[offset : offset + query.limit]
        has_more = offset + query.limit < len(ordered)
        return NearbyPage(
            items=page,
            next_cursor=_encode_offset(offset + query.limit) if has_more else None,
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

    def reopen_report(
        self,
        report_id: UUID,
        user_id: int,
        reason: str | None,
    ) -> ReportDetail:
        return self._repository.reopen_report(report_id, user_id, reason)

    def flag_report(
        self,
        report_id: UUID,
        user_id: int,
        reason: str,
        note: str | None,
    ) -> None:
        self._repository.flag_report(report_id, user_id, reason, note)

    def nudge_report(self, report_id: UUID, user_id: int) -> None:
        self._repository.nudge_report(report_id, user_id)

    def update_agency_status(
        self,
        report_id: UUID,
        action: str,
        deadline: datetime | None,
        justification: str | None,
    ) -> ReportDetail:
        return self._repository.update_agency_status(
            report_id,
            action,
            deadline,
            justification,
        )

    def list_moderation(self, limit: int) -> list[ReportSummary]:
        return self._repository.list_moderation(limit)

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


def _encode_offset(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode().rstrip("=")


def _decode_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        offset = int(base64.urlsafe_b64decode(padded.encode()).decode())
    except (binascii.Error, ValueError, UnicodeDecodeError) as error:
        raise InvalidReportCursor from error
    if offset < 0:
        raise InvalidReportCursor
    return offset
