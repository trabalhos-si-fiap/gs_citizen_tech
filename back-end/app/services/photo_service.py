"""Casos de uso de upload e processamento seguro de fotos."""

from collections.abc import AsyncIterable
from pathlib import Path
from uuid import UUID

from app.infrastructure.job_queue import JobQueue
from app.infrastructure.photo_storage import LocalPhotoStorage
from app.infrastructure.repositories import ReportRepository


class PhotoService:
    def __init__(
        self,
        repository: ReportRepository,
        storage: LocalPhotoStorage,
        queue: JobQueue,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._queue = queue

    async def upload(
        self,
        token: str,
        content: AsyncIterable[bytes],
    ) -> UUID:
        return await self._storage.receive_upload(token, content)

    def complete(
        self,
        report_id: UUID,
        user_id: int,
        sha256: str,
    ) -> None:
        self._repository.assert_photo_owner(report_id, user_id, sha256)
        self._storage.register_completion(report_id, sha256)
        self._queue.enqueue(report_id, "process_photo")

    def read_url(self, report_id: UUID) -> str | None:
        photo_key = self._repository.get_photo_key(report_id)
        if photo_key is None:
            return None
        return self._storage.create_read_url(photo_key)

    def read(self, token: str) -> Path:
        return self._storage.read_path(token)
