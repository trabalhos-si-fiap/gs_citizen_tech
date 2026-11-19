"""Modelos das rotas dos servidores municipais (painel web)."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.reports import AgencyResponse, ReportStatus
from app.models.taxonomy import ReportCategory

STAFF_ROLES = frozenset({"agency", "manager", "moderator", "admin"})
OPEN_STATUSES = frozenset({ReportStatus.FORWARDED, ReportStatus.IN_PROGRESS})
DUE_SOON_WINDOW = timedelta(hours=12)


def _as_utc(value: datetime) -> datetime:
    # O driver Oracle devolve TIMESTAMP sem fuso; os prazos são gravados em UTC.
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def is_overdue(
    status: ReportStatus,
    deadline: datetime | None,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    return (
        status in OPEN_STATUSES
        and deadline is not None
        and _as_utc(deadline) < current
    )


def is_due_soon(
    status: ReportStatus,
    deadline: datetime | None,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    return (
        status in OPEN_STATUSES
        and deadline is not None
        and current <= _as_utc(deadline) <= current + DUE_SOON_WINDOW
    )


@dataclass(frozen=True)
class StaffContext:
    user_id: int
    email: str | None
    role: str
    agency_id: str | None

    @property
    def scope(self) -> Literal["agency", "all"]:
        return "agency" if self.agency_id is not None else "all"


@dataclass(frozen=True)
class StaffReportItem:
    id: UUID
    protocol: str
    status: ReportStatus
    category: ReportCategory | None
    urgency: str | None
    immediate_risk: bool | None
    description: str | None
    latitude: float
    longitude: float
    received_at: datetime
    deadline: datetime | None
    overdue: bool
    agency_id: str | None
    agency_name: str | None
    confirmation_count: int


@dataclass(frozen=True)
class StaffSummary:
    total: int
    by_status: dict[str, int]
    overdue: int
    due_soon: int


class StaffProfileResponse(BaseModel):
    id: str
    email: str | None
    role: str
    scope: Literal["agency", "all"]
    agency: AgencyResponse | None = None


class StaffAgenciesResponse(BaseModel):
    items: list[AgencyResponse]


class StaffSummaryResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    overdue: int
    due_soon: int


class StaffReportItemResponse(BaseModel):
    id: UUID
    protocol: str
    status: ReportStatus
    category: ReportCategory | None
    urgency: str | None
    immediate_risk: bool | None
    description: str | None
    lat: float
    lon: float
    received_at: datetime
    deadline: datetime | None
    overdue: bool
    agency: AgencyResponse | None
    confirmation_count: int


class StaffReportPageResponse(BaseModel):
    items: list[StaffReportItemResponse]
    next_cursor: str | None


class StaffRedirectRequest(BaseModel):
    """Redireciona o reporte a outro órgão; a justificativa vai para a timeline."""

    agency_id: str = Field(min_length=1, max_length=64)
    justification: str = Field(max_length=1000)
    # Sem prazo informado, o novo órgão recebe REDIRECT_DEADLINE_HOURS.
    deadline: datetime | None = None

    @field_validator("justification")
    @classmethod
    def _justification_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Justificativa obrigatória.")
        return value


class StaffModerationRequest(BaseModel):
    """Decisão da moderação; categoria só na aprovação (reclassifica e roteia)."""

    justification: str = Field(max_length=1000)
    category: ReportCategory | None = None
    subcategory: str | None = Field(default=None, max_length=64)

    @field_validator("justification")
    @classmethod
    def _justification_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Justificativa obrigatória.")
        return value
