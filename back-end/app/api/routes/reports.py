"""Rotas do fluxo de reportes."""

from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)

from app.api.auth import require_agency_api_key, require_citizen
from app.models.classification import TriageRequest
from app.models.reports import (
    AgencyResponse,
    ClientTimestampOutOfRange,
    CompletePhotoRequest,
    CreateReportRequest,
    CreateReportCommentRequest,
    NewReport,
    ReportCommentResponse,
    ReportCommentsResponse,
    ReportConfirmationResponse,
    ReportCreatedResponse,
    ReportDetailResponse,
    ReportDetail,
    PhotoProcessingResponse,
    ReportSummaryResponse,
    ReportTimelineEventResponse,
    ReopenReportRequest,
    FlagReportRequest,
    AgencyStatusRequest,
)
from app.infrastructure.repositories import (
    AlreadyConfirmed,
    PhotoStorageUnavailable,
    ReportIdConflict,
    ReportNotFound,
    ReportOwnerCannotConfirm,
    ReportNotOwner,
    ReportPhotoConflict,
    ReportPhotoNotEnabled,
    TriageConflict,
    ReopenNotAllowed,
    NudgeNotAllowed,
    ReportAlreadyFlagged,
    InvalidAgencyAction,
)
from app.infrastructure.photo_storage import (
    InvalidPhoto,
    PhotoUploadConflict,
    PhotoUploadNotFound,
)
from app.services.photo_service import PhotoService
from app.services.report_service import ReportService
from app.infrastructure.worker import ReportJobWorker

router = APIRouter(prefix="/v1/reports", tags=["reports"])


def get_report_service(request: Request) -> ReportService:
    return request.app.state.report_service


def get_report_worker(request: Request) -> ReportJobWorker:
    return request.app.state.report_worker


def get_photo_service(request: Request) -> PhotoService:
    return request.app.state.photo_service


@router.post(
    "",
    response_model=ReportCreatedResponse,
    status_code=201,
    responses={
        200: {
            "model": ReportCreatedResponse,
            "description": "Reenvio idempotente.",
        },
    },
)
def create_report(
    payload: CreateReportRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(require_citizen),
    service: ReportService = Depends(get_report_service),
) -> ReportCreatedResponse:
    report = NewReport(
        id=payload.id,
        description=payload.description,
        has_photo=payload.has_photo,
        category=payload.category,
        latitude=payload.lat,
        longitude=payload.lon,
        location_accuracy_m=payload.location_accuracy_m,
        anonymous=payload.anonymous,
        client_created_at=payload.client_created_at,
        correlation_id=UUID(request.state.correlation_id),
        user_id=None if payload.anonymous else user_id,
        requester_user_id=user_id,
    )

    try:
        result = service.create(report)
    except ClientTimestampOutOfRange as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ReportIdConflict as error:
        raise HTTPException(
            status_code=409,
            detail="Este identificador já foi usado em outra conta.",
        ) from error
    except PhotoStorageUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="O envio de fotos ainda não está disponível.",
        ) from error

    response.status_code = 201 if result.was_created else 200
    if not report.has_photo:
        worker = get_report_worker(request)
        worker.enqueue(report.id)
        background_tasks.add_task(worker.run_once)
    return ReportCreatedResponse(
        id=result.id,
        protocol=result.protocol,
        status=result.status,
        received_at=result.received_at,
        triage_state=result.triage_state,
        upload=result.upload,
    )


@router.get(
    "/{report_id}",
    response_model=ReportDetailResponse,
    responses={404: {"description": "Reporte não encontrado."}},
)
def get_report_detail(
    report_id: UUID,
    _user_id: int = Depends(require_citizen),
    service: ReportService = Depends(get_report_service),
    photos: PhotoService = Depends(get_photo_service),
) -> ReportDetailResponse:
    try:
        detail = service.get_detail(report_id)
    except ReportNotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Reporte não encontrado.",
        ) from error

    return _to_detail_response(detail, _photo_url(photos, report_id))


