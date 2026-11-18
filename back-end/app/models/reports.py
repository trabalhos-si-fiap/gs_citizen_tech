"""Modelos de entrada, domínio e resposta do fluxo de reportes."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.classification import ClassificationResult
from app.models.taxonomy import ReportCategory


class ReportStatus(StrEnum):
    RECEIVED = "recebido"
    FORWARDED = "encaminhado"
    IN_PROGRESS = "em_andamento"
    RESOLVED = "resolvido"


class TriageState(StrEnum):
    PENDING_CLASSIFICATION = "pending_classification"
    AWAITING_USER = "awaiting_user"
    CONFIRMED = "confirmed"
    AUTO_CONFIRMED = "auto_confirmed"
    IN_MODERATION = "in_moderation"


class CreateReportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    description: str | None = Field(default=None, max_length=1000)
    has_photo: bool = False
    category: ReportCategory | None = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    location_accuracy_m: float | None = None
    anonymous: bool = False
    client_created_at: datetime

    @model_validator(mode="after")
    def require_description_or_photo(self) -> "CreateReportRequest":
        if not self.has_photo and not (
            self.description and self.description.strip()
        ):
            raise ValueError("Informe uma foto ou uma descrição.")
        if self.client_created_at.utcoffset() is None:
            raise ValueError("client_created_at deve conter fuso horário.")
        return self


class UploadInstruction(BaseModel):
    url: str
    method: str = "PUT"
    headers: dict[str, str] = Field(default_factory=dict)
    max_bytes: int
    expires_at: datetime


class CompletePhotoRequest(BaseModel):
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class PhotoProcessingResponse(BaseModel):
    photo_status: str = "processing"


class ReportCreatedResponse(BaseModel):
    id: UUID
    protocol: str
    status: ReportStatus
    received_at: datetime
    upload: UploadInstruction | None = None
    triage_state: TriageState


class CreateReportCommentRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ReportCommentResponse(BaseModel):
    id: int
    report_id: UUID
    content: str
    created_at: datetime


class ReportCommentsResponse(BaseModel):
    items: list[ReportCommentResponse]
    count: int


class ReportConfirmationResponse(BaseModel):
    confirmation_count: int


class ReopenReportRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class FlagReportRequest(BaseModel):
    reason: str = Field(pattern="^(ofensivo|dados_pessoais|falso|duplicado_abusivo|outro)$")
    note: str | None = Field(default=None, max_length=500)


class AgencyStatusRequest(BaseModel):
    action: str = Field(pattern="^(in_progress|resolved|contest)$")
    deadline: datetime | None = None
    justification: str | None = Field(default=None, max_length=1000)


class ReportSummaryResponse(BaseModel):
    id: UUID
    protocol: str
    status: ReportStatus
    category: ReportCategory | None
    lat: float
    lon: float
    received_at: datetime
    group_id: str
    confirmation_count: int


class ReportTimelineEventResponse(BaseModel):
    id: int
    type: str
    actor: str
    justification: str | None = None
    created_at: datetime


class AgencyResponse(BaseModel):
    id: str
    name: str


class ReportDetailResponse(ReportSummaryResponse):
    description: str | None
    photo_url: str | None = None
    anonymous: bool
    has_photo: bool
    triage_state: TriageState
    classification: ClassificationResult | None = None
    agency: AgencyResponse | None = None
    deadline: datetime | None = None
    timeline: list[ReportTimelineEventResponse]


class NearbyItemResponse(BaseModel):
    """Item público do mapa: sem protocolo, descrição, foto ou autor."""

    id: UUID
    group_id: str | None
    status: ReportStatus
    category: ReportCategory | None
    subcategory: str | None = None
    lat: float
    lon: float
    confirmation_count: int
    received_at: datetime
    distance_m: int


class NearbyPageResponse(BaseModel):
    items: list[NearbyItemResponse]
    next_cursor: str | None


class UserReportPageResponse(BaseModel):
    items: list[ReportSummaryResponse]
    next_cursor: str | None


@dataclass(frozen=True)
class NewReport:
    id: UUID
    description: str | None
    has_photo: bool
    category: ReportCategory | None
    latitude: float
    longitude: float
    location_accuracy_m: float | None
    anonymous: bool
    client_created_at: datetime
    correlation_id: UUID
    user_id: int | None
    requester_user_id: int

    def __post_init__(self) -> None:
        if not self.has_photo and not (
            self.description and self.description.strip()
        ):
            raise ValueError("Informe uma foto ou uma descrição.")
        if not -90 <= self.latitude <= 90:
            raise ValueError("Latitude fora do intervalo permitido.")
        if not -180 <= self.longitude <= 180:
            raise ValueError("Longitude fora do intervalo permitido.")
        if self.client_created_at.utcoffset() is None:
            raise ValueError("client_created_at deve conter fuso horário.")


@dataclass(frozen=True)
class PersistedReport:
    id: UUID
    protocol: str
    received_at: datetime
    was_created: bool
    status: ReportStatus = ReportStatus.RECEIVED
    triage_state: TriageState = TriageState.PENDING_CLASSIFICATION


@dataclass(frozen=True)
class ReportComment:
    id: int
    report_id: UUID
    user_id: int
    content: str
    created_at: datetime


@dataclass(frozen=True)
class ReportTimelineEvent:
    id: int
    type: str
    actor: str
    justification: str | None
    created_at: datetime


@dataclass(frozen=True)
class ReportSummary:
    id: UUID
    protocol: str
    status: ReportStatus
    category: ReportCategory | None
    latitude: float
    longitude: float
    received_at: datetime
    group_id: str
    confirmation_count: int


@dataclass(frozen=True)
class NearbyQuery:
    latitude: float
    longitude: float
    radius_m: int
    category: ReportCategory | None
    status: ReportStatus | None
    limit: int
    cursor: str | None


@dataclass(frozen=True)
class NearbyReport:
    summary: ReportSummary
    distance_m: float


@dataclass(frozen=True)
class NearbyPage:
    items: list[NearbyReport]
    next_cursor: str | None


@dataclass(frozen=True)
class ReportDetail:
    summary: ReportSummary
    description: str | None
    anonymous: bool
    has_photo: bool
    triage_state: TriageState
    classification: ClassificationResult | None
    agency_id: str | None
    agency_name: str | None
    deadline: datetime | None
    timeline: list[ReportTimelineEvent]


@dataclass(frozen=True)
class ReportCreationResult:
    id: UUID
    protocol: str
    status: ReportStatus
    received_at: datetime
    triage_state: TriageState
    was_created: bool
    upload: UploadInstruction | None


class ClientTimestampOutOfRange(ValueError):
    """Data original do cliente fora da janela aceita pelo servidor."""
