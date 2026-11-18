"""Validação de tokens de acesso para rotas protegidas."""

import hmac

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.infrastructure.tokens import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def require_agency_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    valid_keys = {
        key.strip()
        for key in settings.agency_api_keys.split(",")
        if key.strip()
    }
    if not valid_keys or x_api_key is None or not any(
        hmac.compare_digest(x_api_key, key) for key in valid_keys
    ):
        raise HTTPException(status_code=403, detail="Chave de API do órgão inválida.")


def require_moderator(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> int:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    claims = decode_access_token(
        credentials.credentials,
        settings.jwt_secret.get_secret_value(),
    )
    if claims is None:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")
    if claims.get("role") not in {"moderator", "admin"}:
        raise HTTPException(status_code=403, detail="Ação permitida somente a moderadores.")
    try:
        return int(claims["sub"])
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=401, detail="Token inválido.") from error


def require_citizen(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> int:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = settings.jwt_secret.get_secret_value()
    if len(secret.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=503,
            detail="Autenticação não está configurada.",
        )

    if len(credentials.credentials) > 8192:
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_access_token(credentials.credentials, secret)
    if claims is None:
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if claims.get("role") != "citizen":
        raise HTTPException(
            status_code=403,
            detail="Ação permitida somente para cidadãos.",
        )

    try:
        user_id = int(claims["sub"])
        if user_id < 1:
            raise ValueError
        return user_id
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