@router.post(
    "/{report_id}/photo/complete",
    response_model=PhotoProcessingResponse,
    status_code=202,
    responses={
        403: {"description": "Somente o solicitante pode concluir o upload."},
        404: {"description": "Reporte sem upload pendente."},
        409: {"description": "Reporte não aceita upload de foto."},
        422: {"description": "Hash SHA-256 ou imagem inválida."},
    },
)
def complete_report_photo(
    report_id: UUID,
    payload: CompletePhotoRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(require_citizen),
    service: PhotoService = Depends(get_photo_service),
) -> PhotoProcessingResponse:
    try:
        service.complete(report_id, user_id, payload.sha256)
    except ReportNotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Reporte não encontrado.",
        ) from error
    except ReportNotOwner as error:
        raise HTTPException(
            status_code=403,
            detail="Somente o solicitante pode concluir o upload.",
        ) from error
    except ReportPhotoNotEnabled as error:
        raise HTTPException(
            status_code=409,
            detail="Este reporte não aceita foto.",
        ) from error
    except ReportPhotoConflict as error:
        raise HTTPException(
            status_code=409,
            detail="Este reporte já possui outra foto.",
        ) from error
    except PhotoStorageUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="O armazenamento de fotos não está configurado.",
        ) from error
    except PhotoUploadNotFound as error:
        raise HTTPException(
            status_code=409,
            detail="Não há upload pendente para este reporte.",
        ) from error
    except PhotoUploadConflict as error:
        raise HTTPException(
            status_code=409,
            detail="O upload deste reporte já foi concluído.",
        ) from error
    except InvalidPhoto as error:
        raise HTTPException(
            status_code=422,
            detail="A foto enviada é inválida.",
        ) from error

    background_tasks.add_task(get_report_worker(request).run_once)
    return PhotoProcessingResponse()


@router.post(
    "/{report_id}/triage",
    response_model=ReportDetailResponse,
    responses={
        403: {"description": "Triagem permitida somente ao solicitante."},
        404: {"description": "Reporte não encontrado."},
        409: {"description": "Reporte ainda não está disponível para triagem."},
    },
)
def triage_report(
    report_id: UUID,
    payload: TriageRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(require_citizen),
    service: ReportService = Depends(get_report_service),
    photos: PhotoService = Depends(get_photo_service),
) -> ReportDetailResponse:
    try:
        detail = service.apply_triage(report_id, user_id, payload)
    except ReportNotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Reporte não encontrado.",
        ) from error
    except ReportNotOwner as error:
        raise HTTPException(
            status_code=403,
            detail="Somente o solicitante pode confirmar a triagem.",
        ) from error
    except TriageConflict as error:
        raise HTTPException(
            status_code=409,
            detail="O reporte ainda não está disponível para triagem.",
        ) from error
    if detail.agency_id is not None:
        worker = get_report_worker(request)
        worker.enqueue(report_id, "notify_agency")
        background_tasks.add_task(worker.run_once)
        status_event = next(
            (
                event
                for event in reversed(detail.timeline)
                if event.type == "encaminhado"
            ),
            None,
        )
        if status_event is not None:
            worker.enqueue(report_id, f"notify_status_{status_event.id}")
            background_tasks.add_task(worker.run_once)
    return _to_detail_response(detail, _photo_url(photos, report_id))


def _photo_url(service: PhotoService, report_id: UUID) -> str | None:
    try:
        return service.read_url(report_id)
    except PhotoStorageUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="O armazenamento de fotos não está configurado.",
        ) from error


def _to_detail_response(
    detail: ReportDetail,
    photo_url: str | None = None,
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
                actor=event.actor,
                justification=event.justification,
                created_at=event.created_at,
            )
            for event in detail.timeline
        ],
    )


@router.get(
    "/{report_id}/comments",
    response_model=ReportCommentsResponse,
    responses={404: {"description": "Reporte não encontrado."}},
)
def list_report_comments(
    report_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    service: ReportService = Depends(get_report_service),
) -> ReportCommentsResponse:
    try:
        comments = service.get_comments(report_id, limit)
    except ReportNotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Reporte não encontrado.",
        ) from error

    return ReportCommentsResponse(
        items=[
            ReportCommentResponse(
                id=comment.id,
                report_id=comment.report_id,
                content=comment.content,
                created_at=comment.created_at,
            )
            for comment in comments
        ],
        count=len(comments),
    )


