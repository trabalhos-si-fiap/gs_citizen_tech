import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.infrastructure.repositories import InMemoryReportRepository, TriageConflict
from app.models.classification import ClassificationResult, TriageRequest
from app.models.reports import NewReport, ReportStatus, TriageState
from app.models.taxonomy import ReportCategory
from app.services.report_service import ReportService

MINUTES = 10


def classification(**overrides: object) -> ClassificationResult:
    values: dict[str, object] = {
        "category": ReportCategory.URBAN_RISK,
        "subcategory": None,
        "urgency": "media",
        "confidence": 0.9,
        "immediate_risk": False,
        "model": "fake",
        "source": "ai",
    }
    values.update(overrides)
    return ClassificationResult(**values)


def new_report(owner: int = 7) -> NewReport:
    return NewReport(
        id=uuid4(),
        description="Árvore caída bloqueando a calçada",
        has_photo=False,
        category=None,
        latitude=-23.55,
        longitude=-46.63,
        location_accuracy_m=None,
        anonymous=False,
        client_created_at=datetime.now(timezone.utc),
        correlation_id=uuid4(),
        user_id=owner,
        requester_user_id=owner,
    )


class TriageAutoConfirmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryReportRepository()
        self.now = datetime.now(timezone.utc)

    def service(self, minutes_after: float) -> ReportService:
        moment = self.now + timedelta(minutes=minutes_after)
        return ReportService(
            self.repository,
            object_storage=None,
            clock=lambda: moment,
            triage_auto_confirm_minutes=MINUTES,
        )

    def classified(self, result: ClassificationResult | None = None):
        report = self.repository.create(new_report())
        self.repository.record_classification(report.id, result or classification())
        return report.id

    def test_confirms_suggestion_after_deadline_and_forwards(self) -> None:
        report_id = self.classified()

        confirmed = self.service(MINUTES + 1).auto_confirm_due_triage()

        detail = self.repository.get_detail(report_id)
        self.assertEqual(confirmed, 1)
        self.assertEqual(detail.triage_state, TriageState.AUTO_CONFIRMED)
        self.assertEqual(detail.summary.status, ReportStatus.FORWARDED)
        events = [(event.type, event.actor) for event in detail.timeline]
        self.assertIn(("classificacao_confirmada", "system"), events)
        self.assertIn(("encaminhado", "system"), events)

    def test_keeps_waiting_before_deadline(self) -> None:
        report_id = self.classified()

        confirmed = self.service(MINUTES - 1).auto_confirm_due_triage()

        self.assertEqual(confirmed, 0)
        self.assertEqual(
            self.repository.get_detail(report_id).triage_state,
            TriageState.AWAITING_USER,
        )

    def test_sends_unclassified_report_to_moderation(self) -> None:
        report_id = self.classified(
            classification(
                category=ReportCategory.TO_CLASSIFY,
                subcategory="a_classificar",
                source="none",
            )
        )

        self.service(MINUTES + 1).auto_confirm_due_triage()

        detail = self.repository.get_detail(report_id)
        self.assertEqual(detail.triage_state, TriageState.IN_MODERATION)
        self.assertEqual(detail.summary.status, ReportStatus.RECEIVED)

    def test_sends_escalated_suggestion_to_moderation(self) -> None:
        report_id = self.classified(classification(confidence=0.4, escalated=True))

        self.service(MINUTES + 1).auto_confirm_due_triage()

        self.assertEqual(
            self.repository.get_detail(report_id).triage_state,
            TriageState.IN_MODERATION,
        )

    def test_ignores_report_already_confirmed_by_citizen(self) -> None:
        report_id = self.classified()
        self.service(0).apply_triage(report_id, 7, TriageRequest(action="confirm"))

        confirmed = self.service(MINUTES + 1).auto_confirm_due_triage()

        detail = self.repository.get_detail(report_id)
        self.assertEqual(confirmed, 0)
        self.assertEqual(detail.triage_state, TriageState.CONFIRMED)

    def test_concurrent_confirmation_is_skipped_without_error(self) -> None:
        report_id = self.classified()
        service = self.service(MINUTES + 1)
        original = self.repository.apply_triage

        def citizen_wins_race(*args, **kwargs):
            original(report_id, 7, "confirm", classification(), None, None)
            raise TriageConflict

        self.repository.apply_triage = citizen_wins_race  # type: ignore[method-assign]

        self.assertEqual(service.auto_confirm_due_triage(), 0)

    def test_citizen_cannot_triage_after_auto_confirmation(self) -> None:
        report_id = self.classified()
        self.service(MINUTES + 1).auto_confirm_due_triage()

        with self.assertRaises(TriageConflict):
            self.service(MINUTES + 2).apply_triage(
                report_id, 7, TriageRequest(action="confirm")
            )


if __name__ == "__main__":
    unittest.main()
