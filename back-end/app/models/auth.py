"""Modelos de autenticação usados pelas rotas e serviços."""

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


class ConsentRequest(BaseModel):
    version: str = Field(min_length=1, max_length=64)
    accepted_age: bool


class LoginRequest(BaseModel):
    email: EmailStr | None = None
    code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    google_id_token: str | None = Field(default=None, max_length=8192)
    consent: ConsentRequest | None = None

    @model_validator(mode="after")
    def validate_login_method(self) -> "LoginRequest":
        if self.google_id_token:
            if self.email is not None or self.code is not None:
                raise ValueError("Escolha apenas um método de autenticação.")
            return self
        if self.email is None:
            raise ValueError("Informe um e-mail ou um token Google.")
        return self


class OtpSentResponse(BaseModel):
    status: str = "otp_sent"
    expires_in: int = 600


class UserResponse(BaseModel):
    id: str
    email: EmailStr | None
    role: str
    consent_version: str | None = None
    created_at: datetime


class AuthTokensResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


@dataclass(frozen=True)
class AuthUser:
    id: int
    email: str
    role: str
    consent_version: str | None
    created_at: datetime
