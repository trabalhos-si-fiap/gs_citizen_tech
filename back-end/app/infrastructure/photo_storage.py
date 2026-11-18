"""Armazenamento local e sanitização de fotos enviadas por URL assinada."""

import base64
import hashlib
import hmac
import json
import os
import re
import warnings
from collections.abc import AsyncIterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.models.reports import UploadInstruction
from app.infrastructure.repositories import PhotoStorageUnavailable

MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_SIDE = 8_000
MAX_OUTPUT_SIDE = 2_048
MAX_UPLOAD_BYTES = 5_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class InvalidPhoto(Exception):
    """O arquivo recebido não é uma imagem válida ou permitida."""


class PhotoUploadExpired(Exception):
    """A URL assinada expirou ou não é válida."""


class PhotoUploadConflict(Exception):
    """Já existe um upload ou processamento para este reporte."""


class PhotoUploadTooLarge(Exception):
    """O arquivo ultrapassa o limite permitido."""


class PhotoUploadNotFound(Exception):
    """Não existe upload pendente para o reporte."""


class Redactor(Protocol):
    def blur(self, image: Image.Image) -> Image.Image: ...


class NoOpRedactor:
    """Desfoque facial/placas ainda não disponível no MVP."""

    def blur(self, image: Image.Image) -> Image.Image:
        return image


