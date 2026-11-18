"""Envio de mensagens de autenticação por SMTP."""

import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings
from app.models.notifications import AgencyAssignment


class MailDeliveryError(Exception):
    """Falha ao entregar uma mensagem por e-mail."""


class OtpMailer(Protocol):
    def send_otp(self, email: str, code: str) -> None: ...


class AgencyMailer(Protocol):
    def send_assignment(self, assignment: AgencyAssignment) -> None: ...


class SmtpOtpMailer:
    def __init__(self, config: Settings) -> None:
        self._config = config

    def send_otp(self, email: str, code: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Seu código de acesso ao Reclame Já"
        message["From"] = self._config.smtp_sender
        message["To"] = email
        message.set_content(
            f"Seu código de acesso é {code}. "
            "Ele expira em 10 minutos e só pode ser usado uma vez."
        )

        try:
            with smtplib.SMTP(
                self._config.smtp_host,
                self._config.smtp_port,
                timeout=self._config.smtp_timeout_seconds,
            ) as smtp:
                if self._config.smtp_use_tls:
                    smtp.starttls()
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            raise MailDeliveryError("Não foi possível enviar o código.") from error


class SmtpAgencyMailer:
    def __init__(self, config: Settings) -> None:
        self._config = config

    def send_assignment(self, assignment: AgencyAssignment) -> None:
        if (
            not assignment.email
            or "\r" in assignment.email
            or "\n" in assignment.email
            or "@" not in assignment.email
        ):
            raise MailDeliveryError("Endereço do órgão inválido.")

        message = EmailMessage()
        message["Subject"] = f"Novo reporte {assignment.protocol}"
        message["From"] = self._config.smtp_sender
        message["To"] = assignment.email
        message.set_content(self._assignment_body(assignment))

        try:
            with smtplib.SMTP(
                self._config.smtp_host,
                self._config.smtp_port,
                timeout=self._config.smtp_timeout_seconds,
            ) as smtp:
                if self._config.smtp_use_tls:
                    smtp.starttls()
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            raise MailDeliveryError(
                "Não foi possível notificar o órgão."
            ) from error

    @staticmethod
    def _assignment_body(assignment: AgencyAssignment) -> str:
        lines = [
            f"Um novo reporte foi encaminhado para {assignment.agency_name}.",
            f"Protocolo: {assignment.protocol}",
            f"Identificador: {assignment.report_id}",
            f"Categoria: {assignment.category or 'a_classificar'}",
            f"Subcategoria: {assignment.subcategory or 'não informada'}",
            f"Urgência: {assignment.urgency or 'não informada'}",
            f"Descrição: {assignment.description or 'não informada'}",
            (
                "Coordenadas: "
                f"{assignment.latitude:.6f}, {assignment.longitude:.6f}"
            ),
            (
                "Prazo de referência: "
                f"{assignment.deadline.isoformat() if assignment.deadline else 'não definido'}"
            ),
        ]
        if assignment.photo_url:
            lines.append(f"Foto (link temporário): {assignment.photo_url}")
        return "\n".join(lines)
