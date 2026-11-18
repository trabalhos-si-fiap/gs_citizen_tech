"""Middlewares transversais da API."""

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import Request, Response

RequestHandler = Callable[[Request], Awaitable[Response]]


async def correlation_id_middleware(
    request: Request,
    call_next: RequestHandler,
) -> Response:
    supplied_id = request.headers.get("X-Correlation-ID")
    try:
        correlation_id = str(UUID(supplied_id)) if supplied_id else str(uuid4())
    except ValueError:
        correlation_id = str(uuid4())

    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response
