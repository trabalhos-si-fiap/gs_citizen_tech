"""Rotas públicas autorizadas por URL de upload assinada."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse

from app.infrastructure.photo_storage import (
    InvalidPhoto,
    PhotoUploadConflict,
    PhotoUploadExpired,
    PhotoUploadNotFound,
    PhotoUploadTooLarge,
)
from app.infrastructure.repositories import PhotoStorageUnavailable
from app.services.photo_service import PhotoService

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])
photos_router = APIRouter(prefix="/v1/photos", tags=["uploads"])


def get_photo_service(request: Request) -> PhotoService:
    return request.app.state.photo_service


@router.put("/{token}", status_code=204)
async def upload_photo(
    token: str,
    request: Request,
    service: PhotoService = Depends(get_photo_service),
) -> Response:
    try:
        await service.upload(token, request.stream())
    except PhotoUploadExpired as error:
        raise HTTPException(
            status_code=410,
            detail="A URL de upload expirou ou é inválida.",
        ) from error
    except PhotoUploadTooLarge as error:
        raise HTTPException(
            status_code=413,
            detail="A foto excede o tamanho permitido.",
        ) from error
    except PhotoUploadConflict as error:
        raise HTTPException(
            status_code=409,
            detail="Já existe um arquivo enviado para este reporte.",
        ) from error
    except InvalidPhoto as error:
        raise HTTPException(
            status_code=422,
            detail="O arquivo enviado está vazio ou é inválido.",
        ) from error
    except PhotoStorageUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="O armazenamento de fotos não está configurado.",
        ) from error
    return Response(status_code=204)


@photos_router.get("/{token}")
def read_photo(
    token: str,
    service: PhotoService = Depends(get_photo_service),
) -> FileResponse:
    try:
        photo_path = service.read(token)
    except PhotoUploadExpired as error:
        raise HTTPException(
            status_code=410,
            detail="A URL de leitura expirou ou é inválida.",
        ) from error
    except PhotoUploadNotFound as error:
        raise HTTPException(
            status_code=404,
            detail="Foto não encontrada.",
        ) from error
    except PhotoStorageUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="O armazenamento de fotos não está configurado.",
        ) from error
    return FileResponse(
        photo_path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )
