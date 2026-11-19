"""Rotas dos servidores municipais (painel web)."""

from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
)

from app.api.auth import require_staff_user
from app.infrastructure.repositories import (
    AccountNotFound,
    InvalidAgencyAction,
    InvalidReportCursor,
    PhotoStorageUnavailable,
    ReportNotFound,
    StaffNotAuthorized,
    StaffTransitionNotAllowed,
)
from app.infrastructure.worker import ReportJobWorker
from app.models.reports import (
    AgencyResponse,
    AgencyStatusRequest,
    ReportDetail,
    ReportDetailResponse,
    ReportStatus,
    ReportTimelineEventResponse,
)
from app.models.staff import (
    StaffAgenciesResponse,
    StaffContext,
    StaffProfileResponse,
    StaffRedirectRequest,
    StaffReportItemResponse,
    StaffReportPageResponse,
    StaffSummaryResponse,
)
from app.models.taxonomy import ReportCategory
from app.services.photo_service import PhotoService
from app.services.staff_service import StaffService

router = APIRouter(prefix="/v1/staff", tags=["staff"])


def get_staff_service(request: Request) -> StaffService:
    return request.app.state.staff_service


def get_photo_service(request: Request) -> PhotoService:
    return request.app.state.photo_service


def get_staff_context(
    user_id: int = Depends(require_staff_user),
    service: StaffService = Depends(get_staff_service),
) -> StaffContext:
    try:
        return service.resolve(user_id)
    except AccountNotFound as error:
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except StaffNotAuthorized as error:
        raise HTTPException(
            status_code=403,
            detail="Conta sem permissão ou sem órgão vinculado.",
        ) from error


def _mask_actor(actor: str) -> str:
    # O servidor não recebe o identificador do cidadão (RN-43).
    return "citizen" if actor.startswith("citizen:") else actor


def _to_detail_response(
    detail: ReportDetail,
    photo_url: str | None,
) -> ReportDetailResponse:
    summary = detail.summary
    return ReportDetailResponse(
        id=summary.id,
        protocol=summary.protocol,
        status=summary.status,
        category=summary.category,
        lat=summary.latitude,
        lon=summary.longitude,
        received_at=summary.received_at,
        group_id=summary.group_id,
        confirmation_count=summary.confirmation_count,
        description=detail.description,
        photo_url=photo_url,
        anonymous=detail.anonymous,
        has_photo=detail.has_photo,
        triage_state=detail.triage_state,
        classification=detail.classification,
        agency=(
            AgencyResponse(id=detail.agency_id, name=detail.agency_name)
            if detail.agency_id and detail.agency_name
            else None
        ),
        deadline=detail.deadline,
        timeline=[
            ReportTimelineEventResponse(
                id=event.id,
                type=event.type,
                actor=_mask_actor(event.actor),
                justification=event.justification,
                created_at=event.created_at,
            )
            for event in detail.timeline
        ],
    )


def _photo_url(photos: PhotoService, report_id: UUID) -> str | None:
    try:
        return photos.read_url(report_id)
    except PhotoStorageUnavailable:
        return None


@router.get("/me", response_model=StaffProfileResponse)
def get_profile(
    context: StaffContext = Depends(get_staff_context),
    service: StaffService = Depends(get_staff_service),
) -> StaffProfileResponse:
    name = service.agency_name(context.agency_id)
    return StaffProfileResponse(
        id=str(context.user_id),
        email=context.email,
        role=context.role,
        scope=context.scope,
        agency=(
            AgencyResponse(id=context.agency_id, name=name or context.agency_id)
            if context.agency_id
            else None
        ),
    )


@router.get("/agencies", response_model=StaffAgenciesResponse)
def list_agencies(
    context: StaffContext = Depends(get_staff_context),
    service: StaffService = Depends(get_staff_service),
) -> StaffAgenciesResponse:
    return StaffAgenciesResponse(
        items=[
            AgencyResponse(id=agency_id, name=name)
            for agency_id, name in service.agencies(context)
        ]
    )


@router.get("/summary", response_model=StaffSummaryResponse)
def get_summary(
    context: StaffContext = Depends(get_staff_context),
    service: StaffService = Depends(get_staff_service),
) -> StaffSummaryResponse:
    summary = service.summary(context)
    return StaffSummaryResponse(
        total=summary.total,
        by_status=summary.by_status,
        overdue=summary.overdue,
        due_soon=summary.due_soon,
    )


