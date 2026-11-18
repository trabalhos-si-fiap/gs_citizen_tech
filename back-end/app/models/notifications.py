"""Dados usados por notificações e registro de dispositivos."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


@dataclass(frozen=True)
class AgencyAssignment:
    email: str
    agency_name: str
    report_id: UUID
    protocol: str
    category: str | None
    subcategory: str | None
    urgency: str | None
    description: str | None
    latitude: float
    longitude: float
    deadline: datetime | None
    photo_url: str | None


class RegisterDeviceRequest(BaseModel):
    push_token: str = Field(min_length=1, max_length=512)
    platform: Literal["android", "ios"]

    @field_validator("push_token")
    @classmethod
    def validate_push_token(cls, value: str) -> str:
        if value != value.strip() or any(
            ord(char) < 32 or ord(char) == 127 for char in value
        ):
            raise ValueError("Token de push inválido.")
        return value


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    data: dict[str, str]