@router.post(
    "/{report_id}/comments",
    response_model=ReportCommentResponse,
    status_code=201,
    responses={
        404: {"description": "Reporte não encontrado."},
        422: {"description": "Conteúdo de comentário inválido."},
    },
)
def create_report_comment(
    report_id: UUID,
    payload: CreateReportCommentRequest,
    user_id: int = Depends(require_citizen),
    service: ReportService = Depends(get_report_service),
) -> ReportCommentResponse:
    try:
        comment = service.add_comment(report_id, user_id, payload.content)
    except ReportNotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Reporte não encontrado.",
        ) from error

    return ReportCommentResponse(
        id=comment.id,
        report_id=comment.report_id,
        content=comment.content,
        created_at=comment.created_at,
    )


@router.post(
    "/{report_id}/confirm",
    response_model=ReportConfirmationResponse,
    responses={
        403: {"description": "O autor não pode confirmar o próprio reporte."},
        404: {"description": "Reporte não encontrado."},
        409: {"description": "Usuário já confirmou este grupo."},
    },
)
def confirm_report(
    report_id: UUID,
    user_id: int = Depends(require_citizen),
    service: ReportService = Depends(get_report_service),
) -> ReportConfirmationResponse:
    try:
        count = service.confirm(report_id, user_id)
    except ReportNotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Reporte não encontrado.",
        ) from error
    except ReportOwnerCannotConfirm as error:
        raise HTTPException(
            status_code=403,
            detail="Não é permitido confirmar o próprio reporte.",
        ) from error
    except AlreadyConfirmed as error:
        raise HTTPException(
            status_code=409,
            detail="Você já confirmou este grupo de reportes.",
        ) from error

    return ReportConfirmationResponse(confirmation_count=count)


@router.post("/{report_id}/reopen", response_model=ReportDetailResponse)
def reopen_report(
    report_id: UUID,
    payload: ReopenReportRequest,
    user_id: int = Depends(require_citizen),
    service: ReportService = Depends(get_report_service),
    photos: PhotoService = Depends(get_photo_service),
) -> ReportDetailResponse:
    try:
        detail = service.reopen_report(report_id, user_id, payload.reason)
    except ReportNotFound as error:
        raise HTTPException(status_code=404, detail="Reporte não encontrado.") from error
    except ReportNotOwner as error:
        raise HTTPException(status_code=403, detail="Somente o solicitante pode reabrir.") from error
    except ReopenNotAllowed as error:
        raise HTTPException(status_code=409, detail="A janela de reabertura expirou ou o reporte não está resolvido.") from error
    return _to_detail_response(detail, _photo_url(photos, report_id))


@router.post("/{report_id}/flag", status_code=202)
def flag_report(
    report_id: UUID,
    payload: FlagReportRequest,
    user_id: int = Depends(require_citizen),
    service: ReportService = Depends(get_report_service),
) -> dict[str, str]:
    try:
        service.flag_report(report_id, user_id, payload.reason, payload.note)
    except ReportNotFound as error:
        raise HTTPException(status_code=404, detail="Reporte não encontrado.") from error
    except ReportAlreadyFlagged as error:
        raise HTTPException(status_code=409, detail="Você já sinalizou este reporte.") from error
    return {"status": "received"}


@router.post("/{report_id}/nudge", status_code=202)
def nudge_report(
    report_id: UUID,
    user_id: int = Depends(require_citizen),
    service: ReportService = Depends(get_report_service),
) -> dict[str, str]:
    try:
        service.nudge_report(report_id, user_id)
    except ReportNotFound as error:
        raise HTTPException(status_code=404, detail="Reporte não encontrado.") from error
    except ReportNotOwner as error:
        raise HTTPException(status_code=403, detail="Somente o solicitante pode cobrar.") from error
    except NudgeNotAllowed as error:
        raise HTTPException(status_code=409, detail="Cobrança não permitida ou limite atingido.") from error
    return {"status": "nudge_registered"}