@router.get(
    "/reports",
    response_model=StaffReportPageResponse,
    responses={400: {"description": "Cursor inválido."}},
)
def list_reports(
    status: ReportStatus | None = None,
    category: ReportCategory | None = None,
    overdue: bool = False,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: UUID | None = None,
    context: StaffContext = Depends(get_staff_context),
    service: StaffService = Depends(get_staff_service),
) -> StaffReportPageResponse:
    try:
        items = service.list_reports(
            context,
            status,
            category,
            overdue,
            q,
            limit + 1,
            cursor,
        )
    except InvalidReportCursor as error:
        raise HTTPException(status_code=400, detail="Cursor inválido.") from error

    has_more = len(items) > limit
    page = items[:limit]
    return StaffReportPageResponse(
        items=[
            StaffReportItemResponse(
                id=item.id,
                protocol=item.protocol,
                status=item.status,
                category=item.category,
                urgency=item.urgency,
                immediate_risk=item.immediate_risk,
                description=item.description,
                lat=item.latitude,
                lon=item.longitude,
                received_at=item.received_at,
                deadline=item.deadline,
                overdue=item.overdue,
                agency=(
                    AgencyResponse(id=item.agency_id, name=item.agency_name)
                    if item.agency_id and item.agency_name
                    else None
                ),
                confirmation_count=item.confirmation_count,
            )
            for item in page
        ],
        next_cursor=str(page[-1].id) if has_more and page else None,
    )


@router.get(
    "/reports/{report_id}",
    response_model=ReportDetailResponse,
    responses={404: {"description": "Reporte não encontrado no seu escopo."}},
)
def get_report(
    report_id: UUID,
    context: StaffContext = Depends(get_staff_context),
    service: StaffService = Depends(get_staff_service),
    photos: PhotoService = Depends(get_photo_service),
) -> ReportDetailResponse:
    try:
        detail = service.get_detail(context, report_id)
    except ReportNotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Reporte não encontrado.",
        ) from error
    return _to_detail_response(detail, _photo_url(photos, report_id))


@router.post(
    "/reports/{report_id}/status",
    response_model=ReportDetailResponse,
    responses={
        403: {"description": "Somente servidores de órgão alteram o status."},
        404: {"description": "Reporte não encontrado no seu escopo."},
        409: {"description": "Transição não permitida neste estado."},
        422: {"description": "Prazo ou justificativa inválidos."},
    },
)
def update_status(
    report_id: UUID,
    payload: AgencyStatusRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    context: StaffContext = Depends(get_staff_context),
    service: StaffService = Depends(get_staff_service),
    photos: PhotoService = Depends(get_photo_service),
) -> ReportDetailResponse:
    try:
        detail, event_id = service.update_status(
            context,
            report_id,
            payload.action,
            payload.deadline,
            payload.justification,
        )
    except ReportNotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Reporte não encontrado.",
        ) from error
    except StaffNotAuthorized as error:
        raise HTTPException(
            status_code=403,
            detail="Somente servidores de órgão podem alterar o status.",
        ) from error
    except StaffTransitionNotAllowed as error:
        raise HTTPException(
            status_code=409,
            detail="Transição de status não permitida neste estado.",
        ) from error
    except InvalidAgencyAction as error:
        raise HTTPException(
            status_code=422,
            detail="Ação, prazo ou justificativa inválidos.",
        ) from error

    if event_id is not None:
        worker: ReportJobWorker = request.app.state.report_worker
        worker.enqueue(report_id, f"notify_status_{event_id}")
        background_tasks.add_task(worker.run_once)
    return _to_detail_response(detail, _photo_url(photos, report_id))


@router.post(
    "/reports/{report_id}/redirect",
    response_model=ReportDetailResponse,
    responses={
        403: {"description": "Perfil sem permissão para redirecionar."},
        404: {"description": "Reporte não encontrado no seu escopo."},
        409: {"description": "Estado não permite redirecionar ou órgão é o atual."},
        422: {"description": "Órgão, prazo ou justificativa inválidos."},
    },
)
def redirect_report(
    report_id: UUID,
    payload: StaffRedirectRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    context: StaffContext = Depends(get_staff_context),
    service: StaffService = Depends(get_staff_service),
    photos: PhotoService = Depends(get_photo_service),
) -> ReportDetailResponse:
    try:
        detail, event_id = service.redirect(
            context,
            report_id,
            payload.agency_id,
            payload.justification,
            payload.deadline,
        )
    except ReportNotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Reporte não encontrado.",
        ) from error
    except StaffNotAuthorized as error:
        raise HTTPException(
            status_code=403,
            detail="Seu perfil não pode redirecionar reportes.",
        ) from error
    except StaffTransitionNotAllowed as error:
        raise HTTPException(
            status_code=409,
            detail="Não é possível redirecionar este reporte para esse órgão agora.",
        ) from error
    except InvalidAgencyAction as error:
        raise HTTPException(
            status_code=422,
            detail="Órgão, prazo ou justificativa inválidos.",
        ) from error

    # O novo órgão recebe o aviso de encaminhamento e o cidadão, a mudança.
    worker: ReportJobWorker = request.app.state.report_worker
    if event_id is not None:
        # O id do evento no nome: a fila ignora job repetido para o reporte.
        worker.enqueue(report_id, f"notify_agency_{event_id}")
        worker.enqueue(report_id, f"notify_status_{event_id}")
    background_tasks.add_task(worker.run_once)
    return _to_detail_response(detail, _photo_url(photos, report_id))
