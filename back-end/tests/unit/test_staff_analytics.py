import unittest
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.models.reports import ReportStatus
from app.models.staff import StaffAnalyticsRow
from app.models.taxonomy import ReportCategory
from app.services.staff_analytics_service import StaffAnalyticsService

DAY = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
# Dois pontos próximos (mesma região) e um distante.
CENTRO = (-23.5505, -46.6333)
CENTRO_VIZINHO = (-23.5507, -46.6335)
ZONA_NORTE = (-23.4800, -46.6000)


def row(
    *,
    received: datetime,
    resolved: datetime | None = None,
    category=ReportCategory.URBAN_RISK,
    agency=("zeladoria", "Zeladoria"),
    point=CENTRO,
    status: ReportStatus | None = None,
    deadline: datetime | None = None,
) -> StaffAnalyticsRow:
    return StaffAnalyticsRow(
        report_id=uuid4(),
        received_at=received,
        resolved_at=resolved,
        category=category,
        agency_id=agency[0] if agency else None,
        agency_name=agency[1] if agency else None,
        latitude=point[0],
        longitude=point[1],
        status=status
        or (ReportStatus.RESOLVED if resolved else ReportStatus.FORWARDED),
        deadline=deadline,
    )


class FakeRepository:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def staff_analytics_rows(self, agency_id, start, end):
        self.calls.append((agency_id, start, end))
        return [
            r for r in self.rows if start <= r.received_at <= end
        ]


class StaffAnalyticsTests(unittest.TestCase):
    def analytics(self, rows, **kwargs):
        repository = FakeRepository(rows)
        service = StaffAnalyticsService(
            repository, clock=lambda: DAY + timedelta(days=5)
        )
        params = {
            "agency_id": None,
            "from_date": date(2026, 11, 9),
            "to_date": date(2026, 11, 12),
            "bucket": "day",
        }
        params.update(kwargs)
        return service.analytics(**params), repository

    def test_daily_series_counts_opened_and_resolved_per_day(self) -> None:
        result, _ = self.analytics(
            [
                row(received=DAY, resolved=DAY + timedelta(days=1)),
                row(received=DAY),
                row(received=DAY + timedelta(days=1)),
            ]
        )

        series = {p["period"]: p for p in result["timeseries"]}
        self.assertEqual(
            [p["period"] for p in result["timeseries"]],
            ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12"],
        )
        self.assertEqual(series["2026-11-10"]["opened"], 2)
        self.assertEqual(series["2026-11-11"]["opened"], 1)
        self.assertEqual(series["2026-11-11"]["resolved"], 1)
        self.assertEqual(series["2026-11-09"], {"period": "2026-11-09", "opened": 0, "resolved": 0})

    def test_weekly_buckets_start_on_monday(self) -> None:
        result, _ = self.analytics(
            [row(received=DAY), row(received=DAY + timedelta(days=7))],
            from_date=date(2026, 11, 9),
            to_date=date(2026, 11, 22),
            bucket="week",
        )

        self.assertEqual(
            [(p["period"], p["opened"]) for p in result["timeseries"]],
            [("2026-11-09", 1), ("2026-11-16", 1)],
        )

    def test_groups_by_category_agency_and_region(self) -> None:
        result, _ = self.analytics(
            [
                row(received=DAY, point=CENTRO, resolved=DAY + timedelta(hours=10)),
                row(received=DAY, point=CENTRO_VIZINHO),
                row(
                    received=DAY,
                    point=ZONA_NORTE,
                    category=ReportCategory.PUBLIC_TRANSPORT,
                    agency=("transporte", "Transporte"),
                ),
            ]
        )

        categories = {c["category"]: c for c in result["by_category"]}
        self.assertEqual(categories["risco_urbano"]["reports"], 2)
        self.assertEqual(categories["risco_urbano"]["resolved"], 1)
        self.assertEqual(categories["transporte_publico"]["reports"], 1)
        agencies = {a["agency"]["id"]: a for a in result["by_agency"]}
        self.assertEqual(agencies["zeladoria"]["reports"], 2)
        self.assertEqual(agencies["zeladoria"]["avg_resolution_hours"], 10.0)
        regions = result["by_region"]
        self.assertEqual([r["reports"] for r in regions], [2, 1])
        self.assertAlmostEqual(regions[0]["lat"], -23.5506, places=3)

    def test_counts_open_overdue_reports(self) -> None:
        now = DAY + timedelta(days=5)
        result, _ = self.analytics(
            [
                row(received=DAY, deadline=now - timedelta(hours=1)),
                row(received=DAY, deadline=now + timedelta(hours=1)),
            ]
        )

        self.assertEqual(result["totals"]["overdue"], 1)
        self.assertEqual(result["totals"]["reports"], 2)

    def test_scope_and_period_reach_the_repository(self) -> None:
        _, repository = self.analytics([], agency_id="zeladoria")

        agency_id, start, end = repository.calls[0]
        self.assertEqual(agency_id, "zeladoria")
        self.assertEqual(start, datetime(2026, 11, 9, tzinfo=timezone.utc))
        self.assertEqual(end.date(), date(2026, 11, 12))

    def test_defaults_to_last_30_days(self) -> None:
        result, _ = self.analytics([], from_date=None, to_date=None)

        self.assertEqual(len(result["timeseries"]), 30)
        self.assertEqual(result["period"]["to"], "2026-11-15")

    def test_rejects_inverted_or_too_long_period(self) -> None:
        with self.assertRaises(ValueError):
            self.analytics([], from_date=date(2026, 11, 12), to_date=date(2026, 11, 9))
        with self.assertRaises(ValueError):
            self.analytics([], from_date=date(2025, 1, 1), to_date=date(2026, 11, 9))


if __name__ == "__main__":
    unittest.main()
