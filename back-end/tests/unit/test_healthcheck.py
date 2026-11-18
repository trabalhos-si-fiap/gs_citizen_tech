import os
import socket
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from uuid import uuid4

from app.healthcheck import check_heartbeat, check_http
from app.infrastructure.classifiers import FakeClassifier
from app.infrastructure.job_queue import InMemoryJobQueue
from app.infrastructure.repositories import InMemoryReportRepository
from app.infrastructure.worker import ReportJobWorker
from app.services.classification_service import ClassificationService


class HeartbeatTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "heartbeat"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_heartbeat_is_unhealthy(self) -> None:
        self.assertFalse(check_heartbeat(self.path, max_age_seconds=30))

    def test_recent_heartbeat_is_healthy(self) -> None:
        self.path.touch()

        self.assertTrue(check_heartbeat(self.path, max_age_seconds=30))

    def test_stale_heartbeat_is_unhealthy(self) -> None:
        self.path.touch()
        old = time.time() - 120
        os.utime(self.path, (old, old))

        self.assertFalse(check_heartbeat(self.path, max_age_seconds=30))

    def test_worker_poll_cycle_refreshes_heartbeat(self) -> None:
        worker = ReportJobWorker(
            InMemoryJobQueue(),
            InMemoryReportRepository(),
            ClassificationService(FakeClassifier()),
            worker_id=f"test-{uuid4()}",
            heartbeat_path=self.path,
        )

        worker.run_once()

        self.assertTrue(check_heartbeat(self.path, max_age_seconds=5))


class _OkHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        status = 200 if self.path == "/health" else 503
        self.send_response(status)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *_: object) -> None:
        return None


class HttpCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), _OkHandler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_200_response_is_healthy(self) -> None:
        self.assertTrue(check_http(f"http://127.0.0.1:{self.port}/health"))

    def test_error_status_is_unhealthy(self) -> None:
        self.assertFalse(check_http(f"http://127.0.0.1:{self.port}/other"))

    def test_unreachable_server_is_unhealthy(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            free_port = sock.getsockname()[1]

        self.assertFalse(check_http(f"http://127.0.0.1:{free_port}/health", 1))


if __name__ == "__main__":
    unittest.main()
