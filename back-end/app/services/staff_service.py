"""Casos de uso dos servidores municipais (painel web)."""

from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from app.infrastructure.repositories import (
    AuthRepository,
    InvalidAgencyAction,
    ReportNotFound,
    ReportRepository,
    StaffNotAuthorized,
    StaffTransitionNotAllowed,
)
from app.models.reports import ReportCategory, ReportDetail, ReportStatus
from app.models.staff import (
    STAFF_ROLES,
    StaffContext,
    StaffReportItem,
    StaffSummary,
)
from app.services.routing_service import RoutingService

STATUS_EVENTS = {"em_andamento", "resolvido"}


class StaffService:
    def __init__(
        self,
        auth_repository: AuthRepository,
        report_repository: ReportRepository,
        routing_service: RoutingService | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._auth = auth_repository
        self._reports = report_repository
        self._routing = routing_service or RoutingService()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def resolve(self, user_id: int) -> StaffContext:
        """Resolve papel e órgão no banco; o token só identifica o usuário."""
        user = self._auth.get_user(user_id)
        if user.role not in STAFF_ROLES:
            raise StaffNotAuthorized
        agency_id = None
        if user.role == "agency":
            agency_id = self._auth.get_staff_agency(user_id)
            if agency_id is None:
                raise StaffNotAuthorized
        return StaffContext(
            user_id=user.id,
            email=user.email,
            role=user.role,
            agency_id=agency_id,
        )

    def agencies(self, context: StaffContext) -> list[tuple[str, str]]:
        agencies = self._routing.list_agencies()
        if context.agency_id is None:
            return agencies
        return [item for item in agencies if item[0] == context.agency_id]

    def agency_name(self, agency_id: str | None) -> str | None:
        if agency_id is None:
            return None
        return dict(self._routing.list_agencies()).get(agency_id)

    def list_reports(
        self,
        context: StaffContext,
        status: ReportStatus | None,
        category: ReportCategory | None,
        overdue: bool,
        query: str | None,
        limit: int,
        cursor: UUID | None,
    ) -> list[StaffReportItem]:
        return self._reports.list_staff_reports(
            context.agency_id,
            status,
            category,
            overdue,
            query,
            limit,
            cursor,
        )

    def summary(self, context: StaffContext) -> StaffSummary:
        return self._reports.staff_summary(context.agency_id)

    def get_detail(self, context: StaffContext, report_id: UUID) -> ReportDetail:
        detail = self._reports.get_detail(report_id)
        # Fora do escopo é indistinguível de inexistente (não vaza existência).
        if context.agency_id is not None and detail.agency_id != context.agency_id:
            raise ReportNotFound
        return detail

    def update_status(
        self,
        context: StaffContext,
        report_id: UUID,
        action: str,
        deadline: datetime | None,
        justification: str | None,
    ) -> tuple[ReportDetail, int | None]:
        """Aplica a transição do órgão; devolve o detalhe e o evento a notificar."""
        if context.role != "agency":
            raise StaffNotAuthorized
        current = self.get_detail(context, report_id).summary.status

        if action == "in_progress":
            if current != ReportStatus.FORWARDED:
                raise StaffTransitionNotAllowed
            if deadline is not None and (
                deadline.utcoffset() is None or deadline <= self._clock()
            ):
                raise InvalidAgencyAction
        elif action == "resolved":
            if current != ReportStatus.IN_PROGRESS:
                raise StaffTransitionNotAllowed
        elif action == "contest":
            if current not in {ReportStatus.FORWARDED, ReportStatus.IN_PROGRESS}:
                raise StaffTransitionNotAllowed
        else:
            raise InvalidAgencyAction

        detail = self._reports.update_agency_status(
            report_id,
            action,
            deadline,
            justification,
            actor=f"agency:{context.agency_id}",
            actor_user_id=context.user_id,
        )
        event_id = None
        if action != "contest":
            event_id = next(
                (
                    event.id
                    for event in reversed(detail.timeline)
                    if event.type in STATUS_EVENTS
                ),
                None,
            )
        return detail, event_id


def provision_dev_staff(
    repository: object,
    spec: str,
    known_agencies: set[str],
) -> None:
    """Cria contas de servidor de desenvolvimento a partir de 'email:papel[:órgão]'."""
    for entry in filter(None, (part.strip() for part in spec.split(","))):
        email, _, rest = entry.partition(":")
        role, _, agency_id = rest.partition(":")
        if not email or role not in STAFF_ROLES:
            raise RuntimeError(f"DEV_STAFF_ACCOUNTS inválido: {entry!r}")
        if role == "agency" and agency_id not in known_agencies:
            raise RuntimeError(
                f"DEV_STAFF_ACCOUNTS: órgão desconhecido para {email!r}."
            )
        repository.provision_staff(email, role, agency_id or None)
