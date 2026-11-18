import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.core.geo import GeoBox, haversine_m
from app.infrastructure.repositories import (
    InMemoryReportRepository,
    InvalidReportCursor,
)
from app.models.reports import (
    NearbyQuery,
    NewReport,
    ReportStatus,
    ReportSummary,
)
from app.models.taxonomy import ReportCategory
from app.services.report_service import NEARBY_CANDIDATE_LIMIT, ReportService

NOW = datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc)
CENTER = (-23.5505, -46.6333)
# Cerca de 111 m de latitude por milésimo de grau.
METERS_PER_MILLI_DEGREE = 111.195


def summary(
    north_m: float,
    *,
    category: ReportCategory | None = ReportCategory.URBAN_RISK,
    status: ReportStatus = ReportStatus.RECEIVED,
    group_id: str | None = None,
    report_id: UUID | None = None,
    received_at: datetime = NOW,
) -> ReportSummary:
    report_id = report_id or uuid4()
    return ReportSummary(
        id=report_id,
        protocol="RPT-2026-AAAAAA",
        status=status,
        category=category,
        latitude=CENTER[0] + north_m / METERS_PER_MILLI_DEGREE / 1000,
        longitude=CENTER[1],
        received_at=received_at,
        group_id=group_id or str(report_id),
        confirmation_count=0,
    )


class FakeAreaRepository:
    def __init__(self, summaries: list[ReportSummary]) -> None:
        self.summaries = summaries
        self.calls: list[tuple[GeoBox, int]] = []

    def list_in_area(self, box: GeoBox, max_items: int) -> list[ReportSummary]:
        self.calls.append((box, max_items))
        return [s for s in self.summaries if box.contains(s.latitude, s.longitude)]


def query(**overrides: object) -> NearbyQuery:
    values: dict[str, object] = {
        "latitude": CENTER[0],
        "longitude": CENTER[1],
        "radius_m": 1000,
        "category": None,
        "status": None,
        "limit": 20,
        "cursor": None,
    }
    values.update(overrides)
    return NearbyQuery(**values)


class NearbyServiceTests(unittest.TestCase):
    def service_with(self, summaries: list[ReportSummary]) -> ReportService:
        self.repository = FakeAreaRepository(summaries)
        return ReportService(self.repository, object_storage=None, clock=lambda: NOW)

    def test_returns_reports_within_radius_sorted_by_distance(self) -> None:
        far, near, outside = summary(800), summary(100), summary(1500)
        service = self.service_with([far, outside, near])

        page = service.nearby(query())

        self.assertEqual([item.summary.id for item in page.items], [near.id, far.id])
        self.assertAlmostEqual(page.items[0].distance_m, 100, delta=1)
        self.assertIsNone(page.next_cursor)

    def test_radius_and_distance_use_published_coordinates(self) -> None:
        # Exatamente a ~999,6 m, mas a coordenada publicada (4 casas) fica a ~1000,8 m.
        # Filtrar pela posição exata permitiria descobri-la variando o raio.
        edge = replace(summary(0), latitude=CENTER[0] + 0.00899)
        inside = replace(summary(0), latitude=CENTER[0] + 0.0012345)
        service = self.service_with([edge, inside])

        page = service.nearby(query())

        self.assertEqual([item.summary.id for item in page.items], [inside.id])
        item = page.items[0]
        self.assertEqual(item.summary.latitude, round(CENTER[0] + 0.0012345, 4))
        self.assertEqual(
            item.distance_m,
            haversine_m(*CENTER, item.summary.latitude, item.summary.longitude),
        )

    def test_asks_repository_for_bounding_box_of_radius(self) -> None:
        service = self.service_with([])

        service.nearby(query(radius_m=500))

        box, max_items = self.repository.calls[0]
        self.assertTrue(box.contains(*CENTER))
        self.assertLess(box.max_lat - box.min_lat, 0.01)
        self.assertEqual(max_items, NEARBY_CANDIDATE_LIMIT)

    def test_filters_by_category_and_status(self) -> None:
        match = summary(10, category=ReportCategory.HEALTHCARE, status=ReportStatus.RESOLVED)
        other_category = summary(20, status=ReportStatus.RESOLVED)
        other_status = summary(30, category=ReportCategory.HEALTHCARE)
        service = self.service_with([match, other_category, other_status])

        page = service.nearby(
            query(category=ReportCategory.HEALTHCARE, status=ReportStatus.RESOLVED)
        )

        self.assertEqual([item.summary.id for item in page.items], [match.id])

    def test_groups_duplicates_keeping_closest_report(self) -> None:
        group = "grupo-1"
        closest = summary(50, group_id=group)
        farther = summary(300, group_id=group)
        service = self.service_with([farther, closest])

        page = service.nearby(query())

        self.assertEqual([item.summary.id for item in page.items], [closest.id])

    def test_paginates_with_opaque_cursor(self) -> None:
        reports = [summary(100 * (index + 1)) for index in range(5)]
        service = self.service_with(reports)

        first = service.nearby(query(limit=2))
        second = service.nearby(query(limit=2, cursor=first.next_cursor))
        third = service.nearby(query(limit=2, cursor=second.next_cursor))

        ids = [item.summary.id for page in (first, second, third) for item in page.items]
        self.assertEqual(ids, [report.id for report in reports])
        self.assertIsNotNone(first.next_cursor)
        self.assertIsNone(third.next_cursor)

    def test_invalid_cursor_is_rejected(self) -> None:
        service = self.service_with([])

        for cursor in ("nao-base64!", "LTE", "YWJj"):
            with self.subTest(cursor=cursor):
                with self.assertRaises(InvalidReportCursor):
                    service.nearby(query(cursor=cursor))


def new_report(lat: float, lon: float) -> NewReport:
    return NewReport(
        id=uuid4(),
        description="Buraco na via",
        has_photo=False,
        category=None,
        latitude=lat,
        longitude=lon,
        location_accuracy_m=None,
        anonymous=False,
        client_created_at=NOW - timedelta(minutes=1),
        correlation_id=uuid4(),
        user_id=7,
        requester_user_id=7,
    )


class InMemoryAreaQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryReportRepository()
        self.box = GeoBox(min_lat=-23.56, max_lat=-23.54, min_lon=-46.64, max_lon=-46.62)

    def test_returns_only_reports_inside_box(self) -> None:
        inside = self.repository.create(new_report(-23.55, -46.63))
        self.repository.create(new_report(-23.60, -46.63))

        found = self.repository.list_in_area(self.box, max_items=10)

        self.assertEqual([item.id for item in found], [inside.id])

    def test_hides_reports_in_moderation(self) -> None:
        flagged = self.repository.create(new_report(-23.55, -46.63))
        self.repository.flag_report(flagged.id, user_id=99, reason="ofensivo", note=None)

        self.assertEqual(self.repository.list_in_area(self.box, max_items=10), [])

    def test_respects_max_items(self) -> None:
        for _ in range(3):
            self.repository.create(new_report(-23.55, -46.63))

        found = self.repository.list_in_area(self.box, max_items=2)

        self.assertEqual(len(found), 2)


class HaversineSanityTests(unittest.TestCase):
    def test_summary_helper_places_reports_north_of_center(self) -> None:
        item = summary(250)

        self.assertAlmostEqual(
            haversine_m(*CENTER, item.latitude, item.longitude), 250, delta=1
        )


if __name__ == "__main__":
    unittest.main()
