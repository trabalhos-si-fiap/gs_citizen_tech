import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.core.geo import GeoBox
from app.infrastructure.repositories import InMemoryReportRepository, TriageConflict
from app.models.classification import ClassificationResult, TriageRequest
from app.models.reports import NearbyQuery, NewReport, ReportStatus, TriageState
from app.models.taxonomy import ReportCategory
from app.services.dedup_service import DeduplicationService, text_similarity
from app.services.report_service import ReportService

LAT, LON = -23.5505, -46.6333
# ~1 m de latitude.
METER = 1 / 111_195


class TextSimilarityTests(unittest.TestCase):
    def test_identical_text_is_fully_similar(self) -> None:
        self.assertEqual(text_similarity("Buraco na rua", "Buraco na rua"), 1.0)

    def test_ignores_case_accents_and_punctuation(self) -> None:
        self.assertEqual(
            text_similarity("Árvore CAÍDA na calçada!", "arvore caida na calcada"),
            1.0,
        )

    def test_unrelated_texts_are_dissimilar(self) -> None:
        self.assertLess(
            text_similarity("Buraco enorme na avenida", "Fila longa no posto de saúde"),
            0.3,
        )

    def test_empty_text_has_no_similarity(self) -> None:
        self.assertEqual(text_similarity("", "Buraco"), 0.0)


def classification(
    category: ReportCategory = ReportCategory.URBAN_RISK,
    subcategory: str | None = None,
) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        subcategory=subcategory,
        urgency="media",
        confidence=0.9,
        immediate_risk=False,
        model="fake",
        source="ai",
    )


class DeduplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryReportRepository()
        self.now = datetime.now(timezone.utc)
        self.dedup = self.service()

    def service(self, days_after: float = 0) -> DeduplicationService:
        moment = self.now + timedelta(days=days_after)
        return DeduplicationService(
            self.repository,
            radius_m=50,
            window_days=14,
            text_threshold=0.8,
            clock=lambda: moment,
        )

    def report(
        self,
        *,
        north_m: float = 0,
        description: str | None = "Buraco grande na calçada da esquina",
        category: ReportCategory = ReportCategory.URBAN_RISK,
        subcategory: str | None = None,
        owner: int = 7,
    ) -> UUID:
        persisted = self.repository.create(
            NewReport(
                id=uuid4(),
                description=description,
                has_photo=description is None,
                category=None,
                latitude=LAT + north_m * METER,
                longitude=LON,
                location_accuracy_m=None,
                anonymous=False,
                client_created_at=self.now,
                correlation_id=uuid4(),
                user_id=owner,
                requester_user_id=owner,
            )
        )
        self.repository.record_classification(
            persisted.id, classification(category, subcategory)
        )
        return persisted.id

    def group_of(self, report_id: UUID) -> str:
        return self.repository.get_detail(report_id).summary.group_id

    def test_links_similar_nearby_report_to_existing_group(self) -> None:
        original = self.report()
        duplicate = self.report(north_m=20, owner=8)

        linked = self.dedup.link_if_duplicate(duplicate)

        self.assertTrue(linked)
        self.assertEqual(self.group_of(duplicate), self.group_of(original))
        detail = self.repository.get_detail(duplicate)
        self.assertEqual(detail.triage_state, TriageState.AUTO_CONFIRMED)
        self.assertIn("vinculado_grupo", [event.type for event in detail.timeline])

    def test_original_report_stays_canonical_and_awaiting_triage(self) -> None:
        original = self.report()
        duplicate = self.report(north_m=20, owner=8)

        self.dedup.link_if_duplicate(duplicate)

        self.assertEqual(self.group_of(original), str(original))
        self.assertEqual(
            self.repository.get_detail(original).triage_state,
            TriageState.AWAITING_USER,
        )

    def test_does_not_link_other_category(self) -> None:
        self.report()
        other = self.report(north_m=10, category=ReportCategory.HEALTHCARE)

        self.assertFalse(self.dedup.link_if_duplicate(other))

    def test_does_not_link_different_subcategories(self) -> None:
        self.report(subcategory="calcada_danificada")
        other = self.report(north_m=10, subcategory="iluminacao_falha")

        self.assertFalse(self.dedup.link_if_duplicate(other))

    def test_does_not_link_beyond_radius(self) -> None:
        self.report()
        far = self.report(north_m=60)

        self.assertFalse(self.dedup.link_if_duplicate(far))

    def test_does_not_link_dissimilar_text(self) -> None:
        self.report()
        other = self.report(north_m=10, description="Poste caído com fios soltos")

        self.assertFalse(self.dedup.link_if_duplicate(other))

    def test_without_text_requires_half_the_radius(self) -> None:
        self.report()
        far_photo_only = self.report(north_m=35, description=None)
        self.assertFalse(self.dedup.link_if_duplicate(far_photo_only))

        near_photo_only = self.report(north_m=-20, description=None)
        self.assertTrue(self.dedup.link_if_duplicate(near_photo_only))

    def test_ignores_reports_outside_time_window(self) -> None:
        self.report()
        late = self.report(north_m=10)

        self.assertFalse(self.service(days_after=15).link_if_duplicate(late))

    def test_ignores_resolved_groups(self) -> None:
        original = self.report()
        self.repository.update_agency_status(original, "resolved", None, "Consertado")
        duplicate = self.report(north_m=10)

        self.assertFalse(self.dedup.link_if_duplicate(duplicate))

    def test_ignores_groups_in_moderation(self) -> None:
        original = self.report()
        self.repository.mark_for_moderation(original)
        duplicate = self.report(north_m=10)

        self.assertFalse(self.dedup.link_if_duplicate(duplicate))

    def test_prefers_most_similar_group(self) -> None:
        self.report(north_m=5, description="Buraco grande na calçada")
        best = self.report(north_m=30, description="Buraco grande na calçada da esquina")
        duplicate = self.report(north_m=20, description="Buraco grande na calçada da esquina!")

        self.dedup.link_if_duplicate(duplicate)

        self.assertEqual(self.group_of(duplicate), self.group_of(best))

    def test_does_not_link_after_citizen_triage(self) -> None:
        self.report()
        duplicate = self.report(north_m=10)
        ReportService(self.repository, None).apply_triage(
            duplicate, 7, TriageRequest(action="confirm")
        )

        self.assertFalse(self.dedup.link_if_duplicate(duplicate))

    def test_member_inherits_canonical_status(self) -> None:
        original = self.report()
        duplicate = self.report(north_m=10, owner=8)
        self.dedup.link_if_duplicate(duplicate)

        self.repository.update_agency_status(
            original, "in_progress", self.now + timedelta(days=2), None
        )

        self.assertEqual(
            self.repository.get_detail(duplicate).summary.status,
            ReportStatus.IN_PROGRESS,
        )

    def test_member_triage_is_closed_and_not_swept(self) -> None:
        self.report()
        duplicate = self.report(north_m=10)
        self.dedup.link_if_duplicate(duplicate)

        with self.assertRaises(TriageConflict):
            ReportService(self.repository, None).apply_triage(
                duplicate, 7, TriageRequest(action="confirm")
            )
        self.assertNotIn(
            duplicate,
            self.repository.list_triage_due(self.now + timedelta(hours=1), 10),
        )

    def test_group_counts_member(self) -> None:
        original = self.report()
        duplicate = self.report(north_m=10, owner=8)

        self.dedup.link_if_duplicate(duplicate)

        self.assertEqual(self.repository.group_member_count(self.group_of(original)), 2)

    def test_nearby_shows_one_item_per_group(self) -> None:
        self.report()
        duplicate = self.report(north_m=10, owner=8)
        self.dedup.link_if_duplicate(duplicate)

        page = ReportService(self.repository, None).nearby(
            NearbyQuery(LAT, LON, 1000, None, None, 20, None)
        )

        self.assertEqual(len(page.items), 1)

    def test_staff_list_shows_one_item_per_group(self) -> None:
        original = self.report()
        duplicate = self.report(north_m=10, owner=8)
        self.dedup.link_if_duplicate(duplicate)

        items = self.repository.list_staff_reports(
            None, None, None, False, None, 20, None
        )

        self.assertEqual([item.id for item in items], [original])

    def test_candidate_query_receives_bounding_box_and_window(self) -> None:
        calls: list[tuple[GeoBox, datetime]] = []
        original = self.repository.list_dedup_candidates

        def spy(report_id, box, since, max_items):
            calls.append((box, since))
            return original(report_id, box, since, max_items)

        self.repository.list_dedup_candidates = spy  # type: ignore[method-assign]
        self.dedup.link_if_duplicate(self.report())

        box, since = calls[0]
        self.assertTrue(box.contains(LAT, LON))
        self.assertLess(box.max_lat - box.min_lat, 0.002)
        self.assertEqual(since, self.now - timedelta(days=14))


if __name__ == "__main__":
    unittest.main()
