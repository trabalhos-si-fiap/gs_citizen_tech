"""Modelos das rotas dos servidores municipais (painel web)."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.models.reports import AgencyResponse, ReportStatus
from app.models.taxonomy import ReportCategory

STAFF_ROLES = frozenset({"agency", "manager", "moderator", "admin"})
OPEN_STATUSES = frozenset({ReportStatus.FORWARDED, ReportStatus.IN_PROGRESS})
DUE_SOON_WINDOW = timedelta(hours=12)


def is_overdue(
    status: ReportStatus,
    deadline: datetime | None,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    return status in OPEN_STATUSES and deadline is not None and deadline < current


def is_due_soon(
    status: ReportStatus,
    deadline: datetime | None,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    return (
        status in OPEN_STATUSES
        and deadline is not None
        and current <= deadline <= current + DUE_SOON_WINDOW
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
