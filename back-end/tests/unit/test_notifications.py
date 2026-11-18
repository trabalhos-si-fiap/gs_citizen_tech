import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

from app.core.config import settings
from app.infrastructure.mailer import MailDeliveryError, SmtpAgencyMailer
from app.infrastructure.repositories import InMemoryReportRepository
from app.models.classification import ClassificationResult, RouteDecision
from app.models.notifications import AgencyAssignment, PushMessage
from app.models.reports import NewReport, ReportStatus, TriageState
from app.services.notification_service import (
    AgencyNotificationService,
    CitizenNotificationService,
)
from app.services.photo_service import PhotoService


class AgencyNotificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report_id = uuid4()
        self.repository = InMemoryReportRepository()
        self.repository.create(
            NewReport(
                id=self.report_id,
                description="Buraco na rua principal.",
                has_photo=False,
                category=None,
                latitude=-23.55,
                longitude=-46.63,
                location_accuracy_m=None,
                anonymous=True,
                client_created_at=datetime.now(timezone.utc),
                correlation_id=uuid4(),
                user_id=None,
                requester_user_id=23,
            )
        )
        classification = ClassificationResult(
            category="risco_urbano",
            subcategory="buraco_via",
            urgency="media",
            confidence=0.9,
            immediate_risk=False,
            model="fake",
            source="ai",
        )
        self.repository.record_classification(self.report_id, classification)
        route = RouteDecision(
            rule_id="risco-urbano-geral",
            rule_version=1,
            territory_id="municipio_demo",
            agency_id="prefeitura-demo-zeladoria",
            agency_name="Prefeitura Demo — Zeladoria",
            deadline_hours=72,
            agency_email="zeladoria@example.org",
        )
        self.repository.apply_triage(
            self.report_id,
            23,
            "confirm",
            classification,
            route,
            datetime.now(timezone.utc) + timedelta(hours=72),
        )

    def test_notification_uses_agency_contact_without_requester_data(self) -> None:
        mailer = Mock()
        photo_service = Mock(spec=PhotoService)
        service = AgencyNotificationService(
            self.repository,
            mailer,
            photo_service,
        )

        service.notify_agency(self.report_id)

        assignment = mailer.send_assignment.call_args.args[0]
        self.assertEqual(assignment.email, "zeladoria@example.org")
        self.assertTrue(assignment.protocol.startswith("RPT-"))
        self.assertEqual(assignment.description, "Buraco na rua principal.")
        self.assertIsNone(assignment.photo_url)
        self.assertFalse(hasattr(assignment, "user_id"))
        self.assertFalse(hasattr(assignment, "correlation_id"))
        self.assertEqual(
            self.repository.get_detail(self.report_id).triage_state,
            TriageState.CONFIRMED,
        )

    @patch("app.infrastructure.mailer.smtplib.SMTP")
    def test_smtp_message_contains_operational_fields_only(self, smtp_factory) -> None:
        smtp = smtp_factory.return_value.__enter__.return_value
        assignment = AgencyAssignment(
            email="zeladoria@example.org",
            agency_name="Prefeitura Demo",
            report_id=uuid4(),
            protocol="RPT-2026-ABC123",
            category="risco_urbano",
            subcategory="buraco_via",
            urgency="media",
            description="Buraco na rua.",
            latitude=-23.55,
            longitude=-46.63,
            deadline=datetime(2026, 11, 20, tzinfo=timezone.utc),
            photo_url=None,
        )

        SmtpAgencyMailer(settings).send_assignment(assignment)

        message = smtp.send_message.call_args.args[0]
        body = message.get_content()
        self.assertEqual(message["To"], "zeladoria@example.org")
        self.assertIn("RPT-2026-ABC123", body)
        self.assertNotIn("correlation_id", body)
        self.assertNotIn("user_id", body)

    @patch("app.infrastructure.mailer.smtplib.SMTP")
    def test_smtp_rejects_header_injection_in_recipient(self, smtp_factory) -> None:
        assignment = AgencyAssignment(
            email="zeladoria@example.org\nBcc: other@example.org",
            agency_name="Prefeitura Demo",
            report_id=uuid4(),
            protocol="RPT-2026-ABC123",
            category="risco_urbano",
            subcategory=None,
            urgency=None,
            description=None,
            latitude=-23.55,
            longitude=-46.63,
            deadline=None,
            photo_url=None,
        )

        with self.assertRaises(MailDeliveryError):
            SmtpAgencyMailer(settings).send_assignment(assignment)

        smtp_factory.assert_not_called()


class CitizenNotificationTests(unittest.TestCase):
    def test_status_push_contains_only_the_minimum_payload(self) -> None:
        repository = Mock()
        repository.get_status_event.return_value = "em_andamento"
        repository.list_notification_tokens.return_value = ["device-token"]
        sender = Mock()
        report_id = uuid4()
        service = CitizenNotificationService(repository, sender)

        service.notify_status(report_id, 42)

        sender.send.assert_called_once()
        token, message = sender.send.call_args.args
        self.assertEqual(token, "device-token")
        self.assertEqual(
            message,
            PushMessage(
                title="Atendimento em andamento",
                body="O órgão responsável iniciou o atendimento do seu reporte.",
                data={
                    "type": "status_changed",
                    "report_id": str(report_id),
                    "status": ReportStatus.IN_PROGRESS.value,
                },
            ),
        )

    def test_push_is_skipped_when_event_or_overdue_state_is_missing(self) -> None:
        repository = Mock()
        repository.get_status_event.return_value = None
        repository.get_overdue_status.return_value = None
        sender = Mock()
        service = CitizenNotificationService(repository, sender)
        report_id = uuid4()

        service.notify_status(report_id, 42)
        service.notify_overdue(report_id)

        sender.send.assert_not_called()

    def test_push_is_skipped_when_no_device_is_registered(self) -> None:
        repository = Mock()
        repository.get_status_event.return_value = "resolvido"
        repository.list_notification_tokens.return_value = []
        sender = Mock()
        service = CitizenNotificationService(repository, sender)

        service.notify_status(uuid4(), 42)

        sender.send.assert_not_called()
