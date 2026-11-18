"""Orquestra notificações de encaminhamento para o órgão responsável."""

from uuid import UUID

from app.infrastructure.mailer import AgencyMailer, MailDeliveryError
from app.infrastructure.push import PushSender
from app.infrastructure.repositories import ReportRepository
from app.models.notifications import AgencyAssignment, PushMessage
from app.models.reports import ReportStatus
from app.services.photo_service import PhotoService


class AgencyNotificationService:
    def __init__(
        self,
        repository: ReportRepository,
        mailer: AgencyMailer,
        photos: PhotoService,
    ) -> None:
        self._repository = repository
        self._mailer = mailer
        self._photos = photos

    def notify_agency(self, report_id: UUID) -> None:
        detail = self._repository.get_detail(report_id)
        recipient = self._repository.get_agency_email(report_id)
        if not detail.agency_id or not detail.agency_name or not recipient:
            raise MailDeliveryError(
                "O reporte não tem um destino de notificação válido."
            )

        classification = detail.classification
        category = detail.summary.category
        assignment = AgencyAssignment(
            email=recipient,
            agency_name=detail.agency_name,
            report_id=report_id,
            protocol=detail.summary.protocol,
            category=category.value if category is not None else None,
            subcategory=(
                classification.subcategory if classification is not None else None
            ),
            urgency=(
                classification.urgency if classification is not None else None
            ),
            description=detail.description,
            latitude=detail.summary.latitude,
            longitude=detail.summary.longitude,
            deadline=detail.deadline,
            photo_url=(
                self._photos.read_url(report_id) if detail.has_photo else None
            ),
        )
        self._mailer.send_assignment(assignment)


class CitizenNotificationService:
    _STATUS_COPY = {
        ReportStatus.FORWARDED: (
            "Reporte encaminhado",
            "Seu reporte foi encaminhado ao órgão responsável.",
        ),
        ReportStatus.IN_PROGRESS: (
            "Atendimento em andamento",
            "O órgão responsável iniciou o atendimento do seu reporte.",
        ),
        ReportStatus.RESOLVED: (
            "Reporte resolvido",
            "O órgão responsável atualizou seu reporte como resolvido.",
        ),
    }

    def __init__(
        self,
        repository: ReportRepository,
        sender: PushSender,
    ) -> None:
        self._repository = repository
        self._sender = sender

    def register_device(
        self,
        user_id: int,
        push_token: str,
        platform: str,
    ) -> None:
        self._repository.register_notification_device(
            user_id,
            push_token,
            platform,
        )

    def remove_device(self, user_id: int, push_token: str) -> None:
        self._repository.remove_notification_device(user_id, push_token)

    def notify_status(self, report_id: UUID, event_id: int) -> None:
        status_value = self._repository.get_status_event(report_id, event_id)
        if status_value is None:
            return
        status = ReportStatus(status_value)
        copy = self._STATUS_COPY.get(status)
        if copy is None:
            return
        self._send_to_report_devices(
            report_id,
            PushMessage(
                title=copy[0],
                body=copy[1],
                data={
                    "type": "status_changed",
                    "report_id": str(report_id),
                    "status": status.value,
                },
            ),
        )

    def notify_overdue(self, report_id: UUID) -> None:
        status = self._repository.get_overdue_status(report_id)
        if status is None:
            return
        self._send_to_report_devices(
            report_id,
            PushMessage(
                title="Reporte atrasado",
                body="O prazo de referência do seu reporte foi ultrapassado.",
                data={
                    "type": "report_overdue",
                    "report_id": str(report_id),
                    "status": status.value,
                },
            ),
        )

    def _send_to_report_devices(
        self,
        report_id: UUID,
        message: PushMessage,
    ) -> None:
        for token in self._repository.list_notification_tokens(report_id):
            self._sender.send(token, message)
