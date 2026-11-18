"""Contratos das integrações de persistência e arquivos usados pelo MVP."""

import hmac
import json
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from app.core.geo import GeoBox
from app.infrastructure.database import OracleDatabase
from app.infrastructure.geohash import encode_geohash
from app.models.auth import AuthUser
from app.models.classification import (
    ClassificationInput,
    ClassificationResult,
    RouteDecision,
)
from app.models.reports import (
    ClientTimestampOutOfRange,
    ReportCategory,
    NewReport,
    PersistedReport,
    ReportDetail,
    ReportComment,
    ReportStatus,
    ReportSummary,
    ReportTimelineEvent,
    TriageState,
    UploadInstruction,
)

PROTOCOL_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


class ReportIdConflict(Exception):
    """O UUID do cliente já pertence a outro usuário."""


class PhotoStorageUnavailable(Exception):
    """O armazenamento de fotos ainda não foi configurado."""


class ConsentRequired(Exception):
    """Consentimento e confirmação de idade obrigatórios para criar conta."""


class GoogleAccountConflict(Exception):
    """O e-mail ou identificador Google já está vinculado a outra conta."""


class AccountNotFound(Exception):
    """Conta de usuário inexistente."""


class ReportNotFound(Exception):
    """O reporte solicitado não existe."""


class ReportOwnerCannotConfirm(Exception):
    """O autor não pode confirmar o próprio reporte."""


class AlreadyConfirmed(Exception):
    """O usuário já confirmou este grupo de reportes."""


class InvalidReportCursor(Exception):
    """Cursor inexistente ou que não pertence aos reportes do usuário."""


class ReportNotOwner(Exception):
    """O cidadão não é o solicitante associado ao reporte."""


class ReportPhotoNotEnabled(Exception):
    """O reporte não foi criado com uma foto."""


class ReportPhotoConflict(Exception):
    """O reporte já possui outra foto finalizada."""


class TriageConflict(Exception):
    """O reporte não está disponível para triagem."""


class ReopenNotAllowed(Exception):
    """O reporte não pode ser reaberto neste momento."""


class NudgeNotAllowed(Exception):
    """A cobrança não é permitida para este reporte."""


class ReportAlreadyFlagged(Exception):
    """O reporte já foi sinalizado por esta conta."""


class InvalidAgencyAction(Exception):
    """A ação administrativa não é válida para o estado atual."""


class ReportRepository(Protocol):
    def reopen_report(
        self,
        report_id: UUID,
        user_id: int,
        reason: str | None,
    ) -> ReportDetail: ...

    def flag_report(
        self,
        report_id: UUID,
        user_id: int,
        reason: str,
        note: str | None,
    ) -> None: ...

    def nudge_report(self, report_id: UUID, user_id: int) -> None: ...

    def update_agency_status(
        self,
        report_id: UUID,
        action: str,
        deadline: datetime | None,
        justification: str | None,
    ) -> ReportDetail: ...

    def list_moderation(self, limit: int) -> list[ReportSummary]: ...

    def list_in_area(self, box: GeoBox, max_items: int) -> list[ReportSummary]:
        """Reportes públicos (fora de moderação) no retângulo, mais recentes primeiro."""
        ...

    def export_user_data(self, user_id: int) -> dict[str, object]: ...

    def delete_user_data(self, user_id: int) -> None: ...

    def get_public_metrics(
        self,
        from_date: datetime | None,
        to_date: datetime | None,
        category: str | None,
        agency_id: str | None,
    ) -> dict[str, object]: ...

    def create(self, report: NewReport) -> PersistedReport:
        """Cria ou devolve o reporte existente para o mesmo UUID."""

    def get_detail(self, report_id: UUID) -> ReportDetail: ...

    def classification_input(self, report_id: UUID) -> ClassificationInput: ...

    def mark_for_moderation(self, report_id: UUID) -> None: ...

    def assert_photo_owner(
        self,
        report_id: UUID,
        user_id: int,
        expected_sha256: str,
    ) -> None: ...

    def set_photo_key(self, report_id: UUID, photo_key: str) -> None: ...

    def get_photo_key(self, report_id: UUID) -> str | None: ...

    def get_agency_email(self, report_id: UUID) -> str | None: ...

    def register_notification_device(
        self,
        user_id: int,
        push_token: str,
        platform: str,
    ) -> None: ...

    def remove_notification_device(self, user_id: int, push_token: str) -> None: ...

    def list_notification_tokens(self, report_id: UUID) -> list[str]: ...

    def get_status_event(self, report_id: UUID, event_id: int) -> str | None: ...

    def get_overdue_status(self, report_id: UUID) -> ReportStatus | None: ...

    def list_user_reports(
        self,
        user_id: int,
        limit: int,
        cursor: UUID | None,
        status: ReportStatus | None,
    ) -> list[ReportSummary]: ...

    def create_comment(
        self,
        report_id: UUID,
        user_id: int,
        content: str,
    ) -> ReportComment: ...

    def list_comments(self, report_id: UUID, limit: int) -> list[ReportComment]: ...

    def confirm(self, report_id: UUID, user_id: int) -> int: ...

    def record_classification(
        self,
        report_id: UUID,
        classification: ClassificationResult,
    ) -> None: ...

    def apply_triage(
        self,
        report_id: UUID,
        user_id: int,
        action: str,
        classification: ClassificationResult,
        route: RouteDecision | None,
        deadline: datetime | None,
    ) -> None: ...


class ObjectStorage(Protocol):
    def create_upload_instruction(
        self,
        report_id: UUID,
        *,
        max_bytes: int,
        expires_in: timedelta,
    ) -> UploadInstruction:
        """Gera uma instrução temporária e assinada de upload."""


class AuthRepository(Protocol):
    def get_user(self, user_id: int) -> AuthUser: ...

    def update_email(self, user_id: int, email: str) -> AuthUser: ...

    def delete_account(self, user_id: int) -> None: ...

    def request_otp(
        self,
        email: str,
        code_hash: str,
        *,
        expires_at: datetime,
        consent_version: str | None,
        accepted_age: bool | None,
    ) -> None: ...

    def verify_otp(
        self,
        email: str,
        code_hash: str,
        *,
        refresh_token_hash: str,
        refresh_expires_at: datetime,
    ) -> AuthUser | None: ...

    def rotate_refresh_token(
        self,
        old_token_hash: str,
        new_token_hash: str,
        *,
        expires_at: datetime,
    ) -> AuthUser | None: ...

    def login_google(
        self,
        google_sub: str,
        email: str,
        *,
        consent_version: str | None,
        accepted_age: bool | None,
        refresh_token_hash: str,
        refresh_expires_at: datetime,
    ) -> AuthUser: ...


@dataclass
class _OtpChallenge:
    code_hash: str
    expires_at: datetime
    consent_version: str | None
    attempts: int = 0
    consumed: bool = False


@dataclass
class _RefreshToken:
    user_id: int
    expires_at: datetime
    revoked: bool = False


class InMemoryAuthRepository:
    """Autenticação volátil disponível somente para desenvolvimento."""

    def __init__(self) -> None:
        self._users_by_email: dict[str, AuthUser] = {}
        self._users_by_id: dict[int, AuthUser] = {}
        self._users_by_google_sub: dict[str, AuthUser] = {}
        self._google_sub_by_user: dict[int, str] = {}
        self._challenges: dict[str, _OtpChallenge] = {}
        self._refresh_tokens: dict[str, _RefreshToken] = {}
        self._next_user_id = 1
        self._lock = threading.Lock()

    def get_user(self, user_id: int) -> AuthUser:
        with self._lock:
            user = self._users_by_id.get(user_id)
            if user is None:
                raise AccountNotFound
            return user

    def update_email(self, user_id: int, email: str) -> AuthUser:
        with self._lock:
            current = self._users_by_id.get(user_id)
            if current is None:
                raise AccountNotFound
            normalized_email = email.strip().lower()
            existing = self._users_by_email.get(normalized_email)
            if existing is not None and existing.id != user_id:
                raise GoogleAccountConflict

            if current.email:
                self._users_by_email.pop(current.email, None)
            updated = AuthUser(
                id=current.id,
                email=normalized_email,
                role=current.role,
                consent_version=current.consent_version,
                created_at=current.created_at,
            )
            self._users_by_id[user_id] = updated
            self._users_by_email[normalized_email] = updated
            return updated

    def delete_account(self, user_id: int) -> None:
        with self._lock:
            user = self._users_by_id.pop(user_id, None)
            if user is None:
                raise AccountNotFound
            if user.email:
                self._users_by_email.pop(user.email, None)
            google_sub = self._google_sub_by_user.pop(user_id, None)
            if google_sub is not None:
                self._users_by_google_sub.pop(google_sub, None)
            for token_hash, refresh in list(self._refresh_tokens.items()):
                if refresh.user_id == user_id:
                    self._refresh_tokens.pop(token_hash, None)

    def request_otp(
        self,
        email: str,
        code_hash: str,
        *,
        expires_at: datetime,
        consent_version: str | None,
        accepted_age: bool | None,
    ) -> None:
        with self._lock:
            if email not in self._users_by_email and (
                not consent_version or accepted_age is not True
            ):
                raise ConsentRequired
            self._challenges[email] = _OtpChallenge(
                code_hash=code_hash,
                expires_at=expires_at,
                consent_version=consent_version,
            )

    def verify_otp(
        self,
        email: str,
        code_hash: str,
        *,
        refresh_token_hash: str,
        refresh_expires_at: datetime,
    ) -> AuthUser | None:
        with self._lock:
            challenge = self._challenges.get(email)
            now = datetime.now(timezone.utc)
            if (
                challenge is None
                or challenge.consumed
                or challenge.expires_at <= now
                or challenge.attempts >= 5
            ):
                return None

            challenge.attempts += 1
            if not hmac.compare_digest(challenge.code_hash, code_hash):
                return None

            user = self._users_by_email.get(email)
            if user is None:
                user = AuthUser(
                    id=self._next_user_id,
                    email=email,
                    role="citizen",
                    consent_version=challenge.consent_version,
                    created_at=now,
                )
                self._next_user_id += 1
                self._users_by_email[email] = user
                self._users_by_id[user.id] = user

            challenge.consumed = True
            self._refresh_tokens[refresh_token_hash] = _RefreshToken(
                user_id=user.id,
                expires_at=refresh_expires_at,
            )
            return user

    def login_google(
        self,
        google_sub: str,
        email: str,
        *,
        consent_version: str | None,
        accepted_age: bool | None,
        refresh_token_hash: str,
        refresh_expires_at: datetime,
    ) -> AuthUser:
        with self._lock:
            now = datetime.now(timezone.utc)
            google_user = self._users_by_google_sub.get(google_sub)
            email_user = self._users_by_email.get(email)

            if google_user is not None:
                if email_user is not None and email_user.id != google_user.id:
                    raise GoogleAccountConflict
                user = google_user
            elif email_user is not None:
                existing_sub = self._google_sub_by_user.get(email_user.id)
                if existing_sub is not None and existing_sub != google_sub:
                    raise GoogleAccountConflict
                self._users_by_google_sub[google_sub] = email_user
                self._google_sub_by_user[email_user.id] = google_sub
                user = email_user
            else:
                if not consent_version or accepted_age is not True:
                    raise ConsentRequired
                user = AuthUser(
                    id=self._next_user_id,
                    email=email,
                    role="citizen",
                    consent_version=consent_version,
                    created_at=now,
                )
                self._next_user_id += 1
                self._users_by_email[email] = user
                self._users_by_id[user.id] = user
                self._users_by_google_sub[google_sub] = user
                self._google_sub_by_user[user.id] = google_sub

            self._refresh_tokens[refresh_token_hash] = _RefreshToken(
                user_id=user.id,
                expires_at=refresh_expires_at,
            )
            return user

    def rotate_refresh_token(
        self,
        old_token_hash: str,
        new_token_hash: str,
        *,
        expires_at: datetime,
    ) -> AuthUser | None:
        with self._lock:
            current = self._refresh_tokens.get(old_token_hash)
            now = datetime.now(timezone.utc)
            if (
                current is None
                or current.revoked
                or current.expires_at <= now
            ):
                return None

            user = self._users_by_id.get(current.user_id)
            if user is None:
                return None

            current.revoked = True
            self._refresh_tokens[new_token_hash] = _RefreshToken(
                user_id=user.id,
                expires_at=expires_at,
            )
            return user


