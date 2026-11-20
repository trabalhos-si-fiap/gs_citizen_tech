from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.auth import require_agency_api_key, require_moderator
from app.infrastructure.repositories import (
    InvalidAgencyAction,
    ReportNotFound,
)
from app.infrastructure.repositories import PhotoStorageUnavailable
from app.models.reports import (
    AgencyStatusRequest,
    ReportDetail,
    ReportDetailResponse,
    ReportSummaryResponse,
)
from app.services.photo_service import PhotoService
from app.services.report_service import ReportService

router = APIRouter(tags=["agency", "moderation"])


def get_report_service(request: Request) -> ReportService:
    return request.app.state.report_service


def get_photo_service(request: Request) -> PhotoService:
    return request.app.state.photo_service


def detail_response(
    detail: ReportDetail,
    photo_url: str | None,
) -> ReportDetailResponse:
    return ReportDetailResponse(
        id=detail.summary.id,
        protocol=detail.summary.protocol,
        status=detail.summary.status,
        category=detail.summary.category,
        lat=detail.summary.latitude,
        lon=detail.summary.longitude,
        received_at=detail.summary.received_at,
        group_id=detail.summary.group_id,
        confirmation_count=detail.summary.confirmation_count,
        description=detail.description,
        address=detail.summary.address,
        photo_url=photo_url,
        anonymous=detail.anonymous,
        has_photo=detail.has_photo,
        triage_state=detail.triage_state,
        classification=detail.classification,
        agency=None,
        deadline=detail.deadline,
        timeline=[],
    )


@router.post(
    "/v1/agency/reports/{report_id}/status",
)
def agency_status(
    report_id: UUID,
    payload: AgencyStatusRequest,
    _authorized: None = Depends(require_agency_api_key),
    service: ReportService = Depends(get_report_service),
    photos: PhotoService = Depends(get_photo_service),
):
    try:
        detail = service.update_agency_status(
            report_id,
            payload.action,
            payload.deadline,
            payload.justification,
        )
    except ReportNotFound as error:
        raise HTTPException(status_code=404, detail="Reporte não encontrado.") from error
    except InvalidAgencyAction as error:
        raise HTTPException(status_code=422, detail="Ação ou justificativa inválida.") from error
    photo_url = None
    try:
        photo_url = photos.read_url(report_id)
    except PhotoStorageUnavailable:
        photo_url = None
    return detail_response(detail, photo_url)


@router.get("/v1/moderation/reports")
def list_moderation(
    limit: int = Query(default=50, ge=1, le=100),
    _moderator_id: int = Depends(require_moderator),
    service: ReportService = Depends(get_report_service),
) -> dict[str, object]:
    reports = service.list_moderation(limit)
    return {
        "items": [
            ReportSummaryResponse(
                id=report.id,
                protocol=report.protocol,
                status=report.status,
                category=report.category,
                lat=report.latitude,
                lon=report.longitude,
                received_at=report.received_at,
                group_id=report.group_id,
                confirmation_count=report.confirmation_count,
            )
            for report in reports
        ],
        "count": len(reports),
    }
