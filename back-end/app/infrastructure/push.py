"""Adaptadores de envio push com payload mínimo."""

import logging
from pathlib import Path
from typing import Protocol

import requests

from app.core.config import Settings
from app.models.notifications import PushMessage

logger = logging.getLogger(__name__)
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class PushDeliveryError(Exception):
    """Falha ao entregar uma notificação push."""


class PushSender(Protocol):
    def send(self, token: str, message: PushMessage) -> None: ...


class LogPushSender:
    """Adaptador local que não depende de credenciais nem de rede externa."""

    def send(self, token: str, message: PushMessage) -> None:
        logger.info(
            "Push de desenvolvimento: tipo=%s reporte=%s status=%s",
            message.data.get("type"),
            message.data.get("report_id"),
            message.data.get("status", "n/a"),
        )


class FcmPushSender:
    def __init__(
        self,
        project_id: str,
        service_account_file: Path,
        *,
        timeout_seconds: int,
    ) -> None:
        if not service_account_file.is_file():
            raise ValueError("Arquivo de credenciais do FCM não encontrado.")

        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        credentials, credential_project_id = google.auth.load_credentials_from_file(
            str(service_account_file),
            scopes=[FCM_SCOPE],
        )
        self._project_id = project_id or credential_project_id
        if not self._project_id:
            raise ValueError(
                "Informe FCM_PROJECT_ID ou o project_id nas credenciais do FCM."
            )
        self._timeout_seconds = timeout_seconds
        self._session = AuthorizedSession(credentials)

    def send(self, token: str, message: PushMessage) -> None:
        try:
            response = self._session.post(
                (
                    "https://fcm.googleapis.com/v1/projects/"
                    f"{self._project_id}/messages:send"
                ),
                json={
                    "message": {
                        "token": token,
                        "notification": {
                            "title": message.title,
                            "body": message.body,
                        },
                        "data": message.data,
                    }
                },
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as error:
            raise PushDeliveryError(
                "Não foi possível conectar ao FCM."
            ) from error
        if response.status_code >= 400:
            raise PushDeliveryError(
                f"FCM recusou a notificação (HTTP {response.status_code})."
            )


def build_push_sender(config: Settings) -> PushSender:
    if config.push_provider == "log":
        return LogPushSender()
    if config.push_provider == "fcm":
        if config.fcm_service_account_file is None:
            raise ValueError(
                "FCM_SERVICE_ACCOUNT_FILE é obrigatório para o provedor FCM."
            )
        return FcmPushSender(
            config.fcm_project_id,
            config.fcm_service_account_file,
            timeout_seconds=config.push_timeout_seconds,
        )
    raise ValueError(f"Provedor de push não suportado: {config.push_provider}")