class InMemoryReportRepository:
    """Repositório temporário de desenvolvimento; os dados não sobrevivem ao processo."""

    def __init__(self) -> None:
        self._reports: dict[UUID, tuple[int, PersistedReport]] = {}
        self._report_inputs: dict[UUID, NewReport] = {}
        self._timeline: dict[UUID, list[ReportTimelineEvent]] = {}
        self._protocols: set[str] = set()
        self._comments: dict[UUID, list[ReportComment]] = {}
        self._confirmations: dict[UUID, set[int]] = {}
        self._classifications: dict[UUID, ClassificationResult] = {}
        self._routes: dict[UUID, RouteDecision] = {}
        self._deadlines: dict[UUID, datetime] = {}
        self._photo_keys: dict[UUID, str] = {}
        self._notification_devices: dict[str, tuple[int, str]] = {}
        self._nudges: dict[UUID, list[int]] = {}
        self._flags: dict[UUID, set[int]] = {}
        self._next_comment_id = 1
        self._next_event_id = 1
        self._lock = threading.Lock()

    def create(self, report: NewReport) -> PersistedReport:
        with self._lock:
            existing = self._reports.get(report.id)
            if existing is not None:
                owner_id, persisted = existing
                if owner_id != report.requester_user_id:
                    raise ReportIdConflict
                return PersistedReport(
                    id=persisted.id,
                    protocol=persisted.protocol,
                    received_at=persisted.received_at,
                    was_created=False,
                    status=persisted.status,
                    triage_state=persisted.triage_state,
                )

            protocol = self._new_protocol()
            persisted = PersistedReport(
                id=report.id,
                protocol=protocol,
                received_at=datetime.now(timezone.utc),
                was_created=True,
            )
            self._reports[report.id] = (report.requester_user_id, persisted)
            self._report_inputs[report.id] = report
            self._timeline[report.id] = [
                ReportTimelineEvent(
                    id=self._next_event_id,
                    type="recebido",
                    actor="system",
                    justification=None,
                    created_at=persisted.received_at,
                )
            ]
            self._next_event_id += 1
            self._comments[report.id] = []
            self._confirmations[report.id] = set()
            self._nudges[report.id] = []
            self._flags[report.id] = set()
            return persisted

    def get_detail(self, report_id: UUID) -> ReportDetail:
        with self._lock:
            stored = self._reports.get(report_id)
            report_input = self._report_inputs.get(report_id)
            if stored is None or report_input is None:
                raise ReportNotFound

            _, persisted = stored
            summary = self._summary_for(
                report_input,
                persisted,
                len(self._confirmations[report_id]),
            )
            return ReportDetail(
                summary=summary,
                description=report_input.description,
                anonymous=report_input.anonymous,
                has_photo=report_input.has_photo,
                triage_state=persisted.triage_state,
                classification=self._classifications.get(report_id),
                agency_id=(
                    self._routes[report_id].agency_id
                    if report_id in self._routes
                    else None
                ),
                agency_name=(
                    self._routes[report_id].agency_name
                    if report_id in self._routes
                    else None
                ),
                deadline=self._deadlines.get(report_id),
                timeline=list(self._timeline[report_id]),
            )

    def classification_input(self, report_id: UUID) -> ClassificationInput:
        with self._lock:
            report = self._report_inputs.get(report_id)
            if report is None:
                raise ReportNotFound
            return ClassificationInput(
                text=report.description,
                user_category=report.category,
            )

    def assert_photo_owner(
        self,
        report_id: UUID,
        user_id: int,
        expected_sha256: str,
    ) -> None:
        with self._lock:
            stored = self._reports.get(report_id)
            report_input = self._report_inputs.get(report_id)
            if stored is None or report_input is None:
                raise ReportNotFound
            owner_id, _ = stored
            if not report_input.has_photo:
                raise ReportPhotoNotEnabled
            if owner_id != user_id:
                raise ReportNotOwner
            existing_key = self._photo_keys.get(report_id)
            expected_key = f"objects/{expected_sha256.lower()}.jpg"
            if existing_key is not None and existing_key != expected_key:
                raise ReportPhotoConflict

    def set_photo_key(self, report_id: UUID, photo_key: str) -> None:
        with self._lock:
            report_input = self._report_inputs.get(report_id)
            if report_input is None:
                raise ReportNotFound
            existing_key = self._photo_keys.get(report_id)
            if existing_key is not None and existing_key != photo_key:
                raise ReportPhotoConflict
            self._photo_keys[report_id] = photo_key

    def get_photo_key(self, report_id: UUID) -> str | None:
        with self._lock:
            if report_id not in self._report_inputs:
                raise ReportNotFound
            return self._photo_keys.get(report_id)

    def get_agency_email(self, report_id: UUID) -> str | None:
        with self._lock:
            if report_id not in self._report_inputs:
                raise ReportNotFound
            route = self._routes.get(report_id)
            return route.agency_email if route is not None else None

    def register_notification_device(
        self,
        user_id: int,
        push_token: str,
        platform: str,
    ) -> None:
        with self._lock:
            self._notification_devices[push_token] = (user_id, platform)

    def remove_notification_device(self, user_id: int, push_token: str) -> None:
        with self._lock:
            registered_device = self._notification_devices.get(push_token)
            if registered_device is not None and registered_device[0] == user_id:
                self._notification_devices.pop(push_token)

    def list_notification_tokens(self, report_id: UUID) -> list[str]:
        with self._lock:
            stored = self._reports.get(report_id)
            if stored is None:
                raise ReportNotFound
            owner_id, _ = stored
            return sorted(
                token
                for token, (registered_user_id, _) in self._notification_devices.items()
                if registered_user_id == owner_id
            )

    def get_status_event(self, report_id: UUID, event_id: int) -> str | None:
        status_by_event = {
            "encaminhado": ReportStatus.FORWARDED.value,
            "em_andamento": ReportStatus.IN_PROGRESS.value,
            "resolvido": ReportStatus.RESOLVED.value,
        }
        with self._lock:
            events = self._timeline.get(report_id)
            if events is None:
                raise ReportNotFound
            event = next((item for item in events if item.id == event_id), None)
            return status_by_event.get(event.type) if event is not None else None

    def get_overdue_status(self, report_id: UUID) -> ReportStatus | None:
        with self._lock:
            stored = self._reports.get(report_id)
            if stored is None:
                raise ReportNotFound
            _, persisted = stored
            deadline = self._deadlines.get(report_id)
            if (
                persisted.status not in {
                    ReportStatus.FORWARDED,
                    ReportStatus.IN_PROGRESS,
                }
                or deadline is None
                or deadline >= datetime.now(timezone.utc)
            ):
                return None
            return persisted.status

    def reopen_report(
        self,
        report_id: UUID,
        user_id: int,
        reason: str | None,
    ) -> ReportDetail:
        with self._lock:
            stored = self._reports.get(report_id)
            report_input = self._report_inputs.get(report_id)
            if stored is None or report_input is None:
                raise ReportNotFound
            owner_id, persisted = stored
            if owner_id != user_id:
                raise ReportNotOwner
            if persisted.status != ReportStatus.RESOLVED:
                raise ReopenNotAllowed
            if datetime.now(timezone.utc) - persisted.received_at > timedelta(days=30):
                raise ReopenNotAllowed

            reopened = PersistedReport(
                id=persisted.id,
                protocol=persisted.protocol,
                received_at=persisted.received_at,
                was_created=persisted.was_created,
                status=ReportStatus.IN_PROGRESS,
                triage_state=TriageState.CONFIRMED,
            )
            self._reports[report_id] = (owner_id, reopened)
            self._append_event(
                report_id,
                "reaberto",
                f"citizen:{user_id}",
                reason,
            )
            return self.get_detail(report_id)

    def flag_report(
        self,
        report_id: UUID,
        user_id: int,
        reason: str,
        note: str | None,
    ) -> None:
        with self._lock:
            if report_id not in self._reports:
                raise ReportNotFound
            flagged = self._flags.setdefault(report_id, set())
            if user_id in flagged:
                raise ReportAlreadyFlagged
            flagged.add(user_id)
            _, persisted = self._reports[report_id]
            owner_id = self._reports[report_id][0]
            self._reports[report_id] = (
                owner_id,
                PersistedReport(
                    id=persisted.id,
                    protocol=persisted.protocol,
                    received_at=persisted.received_at,
                    was_created=persisted.was_created,
                    status=persisted.status,
                    triage_state=TriageState.IN_MODERATION,
                ),
            )
            justification = f"{reason}: {note}" if note else reason
            self._append_event(
                report_id,
                "sinalizado",
                f"citizen:{user_id}",
                justification,
            )

    def nudge_report(self, report_id: UUID, user_id: int) -> None:
        with self._lock:
            stored = self._reports.get(report_id)
            if stored is None:
                raise ReportNotFound
            owner_id, persisted = stored
            if owner_id != user_id:
                raise ReportNotOwner
            deadline = self._deadlines.get(report_id)
            nudges = self._nudges.setdefault(report_id, [])
            if (
                persisted.status not in {ReportStatus.FORWARDED, ReportStatus.IN_PROGRESS}
                or deadline is None
                or deadline >= datetime.now(timezone.utc)
                or len(nudges) >= 3
                or user_id in nudges
            ):
                raise NudgeNotAllowed
            nudges.append(user_id)
            self._append_event(
                report_id,
                "cobrado",
                f"citizen:{user_id}",
            )

    def update_agency_status(
        self,
        report_id: UUID,
        action: str,
        deadline: datetime | None,
        justification: str | None,
    ) -> ReportDetail:
        with self._lock:
            stored = self._reports.get(report_id)
            if stored is None:
                raise ReportNotFound
            owner_id, persisted = stored
            if action == "in_progress":
                if deadline is None:
                    raise InvalidAgencyAction
                status = ReportStatus.IN_PROGRESS
                event_type = "em_andamento"
                self._deadlines[report_id] = deadline
            elif action == "resolved":
                if not justification:
                    raise InvalidAgencyAction
                status = ReportStatus.RESOLVED
                event_type = "resolvido"
            elif action == "contest":
                if not justification:
                    raise InvalidAgencyAction
                status = persisted.status
                event_type = "contestado"
            else:
                raise InvalidAgencyAction

            updated = PersistedReport(
                id=persisted.id,
                protocol=persisted.protocol,
                received_at=persisted.received_at,
                was_created=persisted.was_created,
                status=status,
                triage_state=persisted.triage_state,
            )
            self._reports[report_id] = (owner_id, updated)
            self._append_event(
                report_id,
                event_type,
                "agency",
                justification,
            )
            return self.get_detail(report_id)

    def list_moderation(self, limit: int) -> list[ReportSummary]:
        with self._lock:
            items = [
                (report_id, persisted)
                for report_id, (_, persisted) in self._reports.items()
                if persisted.triage_state == TriageState.IN_MODERATION
            ]
            items.sort(
                key=lambda item: self._report_inputs[item[0]].client_created_at,
                reverse=True,
            )
            return [
                self._summary_for(
                    self._report_inputs[report_id],
                    persisted,
                    len(self._confirmations.get(report_id, set())),
                )
                for report_id, persisted in items[:limit]
            ]

    def list_in_area(self, box: GeoBox, max_items: int) -> list[ReportSummary]:
        with self._lock:
            items = [
                (report_id, persisted)
                for report_id, (_, persisted) in self._reports.items()
                if persisted.triage_state != TriageState.IN_MODERATION
                and box.contains(
                    self._report_inputs[report_id].latitude,
                    self._report_inputs[report_id].longitude,
                )
            ]
            items.sort(key=lambda item: item[1].received_at, reverse=True)
            return [
                self._summary_for(
                    self._report_inputs[report_id],
                    persisted,
                    len(self._confirmations.get(report_id, set())),
                )
                for report_id, persisted in items[:max_items]
            ]

    def mark_for_moderation(self, report_id: UUID) -> None:
        with self._lock:
            stored = self._reports.get(report_id)
            if stored is None:
                raise ReportNotFound
            owner_id, persisted = stored
            if persisted.triage_state == TriageState.IN_MODERATION:
                return
            self._reports[report_id] = (
                owner_id,
                PersistedReport(
                    id=persisted.id,
                    protocol=persisted.protocol,
                    received_at=persisted.received_at,
                    was_created=persisted.was_created,
                    status=persisted.status,
                    triage_state=TriageState.IN_MODERATION,
                ),
            )
            self._append_event(report_id, "enviado_moderacao", "system")

    def list_user_reports(
        self,
        user_id: int,
        limit: int,
        cursor: UUID | None,
        status: ReportStatus | None,
    ) -> list[ReportSummary]:
        with self._lock:
            reports = [
                (report_id, owner_id, persisted)
                for report_id, (owner_id, persisted) in self._reports.items()
                if owner_id == user_id
            ]
            reports.sort(
                key=lambda item: (item[2].received_at, str(item[0])),
                reverse=True,
            )

            start_index = 0
            if cursor is not None:
                cursor_index = next(
                    (
                        index
                        for index, (report_id, _, _) in enumerate(reports)
                        if report_id == cursor
                    ),
                    None,
                )
                if cursor_index is None:
                    raise InvalidReportCursor
                start_index = cursor_index + 1

            remaining = reports[start_index:]
            if status is not None:
                remaining = [
                    item for item in remaining if item[2].status == status
                ]
            page = remaining[:limit]
            return [
                self._summary_for(
                    self._report_inputs[report_id],
                    persisted,
                    len(self._confirmations[report_id]),
                )
                for report_id, _, persisted in page
            ]

    def export_user_data(self, user_id: int) -> dict[str, object]:
        with self._lock:
            report_ids = [
                report_id
                for report_id, (owner_id, _) in self._reports.items()
                if owner_id == user_id
            ]
            reports: list[dict[str, object]] = []
            for report_id in report_ids:
                detail = self.get_detail(report_id)
                comments = [
                    {
                        "id": comment.id,
                        "content": comment.content,
                        "created_at": comment.created_at.isoformat(),
                    }
                    for comment in self._comments.get(report_id, [])
                    if comment.user_id == user_id
                ]
                reports.append(
                    {
                        "id": str(detail.summary.id),
                        "protocol": detail.summary.protocol,
                        "description": detail.description,
                        "category": (
                            detail.summary.category.value
                            if detail.summary.category is not None
                            else None
                        ),
                        "received_at": detail.summary.received_at.isoformat(),
                        "status": detail.summary.status.value,
                        "anonymous": detail.anonymous,
                        "comments": comments,
                    }
                )
            devices = [
                {"push_token": token, "platform": platform}
                for token, (owner_id, platform)
                in self._notification_devices.items()
                if owner_id == user_id
            ]
            return {
                "user_id": user_id,
                "reports": reports,
                "notification_devices": devices,
            }

    def delete_user_data(self, user_id: int) -> None:
        with self._lock:
            for report_id, (owner_id, persisted) in list(self._reports.items()):
                if owner_id == user_id:
                    self._reports[report_id] = (0, persisted)
                    self._comments[report_id] = [
                        comment
                        for comment in self._comments.get(report_id, [])
                        if comment.user_id != user_id
                    ]
                    self._confirmations[report_id].discard(user_id)
                    report_input = self._report_inputs[report_id]
                    if report_input.anonymous:
                        self._report_inputs[report_id] = NewReport(
                            id=report_input.id,
                            description=report_input.description,
                            has_photo=report_input.has_photo,
                            category=report_input.category,
                            latitude=report_input.latitude,
                            longitude=report_input.longitude,
                            location_accuracy_m=report_input.location_accuracy_m,
                            anonymous=True,
                            client_created_at=report_input.client_created_at,
                            correlation_id=report_input.correlation_id,
                            user_id=None,
                            requester_user_id=0,
                        )
            for push_token, (owner_id, _) in list(
                self._notification_devices.items()
            ):
                if owner_id == user_id:
                    self._notification_devices.pop(push_token, None)

    def get_public_metrics(
        self,
        from_date: datetime | None,
        to_date: datetime | None,
        category: str | None,
        agency_id: str | None,
    ) -> dict[str, object]:
        with self._lock:
            selected: list[tuple[UUID, PersistedReport, NewReport]] = []
            for report_id, (_, persisted) in self._reports.items():
                report = self._report_inputs[report_id]
                effective_category = (
                    self._classifications[report_id].category
                    if report_id in self._classifications
                    else report.category
                )
                route = self._routes.get(report_id)
                if from_date is not None and persisted.received_at < from_date:
                    continue
                if to_date is not None and persisted.received_at > to_date:
                    continue
                if category is not None:
                    if effective_category is None:
                        continue
                    if effective_category.value != category:
                        continue
                if agency_id is not None:
                    if route is None or route.agency_id != agency_id:
                        continue
                selected.append((report_id, persisted, report))

            response_durations: list[float] = []
            resolved_count = 0
            by_agency: dict[str, list[tuple[UUID, PersistedReport]]] = {}
            recurrence = sum(
                1
                for report_id, _, _ in selected
                if len(self._confirmations.get(report_id, set())) > 0
            )

            for report_id, persisted, _ in selected:
                if persisted.status == ReportStatus.RESOLVED:
                    resolved_count += 1
                    received = persisted.received_at
                    resolved_at = next(
                        (
                            event.created_at
                            for event in self._timeline.get(report_id, [])
                            if event.type == "resolvido"
                        ),
                        received,
                    )
                    response_durations.append(
                        max(0.0, (resolved_at - received).total_seconds()) / 3600
                    )
                route = self._routes.get(report_id)
                if route is not None:
                    by_agency.setdefault(route.agency_id, []).append(
                        (report_id, persisted)
                    )

            agency_rows: list[dict[str, object]] = []
            for current_agency_id, agency_reports in sorted(by_agency.items()):
                if len(agency_reports) < 5:
                    continue
                route = next(
                    self._routes[report_id]
                    for report_id, _ in agency_reports
                )
                agency_resolved = sum(
                    1
                    for _, persisted in agency_reports
                    if persisted.status == ReportStatus.RESOLVED
                )
                agency_durations = [
                    max(
                        0.0,
                        (
                            next(
                                (
                                    event.created_at
                                    for event in self._timeline.get(report_id, [])
                                    if event.type == "resolvido"
                                ),
                                persisted.received_at,
                            )
                            - persisted.received_at
                        ).total_seconds(),
                    )
                    / 3600
                    for report_id, persisted in agency_reports
                    if persisted.status == ReportStatus.RESOLVED
                ]
                agency_rows.append(
                    {
                        "agency": {
                            "id": route.agency_id,
                            "name": route.agency_name,
                        },
                        "reports": len(agency_reports),
                        "avg_response_hours": (
                            round(sum(agency_durations) / len(agency_durations), 2)
                            if agency_durations
                            else None
                        ),
                        "resolution_rate": round(
                            agency_resolved / len(agency_reports),
                            4,
                        ),
                    }
                )

            total = len(selected)
            return {
                "period": {
                    "from": from_date.date().isoformat() if from_date else None,
                    "to": to_date.date().isoformat() if to_date else None,
                },
                "totals": {
                    "reports": total,
                    "avg_response_hours": (
                        round(sum(response_durations) / len(response_durations), 2)
                        if response_durations
                        else None
                    ),
                    "resolution_rate": (
                        round(resolved_count / total, 4) if total else None
                    ),
                    "recurrence": recurrence,
                },
                "by_agency": agency_rows,
            }

    def _summary_for(
        self,
        report: NewReport,
        persisted: PersistedReport,
        confirmation_count: int,
    ) -> ReportSummary:
        return ReportSummary(
            id=report.id,
            protocol=persisted.protocol,
            status=persisted.status,
            category=(
                self._classifications[report.id].category
                if report.id in self._classifications
                else report.category
            ),
            latitude=report.latitude,
            longitude=report.longitude,
            received_at=persisted.received_at,
            group_id=str(report.id),
            confirmation_count=confirmation_count,
        )

    def record_classification(
        self,
        report_id: UUID,
        classification: ClassificationResult,
    ) -> None:
        with self._lock:
            stored = self._reports.get(report_id)
            if stored is None:
                raise ReportNotFound
            _, persisted = stored
            if report_id in self._classifications:
                return
            if persisted.triage_state != TriageState.PENDING_CLASSIFICATION:
                raise TriageConflict
            self._classifications[report_id] = classification
            self._reports[report_id] = (
                stored[0],
                PersistedReport(
                    id=persisted.id,
                    protocol=persisted.protocol,
                    received_at=persisted.received_at,
                    was_created=persisted.was_created,
                    status=persisted.status,
                    triage_state=TriageState.AWAITING_USER,
                ),
            )
            self._append_event(
                report_id,
                "classificado",
                "system",
            )

    def apply_triage(
        self,
        report_id: UUID,
        user_id: int,
        action: str,
        classification: ClassificationResult,
        route: RouteDecision | None,
        deadline: datetime | None,
    ) -> None:
        with self._lock:
            stored = self._reports.get(report_id)
            if stored is None:
                raise ReportNotFound
            owner_id, persisted = stored
            if owner_id != user_id:
                raise ReportNotOwner
            if persisted.triage_state != TriageState.AWAITING_USER:
                raise TriageConflict

            self._classifications[report_id] = classification
            triage_event = (
                "classificacao_confirmada"
                if action == "confirm"
                else "classificacao_corrigida"
            )
            self._append_event(
                report_id,
                triage_event,
                f"citizen:{user_id}",
            )

            if route is None:
                triage_state = TriageState.IN_MODERATION
                status = persisted.status
                self._append_event(
                    report_id,
                    "enviado_moderacao",
                    "system",
                )
            else:
                triage_state = TriageState.CONFIRMED
                status = ReportStatus.FORWARDED
                self._routes[report_id] = route
                if deadline is not None:
                    self._deadlines[report_id] = deadline
                self._append_event(
                    report_id,
                    "encaminhado",
                    "system",
                )
            self._reports[report_id] = (
                owner_id,
                PersistedReport(
                    id=persisted.id,
                    protocol=persisted.protocol,
                    received_at=persisted.received_at,
                    was_created=persisted.was_created,
                    status=status,
                    triage_state=triage_state,
                ),
            )

    def _append_event(
        self,
        report_id: UUID,
        event_type: str,
        actor: str,
        justification: str | None = None,
    ) -> None:
        self._timeline[report_id].append(
            ReportTimelineEvent(
                id=self._next_event_id,
                type=event_type,
                actor=actor,
                justification=justification,
                created_at=datetime.now(timezone.utc),
            )
        )
        self._next_event_id += 1

    def create_comment(
        self,
        report_id: UUID,
        user_id: int,
        content: str,
    ) -> ReportComment:
        with self._lock:
            if report_id not in self._reports:
                raise ReportNotFound
            comment = ReportComment(
                id=self._next_comment_id,
                report_id=report_id,
                user_id=user_id,
                content=content,
                created_at=datetime.now(timezone.utc),
            )
            self._next_comment_id += 1
            self._comments[report_id].append(comment)
            return comment

    def list_comments(self, report_id: UUID, limit: int) -> list[ReportComment]:
        with self._lock:
            comments = self._comments.get(report_id)
            if comments is None:
                raise ReportNotFound
            return sorted(
                comments,
                key=lambda comment: (comment.created_at, comment.id),
                reverse=True,
            )[:limit]

    def confirm(self, report_id: UUID, user_id: int) -> int:
        with self._lock:
            report = self._reports.get(report_id)
            if report is None:
                raise ReportNotFound
            owner_id, _ = report
            if owner_id == user_id:
                raise ReportOwnerCannotConfirm

            confirmations = self._confirmations[report_id]
            if user_id in confirmations:
                raise AlreadyConfirmed
            confirmations.add(user_id)
            self._timeline[report_id].append(
                ReportTimelineEvent(
                    id=self._next_event_id,
                    type="confirmacao_adicionada",
                    actor=f"citizen:{user_id}",
                    justification=None,
                    created_at=datetime.now(timezone.utc),
                )
            )
            self._next_event_id += 1
            return len(confirmations)

    def _new_protocol(self) -> str:
        while True:
            suffix = "".join(secrets.choice(PROTOCOL_ALPHABET) for _ in range(6))
            protocol = f"RPT-{datetime.now(timezone.utc):%Y}-{suffix}"
            if protocol not in self._protocols:
                self._protocols.add(protocol)
                return protocol


