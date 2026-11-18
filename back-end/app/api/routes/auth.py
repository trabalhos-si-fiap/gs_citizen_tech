"""Rotas de autenticação por e-mail."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.infrastructure.mailer import MailDeliveryError
from app.models.auth import (
    AuthTokensResponse,
    LoginRequest,
    OtpSentResponse,
    RefreshRequest,
)
from app.infrastructure.repositories import ConsentRequired, GoogleAccountConflict
from app.services.auth_service import (
    AuthenticationNotConfigured,
    AuthService,
    GoogleVerificationUnavailable,
    InvalidGoogleToken,
    InvalidOtp,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


@router.post(
    "/login",
    response_model=AuthTokensResponse | OtpSentResponse,
    responses={
        202: {
            "model": OtpSentResponse,
            "description": "Código OTP enviado por e-mail.",
        },
        400: {"description": "Consentimento ou confirmação de idade obrigatórios."},
        401: {"description": "OTP ou ID token inválido."},
        409: {"description": "Conta Google vinculada a outra identidade."},
        503: {"description": "Serviço de autenticação indisponível."},
    },
)
def login(
    payload: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokensResponse | OtpSentResponse:
    try:
        if payload.google_id_token:
            return service.login_google(
                payload.google_id_token,
                payload.consent,
            )

        email = str(payload.email)
        if payload.code is None:
            result = service.request_otp(email, payload.consent)
            response.status_code = 202
            return result
        return service.verify_otp(email, payload.code)
    except ConsentRequired as error:
        raise HTTPException(
            status_code=400,
            detail="Aceite os termos e confirme a idade para criar uma conta.",
        ) from error
    except GoogleAccountConflict as error:
        raise HTTPException(
            status_code=409,
            detail="Esta conta Google está vinculada a outro usuário.",
        ) from error
    except InvalidOtp as error:
        raise HTTPException(
            status_code=401,
            detail="Código inválido, expirado ou bloqueado.",
        ) from error
    except InvalidGoogleToken as error:
        raise HTTPException(
            status_code=401,
            detail="ID token Google inválido ou sem e-mail verificado.",
        ) from error
    except GoogleVerificationUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível validar o ID token Google.",
        ) from error
    except AuthenticationNotConfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Autenticação não está configurada.",
        ) from error
    except MailDeliveryError as error:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível enviar o código de acesso.",
        ) from error


@router.post("/refresh", response_model=AuthTokensResponse)
def refresh(
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokensResponse:
    try:
        return service.refresh(payload.refresh_token)
    except InvalidOtp as error:
        raise HTTPException(
            status_code=401,
            detail="Refresh token inválido, expirado ou já utilizado.",
        ) from error
    except AuthenticationNotConfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Autenticação não está configurada.",
        ) from error
