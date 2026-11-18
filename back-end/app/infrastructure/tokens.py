"""Criação e validação de JWTs HS256 da API."""

import base64
import binascii
import hashlib
import hmac
import json
import time
from typing import Any


def create_access_token(
    *,
    user_id: int,
    role: str,
    secret: str,
    expires_in: int,
    now: int | None = None,
) -> str:
    issued_at = int(time.time()) if now is None else now
    header = _encode_segment({"alg": "HS256", "typ": "JWT"})
    payload = _encode_segment(
        {
            "sub": str(user_id),
            "role": role,
            "iat": issued_at,
            "exp": issued_at + expires_in,
        }
    )
    signing_input = f"{header}.{payload}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_encode_bytes(signature)}"


def decode_access_token(
    token: str,
    secret: str,
    *,
    now: float | None = None,
) -> dict[str, Any] | None:
    try:
        header_part, payload_part, signature_part = token.split(".")
        header = _decode_segment(header_part)
        claims = _decode_segment(payload_part)
        provided_signature = _decode_bytes(signature_part)
        signed_content = f"{header_part}.{payload_part}".encode("ascii")
    except (ValueError, TypeError, UnicodeDecodeError, binascii.Error):
        return None

    if not isinstance(header, dict) or header.get("alg") != "HS256":
        return None
    if not isinstance(claims, dict):
        return None

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signed_content,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(provided_signature, expected_signature):
        return None

    expiration = claims.get("exp")
    current_time = time.time() if now is None else now
    if (
        isinstance(expiration, bool)
        or not isinstance(expiration, (int, float))
        or expiration <= current_time
    ):
        return None

    return claims


def _encode_segment(value: dict[str, object]) -> str:
    return _encode_bytes(
        json.dumps(value, separators=(",", ":")).encode("utf-8")
    )


def _encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_segment(segment: str) -> Any:
    return json.loads(_decode_bytes(segment))


def _decode_bytes(segment: str) -> bytes:
    padded_segment = segment + "=" * (-len(segment) % 4)
    return base64.b64decode(
        padded_segment,
        altchars=b"-_",
        validate=True,
    )