class OracleReportRepository:
    def __init__(self, database: OracleDatabase) -> None:
        self._database = database

    def reopen_report(self, report_id, user_id, reason):
        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.execute(
                    """
                    SELECT user_id, received_at,
                           NVL((
                               SELECT type FROM (
                                   SELECT type FROM report_events
                                   WHERE report_id = :report_id
                                     AND type IN ('recebido','encaminhado','em_andamento','resolvido','reaberto','contestado')
                                   ORDER BY id DESC
                               ) WHERE ROWNUM = 1
                           ), 'recebido')
                    FROM reports WHERE id = :report_id
                    """,
                    report_id=str(report_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ReportNotFound
                if row[0] != user_id:
                    raise ReportNotOwner
                if row[2] != "resolvido":
                    raise ReopenNotAllowed
                if row[1] < datetime.now(timezone.utc) - timedelta(days=30):
                    raise ReopenNotAllowed

                cursor.execute(
                    """
                    INSERT INTO report_events
                        (report_id, type, actor, justification)
                    VALUES (:report_id, 'reaberto', :actor, :justification)
                    """,
                    report_id=str(report_id),
                    actor=f"citizen:{user_id}",
                    justification=reason,
                )
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()
        return self.get_detail(report_id)

    def flag_report(self, report_id, user_id, reason, note):
        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.execute(
                    "SELECT 1 FROM reports WHERE id = :report_id",
                    report_id=str(report_id),
                )
                if cursor.fetchone() is None:
                    raise ReportNotFound
                cursor.execute(
                    """
                    SELECT 1 FROM report_events
                    WHERE report_id = :report_id
                      AND type = 'sinalizado'
                      AND actor = :actor
                    """,
                    report_id=str(report_id),
                    actor=f"citizen:{user_id}",
                )
                if cursor.fetchone() is not None:
                    raise ReportAlreadyFlagged
                justification = f"{reason}: {note}" if note else reason
                cursor.execute(
                    """
                    INSERT INTO report_events
                        (report_id, type, actor, justification)
                    VALUES (:report_id, 'sinalizado', :actor, :justification)
                    """,
                    report_id=str(report_id),
                    actor=f"citizen:{user_id}",
                    justification=justification,
                )
                cursor.execute(
                    """
                    UPDATE reports SET triage_state = 'in_moderation'
                    WHERE id = :report_id
                    """,
                    report_id=str(report_id),
                )
                cursor.execute(
                    """
                    INSERT INTO audit_log
                        (actor_user_id, action, resource_type, resource_id, justification)
                    VALUES (:actor, 'flag_report', 'report', :resource, :justification)
                    """,
                    actor=user_id,
                    resource=str(report_id),
                    justification=justification,
                )
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def nudge_report(self, report_id, user_id):
        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.execute(
                    """
                    SELECT r.user_id,
                           NVL((
                               SELECT type FROM (
                                   SELECT type FROM report_events
                                   WHERE report_id = r.id
                                   ORDER BY id DESC
                               ) WHERE ROWNUM = 1
                           ), 'recebido')
                    FROM reports r WHERE r.id = :report_id
                    """,
                    report_id=str(report_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ReportNotFound
                if row[0] != user_id:
                    raise ReportNotOwner
                if row[1] not in {"encaminhado", "em_andamento"}:
                    raise NudgeNotAllowed
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM report_events
                    WHERE report_id = :report_id
                      AND type = 'cobrado'
                      AND actor = :actor
                    """,
                    report_id=str(report_id),
                    actor=f"citizen:{user_id}",
                )
                if int(cursor.fetchone()[0]) >= 3:
                    raise NudgeNotAllowed
                cursor.execute(
                    """
                    INSERT INTO report_events
                        (report_id, type, actor)
                    VALUES (:report_id, 'cobrado', :actor)
                    """,
                    report_id=str(report_id),
                    actor=f"citizen:{user_id}",
                )
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def update_agency_status(self, report_id, action, deadline, justification):
        if action not in {"in_progress", "resolved", "contest"}:
            raise InvalidAgencyAction
        if action == "in_progress" and deadline is None:
            raise InvalidAgencyAction
        if action in {"resolved", "contest"} and not justification:
            raise InvalidAgencyAction
        event_type = {
            "in_progress": "em_andamento",
            "resolved": "resolvido",
            "contest": "contestado",
        }[action]

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.execute(
                    "SELECT 1 FROM reports WHERE id = :report_id",
                    report_id=str(report_id),
                )
                if cursor.fetchone() is None:
                    raise ReportNotFound
                cursor.execute(
                    """
                    INSERT INTO report_events
                        (report_id, type, actor, justification, deadline)
                    VALUES (:report_id, :event_type, 'agency', :justification, :deadline)
                    """,
                    report_id=str(report_id),
                    event_type=event_type,
                    justification=justification,
                    deadline=deadline,
                )
                cursor.execute(
                    """
                    UPDATE reports
                    SET triage_state = CASE
                            WHEN :event_type = 'resolvido' THEN 'confirmed'
                            ELSE triage_state
                        END
                    WHERE id = :report_id
                    """,
                    event_type=event_type,
                    report_id=str(report_id),
                )
                cursor.execute(
                    """
                    INSERT INTO audit_log
                        (action, resource_type, resource_id, justification)
                    VALUES ('agency_status', 'report', :resource, :justification)
                    """,
                    resource=str(report_id),
                    justification=justification,
                )
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()
        return self.get_detail(report_id)

    def list_moderation(self, limit):
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT r.id, r.protocol, r.category, r.lat, r.lon,
                           r.received_at, r.group_id,
                           NVL(g.confirmation_count, 0),
                           NVL((
                               SELECT type FROM (
                                   SELECT type FROM report_events e
                                   WHERE e.report_id = r.id
                                   ORDER BY e.id DESC
                               ) WHERE ROWNUM = 1
                           ), 'recebido')
                    FROM reports r
                    JOIN report_groups g ON g.id = r.group_id
                    WHERE r.triage_state = 'in_moderation'
                       OR EXISTS (
                           SELECT 1 FROM report_events e
                           WHERE e.report_id = r.id
                             AND e.type IN ('sinalizado','enviado_moderacao')
                       )
                    ORDER BY r.received_at DESC
                    FETCH FIRST :limit ROWS ONLY
                    """,
                    limit=limit,
                )
                return [
                    ReportSummary(
                        id=UUID(row[0]),
                        protocol=row[1],
                        status=ReportStatus(row[8]) if row[8] in {status.value for status in ReportStatus} else ReportStatus.RECEIVED,
                        category=ReportCategory(row[2]) if row[2] else None,
                        latitude=float(row[3]),
                        longitude=float(row[4]),
                        received_at=row[5],
                        group_id=str(row[6]),
                        confirmation_count=int(row[7]),
                    )
                    for row in cursor.fetchall()
                ]
            finally:
                cursor.close()

    def export_user_data(self, user_id: int) -> dict[str, object]:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT id, protocol, description, category, lat, lon,
                           received_at, triage_state
                    FROM reports
                    WHERE user_id = :user_id
                       OR EXISTS (
                           SELECT 1 FROM notification_links l
                           WHERE l.report_id = reports.id
                             AND l.user_id = :user_id
                       )
                    """,
                    user_id=user_id,
                )
                reports = [
                    {
                        "id": row[0],
                        "protocol": row[1],
                        "description": row[2],
                        "category": row[3],
                        "latitude": float(row[4]),
                        "longitude": float(row[5]),
                        "received_at": row[6].isoformat(),
                        "triage_state": row[7],
                    }
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    SELECT push_token, platform
                    FROM notification_devices
                    WHERE user_id = :user_id
                    """,
                    user_id=user_id,
                )
                devices = [
                    {"push_token": row[0], "platform": row[1]}
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    SELECT id, report_id, content, created_at
                    FROM report_comments
                    WHERE user_id = :user_id
                    """,
                    user_id=user_id,
                )
                comments = [
                    {
                        "id": int(row[0]),
                        "report_id": row[1],
                        "content": row[2],
                        "created_at": row[3].isoformat(),
                    }
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    INSERT INTO audit_log
                        (actor_user_id, action, resource_type)
                    VALUES (:actor, 'export_user_data', 'account')
                    """,
                    actor=user_id,
                )
                connection.commit()
                return {
                    "user_id": user_id,
                    "reports": reports,
                    "comments": comments,
                    "notification_devices": devices,
                }
            finally:
                cursor.close()

    def delete_user_data(self, user_id: int) -> None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.execute(
                    "UPDATE reports SET user_id = NULL WHERE user_id = :user_id",
                    user_id=user_id,
                )
                cursor.execute(
                    "UPDATE report_comments SET user_id = NULL WHERE user_id = :user_id",
                    user_id=user_id,
                )
                cursor.execute(
                    "DELETE FROM confirmations WHERE user_id = :user_id",
                    user_id=user_id,
                )
                cursor.execute(
                    "DELETE FROM notification_links WHERE user_id = :user_id",
                    user_id=user_id,
                )
                cursor.execute(
                    "DELETE FROM notification_devices WHERE user_id = :user_id",
                    user_id=user_id,
                )
                cursor.execute(
                    """
                    INSERT INTO audit_log
                        (actor_user_id, action, resource_type)
                    VALUES (:actor, 'delete_user_data', 'account')
                    """,
                    actor=user_id,
                )
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def get_public_metrics(
        self,
        from_date: datetime | None,
        to_date: datetime | None,
        category: str | None,
        agency_id: str | None,
    ) -> dict[str, object]:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                parameters: dict[str, object] = {}
                filters = ["1 = 1"]
                if from_date is not None:
                    filters.append("r.received_at >= :from_date")
                    parameters["from_date"] = from_date
                if to_date is not None:
                    filters.append("r.received_at <= :to_date")
                    parameters["to_date"] = to_date
                if category is not None:
                    filters.append("COALESCE(r.category, 'a_classificar') = :category")
                    parameters["category"] = category
                if agency_id is not None:
                    filters.append(
                        "EXISTS (SELECT 1 FROM report_events er "
                        "WHERE er.report_id = r.id "
                        "AND er.payload LIKE '%' || :agency_id || '%')"
                    )
                    parameters["agency_id"] = agency_id

                filter_sql = " AND ".join(filters)
                cursor.execute(
                    f"""
                    SELECT
                        COUNT(*) AS reports,
                        AVG(CASE WHEN resolved.type = 'resolvido'
                            THEN (resolved.created_at - r.received_at) * 24
                            ELSE NULL END),
                        AVG(CASE WHEN resolved.type = 'resolvido' THEN 1 ELSE 0 END),
                        COUNT(DISTINCT CASE
                            WHEN EXISTS (
                                SELECT 1 FROM confirmations c
                                JOIN report_groups g ON g.id = c.target_id
                                WHERE g.canonical_report_id = r.id
                            ) THEN r.id END)
                    FROM reports r
                    LEFT JOIN LATERAL (
                        SELECT type, created_at
                        FROM report_events
                        WHERE report_id = r.id AND type = 'resolvido'
                        ORDER BY id DESC
                        FETCH FIRST 1 ROW ONLY
                    ) resolved ON 1 = 1
                    WHERE {filter_sql}
                    """,
                    **parameters,
                )
                row = cursor.fetchone()
                total = int(row[0] or 0)
                avg_hours = round(float(row[1]), 2) if row[1] is not None else None
                resolution = round(float(row[2]), 4) if row[2] is not None else None
                recurrence = int(row[3] or 0)

                agency_parameters = dict(parameters)
                cursor.execute(
                    f"""
                    SELECT agency_id, agency_name, COUNT(*) reports,
                           AVG(resolved_hours), AVG(resolved_flag)
                    FROM (
                        SELECT r.id,
                               rr.agency_id,
                               a.name agency_name,
                               CASE WHEN resolved.type = 'resolvido'
                                    THEN (resolved.created_at - r.received_at) * 24
                                    END resolved_hours,
                               CASE WHEN resolved.type = 'resolvido' THEN 1 ELSE 0 END resolved_flag
                        FROM reports r
                        LEFT JOIN report_events rr
                            ON rr.report_id = r.id
                           AND rr.type = 'encaminhado'
                        JOIN agencies a
                          ON a.agency_id = JSON_VALUE(
                              rr.payload,
                              '$.agency_id'
                              RETURNING VARCHAR2(64) NULL ON ERROR
                          )
                        LEFT JOIN LATERAL (
                            SELECT type, created_at
                            FROM report_events
                            WHERE report_id = r.id AND type = 'resolvido'
                            ORDER BY id DESC
                            FETCH FIRST 1 ROW ONLY
                        ) resolved ON 1 = 1
                        WHERE {filter_sql}
                    )
                    GROUP BY agency_id, agency_name
                    HAVING COUNT(*) >= 5
                    ORDER BY agency_id
                    """,
                    **agency_parameters,
                )
                by_agency = [
                    {
                        "agency": {"id": row[0], "name": row[1]},
                        "reports": int(row[2]),
                        "avg_response_hours": (
                            round(float(row[3]), 2) if row[3] is not None else None
                        ),
                        "resolution_rate": (
                            round(float(row[4]), 4) if row[4] is not None else None
                        ),
                    }
                    for row in cursor.fetchall()
                ]
                return {
                    "period": {
                        "from": from_date.date().isoformat() if from_date else None,
                        "to": to_date.date().isoformat() if to_date else None,
                    },
                    "totals": {
                        "reports": total,
                        "avg_response_hours": avg_hours,
                        "resolution_rate": resolution,
                        "recurrence": recurrence,
                    },
                    "by_agency": by_agency,
                }
            finally:
                cursor.close()

    def create(self, report: NewReport) -> PersistedReport:
        import oracledb

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                protocol = cursor.var(oracledb.DB_TYPE_VARCHAR, size=20)
                created = cursor.var(oracledb.DB_TYPE_NUMBER)
                try:
                    cursor.callproc(
                        "PKG_REPORTES.registrar_reporte",
                        [
                            str(report.id),
                            report.user_id,
                            report.requester_user_id,
                            report.category.value if report.category else None,
                            report.description,
                            report.latitude,
                            report.longitude,
                            encode_geohash(report.latitude, report.longitude),
                            report.client_created_at,
                            str(report.correlation_id),
                            None,
                            int(report.has_photo),
                            protocol,
                            created,
                        ],
                    )
                    cursor.execute(
                        "SELECT received_at FROM reports WHERE id = :report_id",
                        report_id=str(report.id),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise RuntimeError(
                            "PKG_REPORTES não retornou o reporte registrado."
                        )
                    connection.commit()
                    committed = True
                except oracledb.DatabaseError as error:
                    oracle_error = error.args[0] if error.args else None
                    error_code = getattr(oracle_error, "code", None)
                    if error_code == 20011:
                        raise ReportIdConflict from error
                    if error_code == 20010:
                        raise ClientTimestampOutOfRange(
                            "client_created_at fora da janela permitida."
                        ) from error
                    raise

                return PersistedReport(
                    id=report.id,
                    protocol=protocol.getvalue(),
                    received_at=row[0],
                    was_created=bool(created.getvalue()),
                )
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()
    def get_detail(self, report_id: UUID) -> ReportDetail:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    WITH latest_status AS (
                        SELECT report_id, type,
                               ROW_NUMBER() OVER (
                                   PARTITION BY report_id ORDER BY id DESC
                               ) AS row_number
                        FROM report_events
                        WHERE type IN (
                            'recebido',
                            'encaminhado',
                            'em_andamento',
                            'resolvido',
                            'reaberto'
                        )
                    )
                    SELECT r.id,
                           r.protocol,
                           CASE latest_status.type
                               WHEN 'reaberto' THEN 'em_andamento'
                               ELSE NVL(latest_status.type, 'recebido')
                           END AS status,
                           COALESCE(
                               (
                                   SELECT JSON_VALUE(
                                       classification_event.payload,
                                       '$.category'
                                       RETURNING VARCHAR2(32) NULL ON ERROR
                                   )
                                   FROM report_events classification_event
                                   WHERE classification_event.report_id = r.id
                                     AND classification_event.type IN (
                                         'classificado',
                                         'classificacao_confirmada',
                                         'classificacao_corrigida'
                                     )
                                   ORDER BY classification_event.id DESC
                                   FETCH FIRST 1 ROW ONLY
                               ),
                               r.category
                           ) AS category,
                           r.description,
                           r.lat,
                           r.lon,
                           r.received_at,
                           r.user_id,
                           r.has_photo,
                           r.triage_state,
                           r.group_id,
                           report_groups.confirmation_count
                    FROM reports r
                    JOIN report_groups ON report_groups.id = r.group_id
                    LEFT JOIN latest_status
                        ON latest_status.report_id = r.id
                       AND latest_status.row_number = 1
                    WHERE r.id = :report_id
                    """,
                    report_id=str(report_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ReportNotFound

                cursor.execute(
                    """
                    SELECT id, type, actor, justification, created_at
                    FROM report_events
                    WHERE report_id = :report_id
                    ORDER BY id
                    """,
                    report_id=str(report_id),
                )
                timeline = [
                    ReportTimelineEvent(
                        id=int(event[0]),
                        type=event[1],
                        actor=event[2],
                        justification=event[3],
                        created_at=event[4],
                    )
                    for event in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    SELECT type, payload, deadline
                    FROM report_events
                    WHERE report_id = :report_id
                      AND type IN (
                          'classificado',
                          'classificacao_confirmada',
                          'classificacao_corrigida',
                          'encaminhado',
                          'enviado_moderacao'
                      )
                    ORDER BY id
                    """,
                    report_id=str(report_id),
                )
                triage_events = cursor.fetchall()
                classification = None
                agency_id = None
                agency_name = None
                deadline = None
                triage_state = TriageState.PENDING_CLASSIFICATION
                for event_type, payload, event_deadline in triage_events:
                    event_data = self._decode_event_payload(payload)
                    if event_type in (
                        "classificado",
                        "classificacao_confirmada",
                        "classificacao_corrigida",
                    ):
                        classification = ClassificationResult.model_validate(
                            event_data
                        )
                        triage_state = (
                            TriageState.AWAITING_USER
                            if event_type == "classificado"
                            else TriageState.CONFIRMED
                        )
                    elif event_type == "encaminhado":
                        agency_id = event_data.get("agency_id")
                        agency_name = event_data.get("agency_name")
                        deadline = event_deadline
                    elif event_type == "enviado_moderacao":
                        triage_state = TriageState.IN_MODERATION

                return ReportDetail(
                    summary=ReportSummary(
                        id=UUID(row[0]),
                        protocol=row[1],
                        status=ReportStatus(row[2]),
                        category=(
                            classification.category
                            if classification is not None
                            else ReportCategory(row[3]) if row[3] else None
                        ),
                        latitude=float(row[5]),
                        longitude=float(row[6]),
                        received_at=row[7],
                        group_id=str(row[11]),
                        confirmation_count=int(row[12]),
                    ),
                    description=row[4],
                    anonymous=row[8] is None,
                    has_photo=bool(row[9]),
                    triage_state=triage_state,
                    classification=classification,
                    agency_id=agency_id,
                    agency_name=agency_name,
                    deadline=deadline,
                    timeline=timeline,
                )
            finally:
                cursor.close()

    def classification_input(self, report_id: UUID) -> ClassificationInput:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT description, category
                    FROM reports
                    WHERE id = :report_id
                    """,
                    report_id=str(report_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ReportNotFound
                return ClassificationInput(
                    text=row[0],
                    user_category=ReportCategory(row[1]) if row[1] else None,
                )
            finally:
                cursor.close()

    def assert_photo_owner(
        self,
        report_id: UUID,
        user_id: int,
        expected_sha256: str,
    ) -> None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT r.has_photo, nl.user_id, r.photo_key
                    FROM reports r
                    LEFT JOIN notification_links nl
                        ON nl.report_id = r.id
                       AND nl.user_id = :user_id
                    WHERE r.id = :report_id
                    """,
                    report_id=str(report_id),
                    user_id=user_id,
                )
                row = cursor.fetchone()
                if row is None:
                    raise ReportNotFound
                if not bool(row[0]):
                    raise ReportPhotoNotEnabled
                if row[1] is None:
                    raise ReportNotOwner
                expected_key = f"objects/{expected_sha256.lower()}.jpg"
                if row[2] is not None and row[2] != expected_key:
                    raise ReportPhotoConflict
            finally:
                cursor.close()

    def set_photo_key(self, report_id: UUID, photo_key: str) -> None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.callproc(
                    "PKG_REPORTES.finalizar_foto",
                    [str(report_id), photo_key],
                )
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def get_photo_key(self, report_id: UUID) -> str | None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "SELECT photo_key FROM reports WHERE id = :report_id",
                    report_id=str(report_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ReportNotFound
                return row[0]
            finally:
                cursor.close()

    def get_agency_email(self, report_id: UUID) -> str | None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT agency.contact_email
                    FROM report_events evt
                    JOIN agencies agency
                      ON agency.agency_id = JSON_VALUE(
                          evt.payload,
                          '$.agency_id' RETURNING VARCHAR2(64) NULL ON ERROR
                      )
                    WHERE evt.report_id = :report_id
                      AND evt.type = 'encaminhado'
                      AND agency.active = 1
                    ORDER BY evt.id DESC
                    FETCH FIRST 1 ROW ONLY
                    """,
                    report_id=str(report_id),
                )
                row = cursor.fetchone()
                return row[0] if row is not None else None
            finally:
                cursor.close()

    def register_notification_device(
        self,
        user_id: int,
        push_token: str,
        platform: str,
    ) -> None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.execute(
                    """
                    MERGE INTO notification_devices target
                    USING (
                        SELECT :user_id AS user_id,
                               :push_token AS push_token,
                               :platform AS platform
                        FROM dual
                    ) source
                    ON (
                        target.push_token = source.push_token
                    )
                    WHEN MATCHED THEN
                        UPDATE SET target.user_id = source.user_id,
                                   target.platform = source.platform,
                                   target.updated_at = SYSTIMESTAMP
                    WHEN NOT MATCHED THEN
                        INSERT (user_id, push_token, platform)
                        VALUES (
                            source.user_id,
                            source.push_token,
                            source.platform
                        )
                    """,
                    user_id=user_id,
                    push_token=push_token,
                    platform=platform,
                )
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def remove_notification_device(self, user_id: int, push_token: str) -> None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.execute(
                    """
                    DELETE FROM notification_devices
                    WHERE user_id = :user_id AND push_token = :push_token
                    """,
                    user_id=user_id,
                    push_token=push_token,
                )
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def list_notification_tokens(self, report_id: UUID) -> list[str]:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT push_token
                    FROM notification_devices device
                    JOIN notification_links link
                      ON link.user_id = device.user_id
                    WHERE link.report_id = :report_id
                    """,
                    report_id=str(report_id),
                )
                return [str(row[0]) for row in cursor.fetchall()]
            finally:
                cursor.close()

    def get_status_event(self, report_id: UUID, event_id: int) -> str | None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT type
                    FROM report_events
                    WHERE report_id = :report_id
                      AND id = :event_id
                      AND type IN (
                          'encaminhado',
                          'em_andamento',
                          'resolvido'
                      )
                    """,
                    report_id=str(report_id),
                    event_id=event_id,
                )
                row = cursor.fetchone()
                return str(row[0]) if row is not None else None
            finally:
                cursor.close()

    def get_overdue_status(self, report_id: UUID) -> ReportStatus | None:
        detail = self.get_detail(report_id)
        if (
            detail.summary.status not in {
                ReportStatus.FORWARDED,
                ReportStatus.IN_PROGRESS,
            }
            or detail.deadline is None
            or detail.deadline >= datetime.now(timezone.utc)
        ):
            return None
        return detail.summary.status

    def mark_for_moderation(self, report_id: UUID) -> None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.callproc(
                    "PKG_JOBS.enviar_moderacao",
                    [str(report_id)],
                )
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    @staticmethod
    def _decode_event_payload(payload: object) -> dict[str, object]:
        if payload is None:
            return {}
        if hasattr(payload, "read"):
            payload = payload.read()
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        if isinstance(payload, str):
            decoded = json.loads(payload)
            if not isinstance(decoded, dict):
                raise RuntimeError("Payload de evento inválido.")
            return decoded
        if isinstance(payload, dict):
            return payload
        raise RuntimeError("Payload de evento inválido.")

    def list_in_area(self, box: GeoBox, max_items: int) -> list[ReportSummary]:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                # O retângulo usa ix_reports_lat_lon; o raio exato é aplicado no serviço.
                cursor.execute(
                    """
                    WITH area_reports AS (
                        SELECT r.id, r.protocol, r.category, r.lat, r.lon,
                               r.received_at, r.group_id
                        FROM reports r
                        WHERE r.lat BETWEEN :min_lat AND :max_lat
                          AND r.lon BETWEEN :min_lon AND :max_lon
                          AND r.triage_state <> 'in_moderation'
                        ORDER BY r.received_at DESC
                        FETCH FIRST :max_items ROWS ONLY
                    )
                    SELECT r.id,
                           r.protocol,
                           CASE (
                               SELECT e.type FROM report_events e
                               WHERE e.report_id = r.id
                                 AND e.type IN (
                                     'recebido', 'encaminhado', 'em_andamento',
                                     'resolvido', 'reaberto'
                                 )
                               ORDER BY e.id DESC
                               FETCH FIRST 1 ROW ONLY
                           )
                               WHEN 'reaberto' THEN 'em_andamento'
                               WHEN 'encaminhado' THEN 'encaminhado'
                               WHEN 'em_andamento' THEN 'em_andamento'
                               WHEN 'resolvido' THEN 'resolvido'
                               ELSE 'recebido'
                           END AS status,
                           COALESCE(
                               (
                                   SELECT JSON_VALUE(
                                       e.payload, '$.category'
                                       RETURNING VARCHAR2(32) NULL ON ERROR
                                   )
                                   FROM report_events e
                                   WHERE e.report_id = r.id
                                     AND e.type IN (
                                         'classificado',
                                         'classificacao_confirmada',
                                         'classificacao_corrigida'
                                     )
                                   ORDER BY e.id DESC
                                   FETCH FIRST 1 ROW ONLY
                               ),
                               r.category
                           ) AS category,
                           r.lat,
                           r.lon,
                           r.received_at,
                           r.group_id,
                           NVL(g.confirmation_count, 0)
                    FROM area_reports r
                    LEFT JOIN report_groups g ON g.id = r.group_id
                    ORDER BY r.received_at DESC
                    """,
                    min_lat=box.min_lat,
                    max_lat=box.max_lat,
                    min_lon=box.min_lon,
                    max_lon=box.max_lon,
                    max_items=max_items,
                )
                return [
                    ReportSummary(
                        id=UUID(row[0]),
                        protocol=row[1],
                        status=ReportStatus(row[2]),
                        category=ReportCategory(row[3]) if row[3] else None,
                        latitude=float(row[4]),
                        longitude=float(row[5]),
                        received_at=row[6],
                        group_id=str(row[7]),
                        confirmation_count=int(row[8]),
                    )
                    for row in cursor.fetchall()
                ]
            finally:
                cursor.close()

    def list_user_reports(
        self,
        user_id: int,
        limit: int,
        cursor_id: UUID | None,
        status: ReportStatus | None,
    ) -> list[ReportSummary]:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                parameters: dict[str, object] = {
                    "user_id": user_id,
                    "limit": limit,
                }
                status_filter = ""
                cursor_filter = ""
                if status is not None:
                    status_filter = "AND status = :status"
                    parameters["status"] = status.value
                if cursor_id is not None:
                    cursor.execute(
                        """
                        SELECT r.received_at
                        FROM reports r
                        JOIN notification_links
                            ON notification_links.report_id = r.id
                        WHERE r.id = :report_id
                          AND notification_links.user_id = :user_id
                        """,
                        report_id=str(cursor_id),
                        user_id=user_id,
                    )
                    cursor_row = cursor.fetchone()
                    if cursor_row is None:
                        raise InvalidReportCursor
                    cursor_filter = """
                        AND (
                            received_at < :cursor_received_at
                            OR (
                                received_at = :cursor_received_at
                                AND id < :cursor_id
                            )
                        )
                    """
                    parameters["cursor_received_at"] = cursor_row[0]
                    parameters["cursor_id"] = str(cursor_id)

                cursor.execute(
                    f"""
                    WITH latest_status AS (
                        SELECT report_id, type,
                               ROW_NUMBER() OVER (
                                   PARTITION BY report_id ORDER BY id DESC
                               ) AS row_number
                        FROM report_events
                        WHERE type IN (
                            'recebido',
                            'encaminhado',
                            'em_andamento',
                            'resolvido',
                            'reaberto'
                        )
                    ),
                    owned_reports AS (
                        SELECT r.id,
                               r.protocol,
                               CASE latest_status.type
                                   WHEN 'reaberto' THEN 'em_andamento'
                                   ELSE NVL(latest_status.type, 'recebido')
                               END AS status,
                               COALESCE(
                                   (
                                       SELECT JSON_VALUE(
                                           classification_event.payload,
                                           '$.category'
                                           RETURNING VARCHAR2(32) NULL ON ERROR
                                       )
                                       FROM report_events classification_event
                                       WHERE classification_event.report_id = r.id
                                         AND classification_event.type IN (
                                             'classificado',
                                             'classificacao_confirmada',
                                             'classificacao_corrigida'
                                         )
                                       ORDER BY classification_event.id DESC
                                       FETCH FIRST 1 ROW ONLY
                                   ),
                                   r.category
                               ) AS category,
                               r.lat,
                               r.lon,
                               r.received_at,
                               r.group_id,
                               report_groups.confirmation_count
                        FROM reports r
                        JOIN notification_links
                            ON notification_links.report_id = r.id
                        JOIN report_groups
                            ON report_groups.id = r.group_id
                        LEFT JOIN latest_status
                            ON latest_status.report_id = r.id
                           AND latest_status.row_number = 1
                        WHERE notification_links.user_id = :user_id
                    )
                    SELECT id, protocol, status, category, lat, lon,
                           received_at, group_id, confirmation_count
                    FROM (
                        SELECT id, protocol, status, category, lat, lon,
                               received_at, group_id, confirmation_count
                        FROM owned_reports
                        WHERE 1 = 1
                          {status_filter}
                          {cursor_filter}
                        ORDER BY received_at DESC, id DESC
                    )
                    WHERE ROWNUM <= :limit
                    """,
                    **parameters,
                )
                return [
                    ReportSummary(
                        id=UUID(row[0]),
                        protocol=row[1],
                        status=ReportStatus(row[2]),
                        category=ReportCategory(row[3]) if row[3] else None,
                        latitude=float(row[4]),
                        longitude=float(row[5]),
                        received_at=row[6],
                        group_id=str(row[7]),
                        confirmation_count=int(row[8]),
                    )
                    for row in cursor.fetchall()
                ]
            finally:
                cursor.close()

    def create_comment(
        self,
        report_id: UUID,
        user_id: int,
        content: str,
    ) -> ReportComment:
        import oracledb

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                comment_id = cursor.var(oracledb.DB_TYPE_NUMBER)
                try:
                    cursor.callproc(
                        "PKG_REPORTES.criar_comentario",
                        [str(report_id), user_id, content, comment_id],
                    )
                    cursor.execute(
                        "SELECT created_at FROM report_comments WHERE id = :id",
                        id=comment_id.getvalue(),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise RuntimeError(
                            "PKG_REPORTES não retornou o comentário criado."
                        )
                    connection.commit()
                    committed = True
                except oracledb.DatabaseError as error:
                    oracle_error = error.args[0] if error.args else None
                    if getattr(oracle_error, "code", None) == 20040:
                        raise ReportNotFound from error
                    raise

                return ReportComment(
                    id=int(comment_id.getvalue()),
                    report_id=report_id,
                    user_id=user_id,
                    content=content,
                    created_at=row[0],
                )
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def list_comments(self, report_id: UUID, limit: int) -> list[ReportComment]:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "SELECT 1 FROM reports WHERE id = :report_id",
                    report_id=str(report_id),
                )
                if cursor.fetchone() is None:
                    raise ReportNotFound

                cursor.execute(
                    """
                    SELECT id, report_id, user_id, content, created_at
                    FROM (
                        SELECT id, report_id, user_id, content, created_at
                        FROM report_comments
                        WHERE report_id = :report_id
                        ORDER BY created_at DESC, id DESC
                    )
                    WHERE ROWNUM <= :limit
                    """,
                    report_id=str(report_id),
                    limit=limit,
                )
                return [
                    ReportComment(
                        id=int(row[0]),
                        report_id=UUID(row[1]),
                        user_id=int(row[2]),
                        content=row[3],
                        created_at=row[4],
                    )
                    for row in cursor.fetchall()
                ]
            finally:
                cursor.close()

    def confirm(self, report_id: UUID, user_id: int) -> int:
        import oracledb

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                confirmation_count = cursor.var(oracledb.DB_TYPE_NUMBER)
                try:
                    cursor.callproc(
                        "PKG_REPORTES.confirmar",
                        [
                            str(report_id),
                            user_id,
                            confirmation_count,
                        ],
                    )
                    connection.commit()
                    committed = True
                except oracledb.DatabaseError as error:
                    oracle_error = error.args[0] if error.args else None
                    error_code = getattr(oracle_error, "code", None)
                    if error_code == 20040:
                        raise ReportNotFound from error
                    if error_code == 20041:
                        raise ReportOwnerCannotConfirm from error
                    if error_code == 20042:
                        raise AlreadyConfirmed from error
                    raise
                return int(confirmation_count.getvalue())
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def record_classification(
        self,
        report_id: UUID,
        classification: ClassificationResult,
    ) -> None:
        import oracledb

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                try:
                    cursor.callproc(
                        "PKG_REPORTES.registrar_classificacao",
                        [str(report_id), classification.model_dump_json()],
                    )
                    connection.commit()
                    committed = True
                except oracledb.DatabaseError as error:
                    oracle_error = error.args[0] if error.args else None
                    error_code = getattr(oracle_error, "code", None)
                    if error_code == 20040:
                        raise ReportNotFound from error
                    if error_code == 20043:
                        raise TriageConflict from error
                    raise
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def apply_triage(
        self,
        report_id: UUID,
        user_id: int,
        action: str,
        classification: ClassificationResult,
        route: RouteDecision | None,
        deadline: datetime | None,
    ) -> None:
        import oracledb

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                try:
                    cursor.callproc(
                        "PKG_ROTEAMENTO.aplicar_triagem",
                        [
                            str(report_id),
                            user_id,
                            action,
                            classification.model_dump_json(),
                        ],
                    )
                    connection.commit()
                    committed = True
                except oracledb.DatabaseError as error:
                    oracle_error = error.args[0] if error.args else None
                    error_code = getattr(oracle_error, "code", None)
                    if error_code == 20040:
                        raise ReportNotFound from error
                    if error_code == 20041:
                        raise ReportNotOwner from error
                    if error_code == 20043:
                        raise TriageConflict from error
                    raise
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()


class OracleAuthRepository:
    def __init__(self, database: OracleDatabase) -> None:
        self._database = database

    def get_user(self, user_id: int) -> AuthUser:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT email, role, consent_version, created_at
                    FROM users
                    WHERE id = :user_id AND deleted_at IS NULL
                    """,
                    user_id=user_id,
                )
                row = cursor.fetchone()
                if row is None:
                    raise AccountNotFound
                return AuthUser(
                    id=user_id,
                    email=row[0],
                    role=row[1],
                    consent_version=row[2],
                    created_at=row[3],
                )
            finally:
                cursor.close()

    def update_email(self, user_id: int, email: str) -> AuthUser:
        normalized_email = email.strip().lower()
        import oracledb

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                try:
                    cursor.execute(
                        """
                        UPDATE users
                        SET email = :email
                        WHERE id = :user_id AND deleted_at IS NULL
                        """,
                        email=normalized_email,
                        user_id=user_id,
                    )
                    if cursor.rowcount != 1:
                        raise AccountNotFound
                    cursor.execute(
                        """
                        SELECT role, consent_version, created_at
                        FROM users
                        WHERE id = :user_id
                        """,
                        user_id=user_id,
                    )
                    row = cursor.fetchone()
                    connection.commit()
                    committed = True
                    return AuthUser(
                        id=user_id,
                        email=normalized_email,
                        role=row[0],
                        consent_version=row[1],
                        created_at=row[2],
                    )
                except oracledb.DatabaseError as error:
                    oracle_error = error.args[0] if error.args else None
                    if getattr(oracle_error, "code", None) == 1:
                        raise GoogleAccountConflict from error
                    raise
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def delete_account(self, user_id: int) -> None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.execute(
                    """
                    UPDATE users
                    SET deleted_at = SYSTIMESTAMP,
                        email = NULL,
                        google_sub = NULL
                    WHERE id = :user_id AND deleted_at IS NULL
                    """,
                    user_id=user_id,
                )
                if cursor.rowcount != 1:
                    raise AccountNotFound
                cursor.execute(
                    "DELETE FROM notification_links WHERE user_id = :user_id",
                    user_id=user_id,
                )
                cursor.execute(
                    "DELETE FROM notification_devices WHERE user_id = :user_id",
                    user_id=user_id,
                )
                cursor.execute(
                    "DELETE FROM refresh_tokens WHERE user_id = :user_id",
                    user_id=user_id,
                )
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def request_otp(
        self,
        email: str,
        code_hash: str,
        *,
        expires_at: datetime,
        consent_version: str | None,
        accepted_age: bool | None,
    ) -> None:
        import oracledb

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                try:
                    cursor.callproc(
                        "PKG_AUTH.solicitar_otp",
                        [
                            email,
                            code_hash,
                            expires_at,
                            consent_version,
                            (
                                int(accepted_age)
                                if accepted_age is not None
                                else None
                            ),
                        ],
                    )
                    connection.commit()
                    committed = True
                except oracledb.DatabaseError as error:
                    oracle_error = error.args[0] if error.args else None
                    if getattr(oracle_error, "code", None) == 20020:
                        raise ConsentRequired from error
                    raise
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def verify_otp(
        self,
        email: str,
        code_hash: str,
        *,
        refresh_token_hash: str,
        refresh_expires_at: datetime,
    ) -> AuthUser | None:
        import oracledb

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                status = cursor.var(oracledb.DB_TYPE_VARCHAR, size=20)
                user_id = cursor.var(oracledb.DB_TYPE_NUMBER)
                role = cursor.var(oracledb.DB_TYPE_VARCHAR, size=20)
                consent_version = cursor.var(
                    oracledb.DB_TYPE_VARCHAR,
                    size=64,
                )
                cursor.callproc(
                    "PKG_AUTH.validar_otp",
                    [
                        email,
                        code_hash,
                        refresh_token_hash,
                        refresh_expires_at,
                        status,
                        user_id,
                        role,
                        consent_version,
                    ],
                )
                if status.getvalue() != "ok":
                    connection.commit()
                    committed = True
                    return None

                cursor.execute(
                    "SELECT created_at FROM users WHERE id = :user_id",
                    user_id=user_id.getvalue(),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        "PKG_AUTH validou OTP sem retornar um usuário."
                    )
                connection.commit()
                committed = True
                return AuthUser(
                    id=int(user_id.getvalue()),
                    email=email,
                    role=role.getvalue(),
                    consent_version=consent_version.getvalue(),
                    created_at=row[0],
                )
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def rotate_refresh_token(
        self,
        old_token_hash: str,
        new_token_hash: str,
        *,
        expires_at: datetime,
    ) -> AuthUser | None:
        import oracledb

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                status = cursor.var(oracledb.DB_TYPE_VARCHAR, size=20)
                user_id = cursor.var(oracledb.DB_TYPE_NUMBER)
                role = cursor.var(oracledb.DB_TYPE_VARCHAR, size=20)
                consent_version = cursor.var(
                    oracledb.DB_TYPE_VARCHAR,
                    size=64,
                )
                cursor.callproc(
                    "PKG_AUTH.rotacionar_refresh_token",
                    [
                        old_token_hash,
                        new_token_hash,
                        expires_at,
                        status,
                        user_id,
                        role,
                        consent_version,
                    ],
                )
                if status.getvalue() != "ok":
                    connection.commit()
                    committed = True
                    return None

                cursor.execute(
                    "SELECT email, created_at FROM users WHERE id = :user_id",
                    user_id=user_id.getvalue(),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        "PKG_AUTH rotacionou token sem retornar um usuário."
                    )
                connection.commit()
                committed = True
                return AuthUser(
                    id=int(user_id.getvalue()),
                    email=row[0],
                    role=role.getvalue(),
                    consent_version=consent_version.getvalue(),
                    created_at=row[1],
                )
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def login_google(
        self,
        google_sub: str,
        email: str,
        *,
        consent_version: str | None,
        accepted_age: bool | None,
        refresh_token_hash: str,
        refresh_expires_at: datetime,
    ) -> AuthUser:
        import oracledb

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                status = cursor.var(oracledb.DB_TYPE_VARCHAR, size=32)
                user_id = cursor.var(oracledb.DB_TYPE_NUMBER)
                role = cursor.var(oracledb.DB_TYPE_VARCHAR, size=20)
                stored_consent = cursor.var(
                    oracledb.DB_TYPE_VARCHAR,
                    size=64,
                )
                cursor.callproc(
                    "PKG_AUTH.login_google",
                    [
                        google_sub,
                        email,
                        consent_version,
                        int(accepted_age) if accepted_age is not None else None,
                        refresh_token_hash,
                        refresh_expires_at,
                        status,
                        user_id,
                        role,
                        stored_consent,
                    ],
                )
                result = status.getvalue()
                if result == "consent_required":
                    connection.commit()
                    committed = True
                    raise ConsentRequired
                if result == "conflict":
                    connection.commit()
                    committed = True
                    raise GoogleAccountConflict
                if result != "ok":
                    connection.commit()
                    committed = True
                    raise RuntimeError(
                        f"PKG_AUTH.login_google retornou status inesperado: {result}"
                    )

                cursor.execute(
                    "SELECT email, created_at FROM users WHERE id = :user_id",
                    user_id=user_id.getvalue(),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        "PKG_AUTH.login_google validou usuário inexistente."
                    )
                connection.commit()
                committed = True
                return AuthUser(
                    id=int(user_id.getvalue()),
                    email=row[0],
                    role=role.getvalue(),
                    consent_version=stored_consent.getvalue(),
                    created_at=row[1],
                )
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()


