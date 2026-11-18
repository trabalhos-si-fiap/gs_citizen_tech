"""Rotas dos dados associados ao usuário autenticado."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.auth import require_citizen
from app.models.auth import DeleteAccountResponse, UpdateMeRequest, UserResponse
from app.models.notifications import RegisterDeviceRequest
from app.models.reports import (
    ReportStatus,
    ReportSummaryResponse,
    UserReportPageResponse,
)
from app.infrastructure.repositories import InvalidReportCursor
from app.services.notification_service import CitizenNotificationService
from app.services.report_service import ReportService
from app.services.privacy_service import PrivacyService
from app.infrastructure.repositories import AccountNotFound, GoogleAccountConflict

router = APIRouter(prefix="/v1/me", tags=["me"])


def get_report_service(request: Request) -> ReportService:
    return request.app.state.report_service


def get_citizen_notification_service(
    request: Request,
) -> CitizenNotificationService:
    return request.app.state.citizen_notification_service


def get_privacy_service(request: Request) -> PrivacyService:
    return request.app.state.privacy_service


@router.get("", response_model=UserResponse)
def get_account(
    user_id: int = Depends(require_citizen),
    service: PrivacyService = Depends(get_privacy_service),
) -> UserResponse:
    try:
        account = service.get_account(user_id)
    except AccountNotFound as error:
        raise HTTPException(status_code=404, detail="Conta não encontrada.") from error
    return UserResponse(
        id=str(account.id),
        email=account.email,
        role=account.role,
        consent_version=account.consent_version,
        created_at=account.created_at,
    )


@router.patch("", response_model=UserResponse)
def update_account(
    payload: UpdateMeRequest,
    user_id: int = Depends(require_citizen),
    service: PrivacyService = Depends(get_privacy_service),
) -> UserResponse:
    try:
        account = service.update_email(user_id, str(payload.email))
    except AccountNotFound as error:
        raise HTTPException(status_code=404, detail="Conta não encontrada.") from error
    except GoogleAccountConflict as error:
        raise HTTPException(status_code=409, detail="Este e-mail já está associado a outra conta.") from error
    return UserResponse(
        id=str(account.id),
        email=account.email,
        role=account.role,
        consent_version=account.consent_version,
        created_at=account.created_at,
    )


@router.get("/export")
def export_account_data(
    user_id: int = Depends(require_citizen),
    service: PrivacyService = Depends(get_privacy_service),
) -> dict[str, object]:
    try:
        return service.export_data(user_id)
    except AccountNotFound as error:
        raise HTTPException(status_code=404, detail="Conta não encontrada.") from error


@router.delete("", status_code=202, response_model=DeleteAccountResponse)
def delete_account(
    user_id: int = Depends(require_citizen),
    service: PrivacyService = Depends(get_privacy_service),
) -> DeleteAccountResponse:
    try:
        service.delete_account(user_id)
    except AccountNotFound as error:
        raise HTTPException(status_code=404, detail="Conta não encontrada.") from error
    return DeleteAccountResponse()


@router.put("/devices", status_code=204)
def register_device(
    payload: RegisterDeviceRequest,
    user_id: int = Depends(require_citizen),
    service: CitizenNotificationService = Depends(
        get_citizen_notification_service
    ),
) -> Response:
    service.register_device(user_id, payload.push_token, payload.platform)
    return Response(status_code=204)


@router.delete("/devices", status_code=204)
def remove_device(
    payload: RegisterDeviceRequest,
    user_id: int = Depends(require_citizen),
    service: CitizenNotificationService = Depends(
        get_citizen_notification_service
    ),
) -> Response:
    service.remove_device(user_id, payload.push_token)
    return Response(status_code=204)


@router.get(
    "/reports",
    response_model=UserReportPageResponse,
    responses={400: {"description": "Cursor inválido."}},
)
def list_my_reports(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: UUID | None = None,
    status: ReportStatus | None = None,
    user_id: int = Depends(require_citizen),
    service: ReportService = Depends(get_report_service),
) -> UserReportPageResponse:
    try:
        reports = service.list_user_reports(
            user_id,
            limit + 1,
            cursor,
            status,
        )
    except InvalidReportCursor as error:
        raise HTTPException(
            status_code=400,
            detail="Cursor inválido ou fora dos seus reportes.",
        ) from error

    has_more = len(reports) > limit
    page = reports[:limit]
    return UserReportPageResponse(
        items=[
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
            for report in page
        ],
        next_cursor=str(page[-1].id) if has_more and page else None,
    )
