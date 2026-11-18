import hashlib
import io
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image

from app.infrastructure.photo_storage import (
    InvalidPhoto,
    LocalPhotoStorage,
    PhotoUploadConflict,
    PhotoUploadExpired,
    PhotoUploadTooLarge,
)

NOW = datetime(2026, 11, 17, tzinfo=timezone.utc)


class PhotoStorageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = LocalPhotoStorage(
            storage_dir=Path(self.temp_dir.name),
            base_url="http://localhost:8000",
            secret="photo-upload-test-secret-with-at-least-32-bytes",
            max_bytes=1_000_000,
            clock=lambda: NOW,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def jpeg_with_exif() -> bytes:
        image = Image.new("RGB", (32, 24), color="blue")
        exif = Image.Exif()
        exif[0x010E] = "private metadata"
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", exif=exif)
        return buffer.getvalue()

    @staticmethod
    async def chunks(data: bytes):
        yield data[:17]
        yield data[17:]

    async def test_signed_upload_is_recoded_without_exif(self) -> None:
        report_id = uuid4()
        data = self.jpeg_with_exif()
        instruction = self.storage.create_upload_instruction(
            report_id,
            max_bytes=1_000_000,
            expires_in=timedelta(minutes=10),
        )
        token = instruction.url.rsplit("/", 1)[1]

        await self.storage.receive_upload(token, self.chunks(data))
        self.storage.register_completion(report_id, hashlib.sha256(data).hexdigest())
        key = self.storage.process_upload(report_id)

        output_path = Path(self.temp_dir.name) / key
        with Image.open(output_path) as processed:
            self.assertEqual(processed.format, "JPEG")
            self.assertEqual(dict(processed.getexif()), {})
        read_url = self.storage.create_read_url(key)
        read_token = read_url.rsplit("/", 1)[1]
        self.assertEqual(self.storage.read_path(read_token), output_path)
        self.storage.discard_upload(report_id)
        self.assertFalse(
            (Path(self.temp_dir.name) / "staging" / f"{report_id}.upload").exists()
        )

    async def test_upload_token_rejects_tampering_and_expiration(self) -> None:
        instruction = self.storage.create_upload_instruction(
            uuid4(),
            max_bytes=1_000_000,
            expires_in=timedelta(minutes=10),
        )
        token = instruction.url.rsplit("/", 1)[1]

        with self.assertRaises(PhotoUploadExpired):
            await self.storage.receive_upload(token + "x", self.chunks(b"data"))

        expired_storage = LocalPhotoStorage(
            storage_dir=Path(self.temp_dir.name),
            secret="photo-upload-test-secret-with-at-least-32-bytes",
            max_bytes=1_000_000,
            clock=lambda: NOW + timedelta(minutes=11),
        )
        with self.assertRaises(PhotoUploadExpired):
            await expired_storage.receive_upload(token, self.chunks(b"data"))

    async def test_oversized_and_non_image_uploads_are_rejected(self) -> None:
        report_id = uuid4()
        limited_storage = LocalPhotoStorage(
            storage_dir=Path(self.temp_dir.name),
            secret="photo-upload-test-secret-with-at-least-32-bytes",
            max_bytes=8,
            clock=lambda: NOW,
        )
        instruction = limited_storage.create_upload_instruction(
            report_id,
            max_bytes=8,
            expires_in=timedelta(minutes=10),
        )
        token = instruction.url.rsplit("/", 1)[1]

        with self.assertRaises(PhotoUploadTooLarge):
            await limited_storage.receive_upload(token, self.chunks(b"x" * 9))

        report_id = uuid4()
        instruction = self.storage.create_upload_instruction(
            report_id,
            max_bytes=1_000_000,
            expires_in=timedelta(minutes=10),
        )
        await self.storage.receive_upload(
            instruction.url.rsplit("/", 1)[1],
            self.chunks(b"not an image"),
        )
        with self.assertRaises(InvalidPhoto):
            self.storage.register_completion(
                report_id,
                hashlib.sha256(b"not an image").hexdigest(),
            )

    async def test_upload_url_cannot_be_reused(self) -> None:
        report_id = uuid4()
        instruction = self.storage.create_upload_instruction(
            report_id,
            max_bytes=1_000_000,
            expires_in=timedelta(minutes=10),
        )
        token = instruction.url.rsplit("/", 1)[1]
        await self.storage.receive_upload(token, self.chunks(b"first"))

        with self.assertRaises(PhotoUploadConflict):
            await self.storage.receive_upload(token, self.chunks(b"second"))
