"""Analítica do painel: série temporal e agregações por categoria, órgão e região."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Literal, Protocol

from app.infrastructure.geohash import encode_geohash
from app.models.staff import StaffAnalyticsRow, is_overdue

DEFAULT_PERIOD_DAYS = 30
MAX_PERIOD_DAYS = 366
# Sem base de bairros, a "região" é uma célula de geohash de 6 caracteres
# (cerca de 1,2 km x 0,6 km); o painel mostra o centro de cada célula.
REGION_PRECISION = 6
MAX_REGIONS = 20

Bucket = Literal["day", "week"]


class AnalyticsRepository(Protocol):
    def staff_analytics_rows(
        self,
        agency_id: str | None,
        start: datetime,
        end: datetime,
    ) -> list[StaffAnalyticsRow]: ...


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class StaffAnalyticsService:
    def __init__(
        self,
        repository: AnalyticsRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def analytics(
        self,
        agency_id: str | None,
        from_date: date | None,
        to_date: date | None,
        bucket: Bucket,
    ) -> dict[str, object]:
        now = self._clock()
        to_date = to_date or now.date()
        from_date = from_date or to_date - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
        if from_date > to_date:
            raise ValueError("O período inicial não pode ser posterior ao final.")
        if (to_date - from_date).days + 1 > MAX_PERIOD_DAYS:
            raise ValueError("O período máximo é de 366 dias.")

        start = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
        end = datetime.combine(to_date, time.max, tzinfo=timezone.utc)
        rows = self._repository.staff_analytics_rows(agency_id, start, end)

        return {
            "period": {
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
                "bucket": bucket,
            },
            "totals": self._totals(rows, now),
            "timeseries": self._timeseries(rows, from_date, to_date, bucket),
            "by_category": self._by_category(rows),
            "by_agency": self._by_agency(rows, now),
            "by_region": self._by_region(rows),
        }

    @staticmethod
    def _bucket_start(day: date, bucket: Bucket) -> date:
        return day - timedelta(days=day.weekday()) if bucket == "week" else day

    def _timeseries(
        self,
        rows: list[StaffAnalyticsRow],
        from_date: date,
        to_date: date,
        bucket: Bucket,
    ) -> list[dict[str, object]]:
        step = timedelta(days=7 if bucket == "week" else 1)
        periods: dict[date, dict[str, int]] = {}
        current = self._bucket_start(from_date, bucket)
        while current <= to_date:
            periods[current] = {"opened": 0, "resolved": 0}
            current += step

        for row in rows:
            opened = self._bucket_start(_as_utc(row.received_at).date(), bucket)
            if opened in periods:
                periods[opened]["opened"] += 1
            # Conta a conclusão no período em que aconteceu, dentre os reportes
            # abertos no intervalo consultado.
            if row.resolved_at is not None:
                resolved = self._bucket_start(_as_utc(row.resolved_at).date(), bucket)
                if resolved in periods:
                    periods[resolved]["resolved"] += 1

        return [
            {"period": period.isoformat(), **counts}
            for period, counts in periods.items()
        ]

    @staticmethod
    def _totals(rows: list[StaffAnalyticsRow], now: datetime) -> dict[str, int]:
        resolved = sum(1 for row in rows if row.resolved_at is not None)
        return {
            "reports": len(rows),
            "resolved": resolved,
            "open": len(rows) - resolved,
            "overdue": sum(
                1 for row in rows if is_overdue(row.status, row.deadline, now)
            ),
        }

    @staticmethod
    def _by_category(rows: list[StaffAnalyticsRow]) -> list[dict[str, object]]:
        groups: dict[str, list[StaffAnalyticsRow]] = defaultdict(list)
        for row in rows:
            key = row.category.value if row.category is not None else "a_classificar"
            groups[key].append(row)
        return sorted(
            (
                {
                    "category": key,
                    "reports": len(items),
                    "resolved": sum(1 for r in items if r.resolved_at is not None),
                }
                for key, items in groups.items()
            ),
            key=lambda item: (-item["reports"], item["category"]),
        )

    @staticmethod
    def _by_agency(
        rows: list[StaffAnalyticsRow], now: datetime
    ) -> list[dict[str, object]]:
        groups: dict[str, list[StaffAnalyticsRow]] = defaultdict(list)
        for row in rows:
            if row.agency_id is not None:
                groups[row.agency_id].append(row)
        result = []
        for agency_id, items in groups.items():
            durations = [
                (_as_utc(r.resolved_at) - _as_utc(r.received_at)).total_seconds() / 3600
                for r in items
                if r.resolved_at is not None
            ]
            result.append(
                {
                    "agency": {"id": agency_id, "name": items[0].agency_name},
                    "reports": len(items),
                    "resolved": len(durations),
                    "overdue": sum(
                        1 for r in items if is_overdue(r.status, r.deadline, now)
                    ),
                    "avg_resolution_hours": (
                        round(sum(durations) / len(durations), 1)
                        if durations
                        else None
                    ),
                }
            )
        return sorted(result, key=lambda item: (-item["reports"], item["agency"]["id"]))

    @staticmethod
    def _by_region(rows: list[StaffAnalyticsRow]) -> list[dict[str, object]]:
        groups: dict[str, list[StaffAnalyticsRow]] = defaultdict(list)
        for row in rows:
            groups[
                encode_geohash(row.latitude, row.longitude, REGION_PRECISION)
            ].append(row)
        regions = [
            {
                "region": cell,
                "lat": round(sum(r.latitude for r in items) / len(items), 4),
                "lon": round(sum(r.longitude for r in items) / len(items), 4),
                "reports": len(items),
                "resolved": sum(1 for r in items if r.resolved_at is not None),
            }
            for cell, items in groups.items()
        ]
        regions.sort(key=lambda item: (-item["reports"], item["region"]))
        return regions[:MAX_REGIONS]
