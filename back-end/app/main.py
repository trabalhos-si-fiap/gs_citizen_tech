from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import http_error_handler, validation_error_handler
from app.api.middleware import correlation_id_middleware
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.me import router as me_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.moderation import router as moderation_router
from app.api.routes.reports import router as reports_router
from app.api.routes.uploads import photos_router, router as uploads_router
from app.core.config import settings
from app.infrastructure.classifiers import build_classifier
from app.infrastructure.database import OracleDatabase
from app.infrastructure.job_queue import InMemoryJobQueue, OracleJobQueue
from app.infrastructure.mailer import SmtpAgencyMailer, SmtpOtpMailer
from app.infrastructure.photo_storage import LocalPhotoStorage
from app.infrastructure.push import build_push_sender
from app.infrastructure.repositories import (
    InMemoryAuthRepository,
    InMemoryReportRepository,
    OracleAuthRepository,
    OracleReportRepository,
)
from app.services.auth_service import AuthService
from app.services.classification_service import ClassificationService
from app.services.notification_service import (
    AgencyNotificationService,
    CitizenNotificationService,
)
from app.services.photo_service import PhotoService
from app.services.report_service import ReportService
from app.services.privacy_service import PrivacyService
from app.services.analytics_service import AnalyticsService
from app.services.visual_verification_service import VisualVerificationService
from app.infrastructure.worker import ReportJobWorker


database: OracleDatabase | None = None
if settings.report_repository == "memory":
    if settings.environment != "development":
        raise RuntimeError(
            "O repositório em memória só pode ser usado em development."
        )
    report_repository = InMemoryReportRepository()
    auth_repository = InMemoryAuthRepository()
elif settings.report_repository == "oracle":
    database = OracleDatabase(settings)
    report_repository = OracleReportRepository(database)
    auth_repository = OracleAuthRepository(database)
else:
    raise RuntimeError(
        f"Repositório não suportado: {settings.report_repository}"
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if database is not None:
        database.open()
    try:
        yield
    finally:
        if database is not None:
            database.close()


app = FastAPI(
    title="Reclame Já API",
    description="API para registro, encaminhamento e acompanhamento de ocorrências urbanas.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
)

app.middleware("http")(correlation_id_middleware)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)

classification_service = ClassificationService(build_classifier(settings))
photo_storage = LocalPhotoStorage()
job_queue = (
    OracleJobQueue(database)
    if database is not None
    else InMemoryJobQueue()
)
app.state.report_service = ReportService(
    report_repository,
    photo_storage,
)
app.state.photo_service = PhotoService(
    report_repository,
    photo_storage,
    job_queue,
)
app.state.notification_service = AgencyNotificationService(
    report_repository,
    SmtpAgencyMailer(settings),
    app.state.photo_service,
)
app.state.citizen_notification_service = CitizenNotificationService(
    report_repository,
    build_push_sender(settings),
)
app.state.visual_verification_service = VisualVerificationService(
    settings.visual_verification_enabled,
    settings.visual_verification_provider,
)
app.state.report_worker = ReportJobWorker(
    job_queue,
    report_repository,
    classification_service,
    photo_storage=photo_storage,
    notification_service=app.state.notification_service,
    citizen_notification_service=app.state.citizen_notification_service,
    visual_verification_service=app.state.visual_verification_service,
)
app.state.auth_service = AuthService(auth_repository, SmtpOtpMailer(settings))
app.state.privacy_service = PrivacyService(auth_repository, report_repository)
app.state.analytics_service = AnalyticsService(report_repository)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(reports_router)
app.include_router(uploads_router)
app.include_router(photos_router)
app.include_router(me_router)
app.include_router(analytics_router)
app.include_router(moderation_router)


@app.get("/health", tags=["public"])
def get_health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {"message": "Reclame Já API funcionando"}
