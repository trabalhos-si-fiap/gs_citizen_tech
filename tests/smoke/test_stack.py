"""Teste de fumaça ponta a ponta contra o stack em execução.

Pré-requisito: `docker compose up --build --wait` na raiz do repositório.
Executar:  python -m unittest discover -s tests/smoke -v

Fluxo: login por OTP (código lido no Mailpit) -> criação de reporte no Oracle
-> worker classifica o reporte (fila Oracle) -> painel web responde.
Usa apenas a biblioteca padrão, para rodar em qualquer máquina com Python 3.10+.
"""

import json
import os
import random
import re
import subprocess
import time
import unittest
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = os.environ.get("SMOKE_API_URL", "http://127.0.0.1:8000")
WEB = os.environ.get("SMOKE_WEB_URL", "http://127.0.0.1:4200")
MAILPIT = os.environ.get("SMOKE_MAILPIT_URL", "http://127.0.0.1:8025")


def request(method: str, url: str, body: dict | None = None, token: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None, response.headers
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = raw.decode(errors="replace")
        return error.code, payload, error.headers


def wait_for(condition, timeout: float, interval: float = 1.0):
    deadline = time.monotonic() + timeout
    while True:
        value = condition()
        if value or time.monotonic() > deadline:
            return value
        time.sleep(interval)


def otp_from_mailpit(email: str) -> str | None:
    status, result, _ = request("GET", f"{MAILPIT}/api/v1/search?query=to:{email}")
    if status != 200 or not result.get("messages"):
        return None
    message_id = result["messages"][0]["ID"]
    _, message, _ = request("GET", f"{MAILPIT}/api/v1/message/{message_id}")
    match = re.search(r"\b(\d{6})\b", message.get("Text", ""))
    return match.group(1) if match else None


class StackSmokeTests(unittest.TestCase):
    def test_api_health(self) -> None:
        status, body, headers = request("GET", f"{API}/health")

        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok"})
        self.assertNotIn("server", {key.lower() for key in headers.keys()})

    def test_web_serves_spa_with_security_headers(self) -> None:
        with urllib.request.urlopen(f"{WEB}/indicadores", timeout=10) as response:
            html = response.read().decode()
            headers = response.headers

        self.assertIn("<app-root>", html)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_citizen_flow_reaches_oracle_and_worker(self) -> None:
        email = f"smoke-{uuid.uuid4().hex[:10]}@example.com"
        consent = {"version": "2026-11", "accepted_age": True}

        status, _, _ = request(
            "POST", f"{API}/v1/auth/login", {"email": email, "consent": consent}
        )
        self.assertEqual(status, 202)

        code = wait_for(lambda: otp_from_mailpit(email), timeout=20)
        self.assertIsNotNone(code, "OTP não chegou ao Mailpit")

        status, session, _ = request(
            "POST", f"{API}/v1/auth/login", {"email": email, "code": code}
        )
        self.assertEqual(status, 200, session)
        token = session["access_token"]

        report_id = str(uuid.uuid4())
        # Ponto aleatório na região central, para não colidir com execuções anteriores.
        lat = round(-23.55 + random.uniform(-0.05, 0.05), 6)
        lon = round(-46.63 + random.uniform(-0.05, 0.05), 6)
        report = {
            "id": report_id,
            "description": "Árvore com galho quebrado sobre a calçada (teste)",
            "category": "risco_urbano",
            "lat": lat,
            "lon": lon,
            "client_created_at": datetime.now(timezone.utc).isoformat(),
        }
        status, created, _ = request("POST", f"{API}/v1/reports", report, token)
        self.assertEqual(status, 201, created)

        status, again, _ = request("POST", f"{API}/v1/reports", report, token)
        self.assertIn(status, {200, 201}, again)
        self.assertEqual(again["id"], created["id"], "reenvio deve ser idempotente")

        def classified():
            _, detail, _ = request("GET", f"{API}/v1/reports/{report_id}", token=token)
            return detail if detail and detail.get("classification") else None

        detail = wait_for(classified, timeout=30)
        self.assertIsNotNone(detail, "worker não classificou o reporte")

        # Mapa público: sem token, consulta o Oracle por proximidade.
        status, nearby, _ = request(
            "GET", f"{API}/v1/reports/nearby?lat={lat}&lon={lon}&radius_m=50"
        )
        self.assertEqual(status, 200, nearby)
        items = {item["id"]: item for item in nearby["items"]}
        self.assertIn(report_id, items)
        self.assertNotIn("description", items[report_id])
        self.assertLessEqual(items[report_id]["distance_m"], 10)


class ContainerRuntimeTests(unittest.TestCase):
    def test_built_containers_run_as_non_root(self) -> None:
        for service in ("api", "worker", "web"):
            with self.subTest(service=service):
                result = subprocess.run(
                    ["docker", "compose", "exec", "-T", service, "id", "-u"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertNotEqual(result.stdout.strip(), "0")

    def test_root_filesystem_is_read_only(self) -> None:
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "api", "touch", "/app/x"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
