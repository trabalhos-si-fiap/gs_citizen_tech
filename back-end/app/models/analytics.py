from datetime import date

from pydantic import BaseModel


class MetricsPeriod(BaseModel):
    from_: date | None = None
    to: date | None = None


class MetricsTotals(BaseModel):
    reports: int
    avg_response_hours: float | None
    resolution_rate: float | None
    recurrence: int


class AgencyMetrics(BaseModel):
    agency: dict[str, str]
    reports: int
    avg_response_hours: float | None
    resolution_rate: float | None


class PublicMetrics(BaseModel):
    period: MetricsPeriod
    totals: MetricsTotals
    by_agency: list[AgencyMetrics]
