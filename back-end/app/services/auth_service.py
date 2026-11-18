"""Casos de uso de login por OTP e renovação de sessão."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.infrastructure.mailer import OtpMailer
from app.models.auth import (
    AuthTokensResponse,
    AuthUser,
    ConsentRequest,
    OtpSentResponse,
    UserResponse,
)
from app.infrastructure.repositories import AuthRepository, ConsentRequired
from app.infrastructure.tokens import create_access_token

OTP_TTL = timedelta(minutes=10)
ACCESS_TOKEN_TTL_SECONDS = 15 * 60
REFRESH_TOKEN_TTL = timedelta(days=30)


class InvalidOtp(Exception):
    """Código inválido, expirado ou bloqueado."""


class AuthenticationNotConfigured(Exception):
    """Configuração criptográfica de autenticação ausente."""


class InvalidGoogleToken(Exception):
    """ID token Google inválido, expirado ou sem e-mail verificado."""


class GoogleVerificationUnavailable(Exception):
    """Não foi possível obter as chaves públicas para validar o token."""


class AuthService:
    def __init__(self, repository: AuthRepository, mailer: OtpMailer) -> None:
        self._repository = repository
        self._mailer = mailer

    def request_otp(
        self,
        email: str,
        consent: ConsentRequest | None,
    ) -> OtpSentResponse:
        secret = self._secret()
        normalized_email = email.strip().lower()
        code = f"{secrets.randbelow(1_000_000):06d}"
        code_hash = self._hash_otp(secret, normalized_email, code)
        self._repository.request_otp(
            normalized_email,
            code_hash,
            expires_at=datetime.now(timezone.utc) + OTP_TTL,
            consent_version=consent.version if consent else None,
            accepted_age=consent.accepted_age if consent else None,
        )
        self._mailer.send_otp(normalized_email, code)
        return OtpSentResponse()

    def verify_otp(self, email: str, code: str) -> AuthTokensResponse:
        secret = self._secret()
        normalized_email = email.strip().lower()
        refresh_token = secrets.token_urlsafe(48)
        user = self._repository.verify_otp(
            normalized_email,
            self._hash_otp(secret, normalized_email, code),
            refresh_token_hash=self._hash_refresh_token(refresh_token),
            refresh_expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_TTL,
        )
        if user is None:
            raise InvalidOtp
        return self._tokens_for_user(user, refresh_token, secret)

    def refresh(self, refresh_token: str) -> AuthTokensResponse:
        secret = self._secret()
        new_refresh_token = secrets.token_urlsafe(48)
        user = self._repository.rotate_refresh_token(
            self._hash_refresh_token(refresh_token),
            self._hash_refresh_token(new_refresh_token),
            expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_TTL,
        )
        if user is None:
            raise InvalidOtp
        return self._tokens_for_user(user, new_refresh_token, secret)

    def login_google(
        self,
        token: str,
        consent: ConsentRequest | None,
    ) -> AuthTokensResponse:
        secret = self._secret()
        client_id = settings.google_client_id.strip()
        if not client_id:
            raise AuthenticationNotConfigured

        claims = self._verify_google_token(token, client_id)
        google_sub = claims.get("sub")
        email = claims.get("email")
        if (
            not isinstance(google_sub, str)
            or not google_sub
            or not isinstance(email, str)
            or not email
            or claims.get("email_verified") is not True
        ):
            raise InvalidGoogleToken

        normalized_email = email.strip().lower()
        refresh_token = secrets.token_urlsafe(48)
        user = self._repository.login_google(
            google_sub,
            normalized_email,
            consent_version=consent.version if consent else None,
            accepted_age=consent.accepted_age if consent else None,
            refresh_token_hash=self._hash_refresh_token(refresh_token),
            refresh_expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_TTL,
        )
        return self._tokens_for_user(user, refresh_token, secret)

    def _tokens_for_user(
        self,
        user: AuthUser,
        refresh_token: str,
        secret: str,
    ) -> AuthTokensResponse:
        return AuthTokensResponse(
            access_token=create_access_token(
                user_id=user.id,
                role=user.role,
                secret=secret,
                expires_in=ACCESS_TOKEN_TTL_SECONDS,
            ),
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_TTL_SECONDS,
            user=UserResponse(
                id=str(user.id),
                email=user.email,
                role=user.role,
                consent_version=user.consent_version,
                created_at=user.created_at,
            ),
        )

    @staticmethod
    def _hash_otp(secret: str, email: str, code: str) -> str:
        return hmac.new(
            secret.encode("utf-8"),
            f"{email}:{code}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _secret() -> str:
        secret = settings.jwt_secret.get_secret_value()
        if len(secret.encode("utf-8")) < 32:
            raise AuthenticationNotConfigured
        return secret

    @staticmethod
    def _verify_google_token(token: str, client_id: str) -> dict[str, Any]:
        try:
            from google.auth.exceptions import GoogleAuthError, TransportError
            from google.auth.transport.requests import Request
            from google.oauth2 import id_token
        except ImportError as error:
            raise AuthenticationNotConfigured from error

        try:
            return id_token.verify_oauth2_token(
                token,
                Request(),
                audience=client_id,
            )
        except TransportError as error:
            raise GoogleVerificationUnavailable from error
        except GoogleAuthError as error:
            raise InvalidGoogleToken from error
        except ValueError as error:
            raise InvalidGoogleToken from error
