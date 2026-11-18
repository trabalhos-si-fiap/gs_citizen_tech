"""Tratamento padronizado de erros HTTP da API."""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

HTTP_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    410: "gone",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
    501: "not_implemented",
}


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "correlation_id": getattr(request.state, "correlation_id", None),
    }
    if field is not None:
        error["field"] = field

    return JSONResponse(
        status_code=status_code,
        content={"error": error},
    )


async def validation_error_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    field = None
    for validation_error in exception.errors():
        location = validation_error.get("loc", ())
        if location and location[0] in {"body", "path", "query", "header"}:
            field = str(location[-1])
            break

    return _error_response(
        request,
        status_code=422,
        code="validation_error",
        message="A requisição contém dados inválidos.",
        field=field,
    )


async def http_error_handler(
    request: Request,
    exception: StarletteHTTPException,
) -> JSONResponse:
    status_code = exception.status_code
    message = (
        exception.detail
        if isinstance(exception.detail, str)
        else "Não foi possível processar a requisição."
    )
    response = _error_response(
        request,
        status_code=status_code,
        code=HTTP_ERROR_CODES.get(status_code, "http_error"),
        message=message,
    )
    if exception.headers:
        response.headers.update(exception.headers)
    return response
