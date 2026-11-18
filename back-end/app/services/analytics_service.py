from datetime import date, datetime, time, timezone

from app.infrastructure.repositories import ReportRepository


class AnalyticsService:
    def __init__(self, report_repository: ReportRepository) -> None:
        self._report_repository = report_repository

    def get_public_metrics(
        self,
        from_date: date | None,
        to_date: date | None,
        category: str | None,
        agency_id: str | None,
    ) -> dict[str, object]:
        if from_date is not None and to_date is not None and from_date > to_date:
            raise ValueError("O período inicial não pode ser posterior ao final.")

        start = (
            datetime.combine(from_date, time.min, tzinfo=timezone.utc)
            if from_date is not None
            else None
        )
        end = (
            datetime.combine(to_date, time.max, tzinfo=timezone.utc)
            if to_date is not None
            else None
        )
        return self._report_repository.get_public_metrics(
            start,
            end,
            category,
            agency_id,
        )