class LocalPhotoStorage:
    def __init__(
        self,
        *,
        storage_dir: Path | None = None,
        base_url: str | None = None,
        secret: str | None = None,
        max_bytes: int | None = None,
        redactor: Redactor | None = None,
        clock=lambda: datetime.now(timezone.utc),
    ) -> None:
        self._root = storage_dir or settings.photo_storage_dir
        self._base_url = (base_url or settings.public_api_base_url).rstrip("/")
        self._secret = (
            secret
            if secret is not None
            else settings.photo_upload_secret.get_secret_value()
        )
        self._max_bytes = settings.photo_max_bytes if max_bytes is None else max_bytes
        self._redactor = redactor or NoOpRedactor()
        self._clock = clock

    def create_upload_instruction(
        self,
        report_id: UUID,
        *,
        max_bytes: int,
        expires_in: timedelta,
    ) -> UploadInstruction:
        self._validate_configuration()
        if max_bytes < 1 or max_bytes > self._max_bytes:
            raise PhotoStorageUnavailable
        expires_at = self._clock() + expires_in
        token = self._make_token(report_id, max_bytes, int(expires_at.timestamp()))
        return UploadInstruction(
            url=f"{self._base_url}/v1/uploads/{token}",
            method="PUT",
            headers={"Content-Type": "application/octet-stream"},
            max_bytes=max_bytes,
            expires_at=expires_at,
        )

    async def receive_upload(
        self,
        token: str,
        content: AsyncIterable[bytes],
    ) -> UUID:
        report_id, max_bytes = self._read_token(token)
        staging_path = self._staging_path(report_id)
        staging_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

        try:
            file_descriptor = os.open(
                staging_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            with os.fdopen(file_descriptor, "wb") as destination:
                written = 0
                async for chunk in content:
                    written += len(chunk)
                    if written > max_bytes:
                        raise PhotoUploadTooLarge
                    destination.write(chunk)
                if written == 0:
                    raise InvalidPhoto
        except FileExistsError as error:
            raise PhotoUploadConflict from error
        except BaseException:
            staging_path.unlink(missing_ok=True)
            raise

        return report_id

    def register_completion(self, report_id: UUID, expected_sha256: str) -> None:
        if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
            raise InvalidPhoto
        staging_path = self._staging_path(report_id)
        if not staging_path.is_file():
            completed_path = (
                self._root / "objects" / f"{expected_sha256.lower()}.jpg"
            )
            if completed_path.is_file():
                return
            raise PhotoUploadNotFound

        actual_sha256 = self._file_sha256(staging_path)
        normalized_sha256 = expected_sha256.lower()
        if not hmac.compare_digest(actual_sha256, normalized_sha256):
            raise InvalidPhoto

        try:
            self._validate_image(staging_path)
        except InvalidPhoto:
            staging_path.unlink(missing_ok=True)
            raise
        completion_path = self._completion_path(report_id)
        try:
            with completion_path.open("x", encoding="ascii") as completion:
                completion.write(normalized_sha256)
            os.chmod(completion_path, 0o600)
        except FileExistsError:
            if completion_path.read_text(encoding="ascii") != normalized_sha256:
                raise PhotoUploadConflict

    def process_upload(self, report_id: UUID) -> str:
        staging_path = self._staging_path(report_id)
        completion_path = self._completion_path(report_id)
        if not staging_path.is_file() or not completion_path.is_file():
            raise PhotoUploadNotFound

        expected_sha256 = completion_path.read_text(encoding="ascii")
        if not hmac.compare_digest(
            self._file_sha256(staging_path),
            expected_sha256,
        ):
            raise InvalidPhoto

        output_key = f"objects/{expected_sha256}.jpg"
        output_path = self._root / output_key
        output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not output_path.exists():
            self._sanitize(staging_path, output_path)
        return output_key

    def create_read_url(self, photo_key: str) -> str:
        self._validate_configuration()
        if not re.fullmatch(r"objects/[a-f0-9]{64}\.jpg", photo_key):
            raise ValueError("Chave de foto inválida.")
        payload = json.dumps(
            {
                "key": photo_key,
                "expires_at": int(
                    (self._clock() + timedelta(minutes=15)).timestamp()
                ),
                "purpose": "read",
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        encoded_payload = self._encode(payload)
        signature = hmac.new(
            self._secret.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        token = f"{encoded_payload}.{self._encode(signature)}"
        return f"{self._base_url}/v1/photos/{token}"

    def read_path(self, token: str) -> Path:
        self._validate_configuration()
        try:
            if len(token) > 2048:
                raise ValueError
            encoded_payload, encoded_signature = token.split(".", 1)
            provided_signature = self._decode(encoded_signature)
            expected_signature = hmac.new(
                self._secret.encode("utf-8"),
                encoded_payload.encode("ascii"),
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(provided_signature, expected_signature):
                raise ValueError
            payload = json.loads(self._decode(encoded_payload))
            key = payload["key"]
            if (
                payload["purpose"] != "read"
                or int(payload["expires_at"]) <= int(self._clock().timestamp())
                or not isinstance(key, str)
                or not re.fullmatch(r"objects/[a-f0-9]{64}\.jpg", key)
            ):
                raise ValueError
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise PhotoUploadExpired from error

        path = self._root / key
        if not path.is_file():
            raise PhotoUploadNotFound
        return path

    def discard_upload(self, report_id: UUID) -> None:
        self._staging_path(report_id).unlink(missing_ok=True)
        self._completion_path(report_id).unlink(missing_ok=True)

    def _sanitize(self, source_path: Path, output_path: Path) -> None:
        temporary_path = output_path.with_name(
            f".{output_path.name}.{uuid4().hex}.tmp"
        )
        images: list[Image.Image] = []
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(source_path) as source:
                    if source.format not in ALLOWED_IMAGE_FORMATS:
                        raise InvalidPhoto
                    if (
                        source.width > MAX_IMAGE_SIDE
                        or source.height > MAX_IMAGE_SIDE
                        or source.width * source.height > MAX_IMAGE_PIXELS
                    ):
                        raise InvalidPhoto
                    source.load()
                    oriented = ImageOps.exif_transpose(source)
                    oriented.thumbnail((MAX_OUTPUT_SIDE, MAX_OUTPUT_SIDE))
                    rgb_image = oriented.convert("RGB")
                    images.append(rgb_image)

            clean_image = Image.new("RGB", rgb_image.size, (255, 255, 255))
            images.append(clean_image)
            clean_image.paste(rgb_image)
            redacted_image = self._redactor.blur(clean_image)
            if redacted_image is not clean_image:
                images.append(redacted_image)
            image = redacted_image

            while True:
                for quality in (85, 75, 65, 55):
                    image.save(
                        temporary_path,
                        format="JPEG",
                        quality=quality,
                        optimize=True,
                    )
                    os.chmod(temporary_path, 0o600)
                    if temporary_path.stat().st_size <= self._max_bytes:
                        os.replace(temporary_path, output_path)
                        return
                if max(image.size) <= 256:
                    raise InvalidPhoto
                new_size = tuple(max(1, int(side * 0.8)) for side in image.size)
                resized = image.resize(new_size, Image.Resampling.LANCZOS)
                images.append(resized)
                image = resized
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
        ) as error:
            raise InvalidPhoto from error
        finally:
            for image in images:
                image.close()
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _validate_image(source_path: Path) -> None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(source_path) as source:
                    if (
                        source.format not in ALLOWED_IMAGE_FORMATS
                        or source.width > MAX_IMAGE_SIDE
                        or source.height > MAX_IMAGE_SIDE
                        or source.width * source.height > MAX_IMAGE_PIXELS
                    ):
                        raise InvalidPhoto
                    source.load()
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
        ) as error:
            raise InvalidPhoto from error

    def _make_token(self, report_id: UUID, max_bytes: int, expires_at: int) -> str:
        payload = json.dumps(
            {
                "report_id": str(report_id),
                "max_bytes": max_bytes,
                "expires_at": expires_at,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        encoded_payload = self._encode(payload)
        signature = hmac.new(
            self._secret.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return f"{encoded_payload}.{self._encode(signature)}"

    def _read_token(self, token: str) -> tuple[UUID, int]:
        self._validate_configuration()
        try:
            if len(token) > 2048:
                raise ValueError
            encoded_payload, encoded_signature = token.split(".", 1)
            provided_signature = self._decode(encoded_signature)
            expected_signature = hmac.new(
                self._secret.encode("utf-8"),
                encoded_payload.encode("ascii"),
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(provided_signature, expected_signature):
                raise ValueError
            payload = json.loads(self._decode(encoded_payload))
            report_id = UUID(payload["report_id"])
            max_bytes = int(payload["max_bytes"])
            expires_at = int(payload["expires_at"])
            if (
                max_bytes < 1
                or max_bytes > self._max_bytes
                or expires_at <= int(self._clock().timestamp())
            ):
                raise ValueError
            return report_id, max_bytes
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise PhotoUploadExpired from error

    def _validate_configuration(self) -> None:
        url = urlsplit(self._base_url)
        if (
            len(self._secret.encode("utf-8")) < 32
            or self._max_bytes < 1
            or self._max_bytes > MAX_UPLOAD_BYTES
            or url.scheme not in {"http", "https"}
            or not url.netloc
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or (
                settings.environment != "development"
                and url.scheme != "https"
            )
        ):
            raise PhotoStorageUnavailable

    def _staging_path(self, report_id: UUID) -> Path:
        return self._root / "staging" / f"{report_id}.upload"

    def _completion_path(self, report_id: UUID) -> Path:
        return self._root / "staging" / f"{report_id}.sha256"

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
