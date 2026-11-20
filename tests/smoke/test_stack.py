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
from datetime import datetime, timedelta, timezone
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
        self.assertEqual(detail["triage_state"], "awaiting_user")

        # Mapa público: sem token, consulta o Oracle por proximidade.
        status, nearby, _ = request(
            "GET", f"{API}/v1/reports/nearby?lat={lat}&lon={lon}&radius_m=50"
        )
        self.assertEqual(status, 200, nearby)
        items = {item["id"]: item for item in nearby["items"]}
        self.assertIn(report_id, items)
        self.assertNotIn("description", items[report_id])
        self.assertLessEqual(items[report_id]["distance_m"], 10)


# Roda a varredura de triagem no worker com o relógio adiantado, sem esperar
# os 10 minutos reais de TRIAGE_AUTO_CONFIRM_MINUTES.
SWEEP_WITH_CLOCK_AHEAD = """
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from app.infrastructure.database import OracleDatabase
from app.infrastructure.repositories import OracleReportRepository
from app.services.report_service import ReportService
database = OracleDatabase(settings)
database.open()
ahead = datetime.now(timezone.utc) + timedelta(minutes=settings.triage_auto_confirm_minutes + 1)
service = ReportService(OracleReportRepository(database), None, clock=lambda: ahead)
print(service.auto_confirm_due_triage(limit=500))
database.close()
"""


class TriageAutoConfirmSmokeTests(unittest.TestCase):
    def test_pending_triage_is_auto_confirmed_and_forwarded(self) -> None:
        email = f"smoke-{uuid.uuid4().hex[:10]}@example.com"
        request("POST", f"{API}/v1/auth/login",
                {"email": email, "consent": {"version": "2026-11", "accepted_age": True}})
        code = wait_for(lambda: otp_from_mailpit(email), timeout=20)
        _, session, _ = request("POST", f"{API}/v1/auth/login", {"email": email, "code": code})
        token = session["access_token"]
        report_id = str(uuid.uuid4())
        status, created, _ = request("POST", f"{API}/v1/reports", {
            "id": report_id,
            "description": "Semáforo apagado no cruzamento (teste)",
            "category": "risco_urbano",
            "lat": round(-23.55 + random.uniform(-0.05, 0.05), 6),
            "lon": round(-46.63 + random.uniform(-0.05, 0.05), 6),
            "client_created_at": datetime.now(timezone.utc).isoformat(),
        }, token)
        self.assertEqual(status, 201, created)
        wait_for(
            lambda: request("GET", f"{API}/v1/reports/{report_id}", token=token)[1]
            .get("triage_state") == "awaiting_user",
            timeout=30,
        )

        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "worker", "python", "-c",
             SWEEP_WITH_CLOCK_AHEAD],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

        _, detail, _ = request("GET", f"{API}/v1/reports/{report_id}", token=token)
        self.assertEqual(detail["triage_state"], "auto_confirmed")
        self.assertEqual(detail["status"], "encaminhado")
        actors = {(event["type"], event["actor"]) for event in detail["timeline"]}
        self.assertIn(("classificacao_confirmada", "system"), actors)



def citizen_token() -> str:
    email = f"smoke-{uuid.uuid4().hex[:10]}@example.com"
    request("POST", f"{API}/v1/auth/login",
            {"email": email, "consent": {"version": "2026-11", "accepted_age": True}})
    code = wait_for(lambda: otp_from_mailpit(email), timeout=20)
    _, session, _ = request("POST", f"{API}/v1/auth/login", {"email": email, "code": code})
    return session["access_token"]


def create_report(token: str, lat: float, lon: float, description: str) -> str:
    report_id = str(uuid.uuid4())
    status, body, _ = request("POST", f"{API}/v1/reports", {
        "id": report_id,
        "description": description,
        "category": "risco_urbano",
        "lat": lat,
        "lon": lon,
        "client_created_at": datetime.now(timezone.utc).isoformat(),
    }, token)
    assert status == 201, body
    return report_id


def wait_triage_settled(report_id: str, token: str) -> dict:
    def settled():
        _, detail, _ = request("GET", f"{API}/v1/reports/{report_id}", token=token)
        return detail if detail.get("triage_state") != "pending_classification" else None
    return wait_for(settled, timeout=30)


class ReportUpdatesSmokeTests(unittest.TestCase):
    def test_another_citizen_can_flag_a_report(self) -> None:
        owner, other = citizen_token(), citizen_token()
        report_id = create_report(
            owner, -23.6 + random.uniform(-0.05, 0.05), -46.7, "Pichação ofensiva (teste)"
        )

        status, body, _ = request(
            "POST", f"{API}/v1/reports/{report_id}/flag", {"reason": "ofensivo"}, other
        )

        self.assertEqual(status, 202, body)

    def test_similar_report_nearby_joins_existing_group(self) -> None:
        lat = round(-23.55 + random.uniform(-0.05, 0.05), 6)
        lon = round(-46.63 + random.uniform(-0.05, 0.05), 6)
        text = f"Bueiro entupido alagando a rua {uuid.uuid4().hex[:6]} (teste)"
        first_token, second_token = citizen_token(), citizen_token()
        first = create_report(first_token, lat, lon, text)
        wait_triage_settled(first, first_token)

        second = create_report(second_token, lat + 0.0001, lon, text)
        detail = wait_triage_settled(second, second_token)

        _, original, _ = request("GET", f"{API}/v1/reports/{first}", token=first_token)
        self.assertEqual(detail["group_id"], original["group_id"])
        self.assertEqual(detail["triage_state"], "auto_confirmed")
        self.assertIn("vinculado_grupo", [event["type"] for event in detail["timeline"]])
        _, nearby, _ = request(
            "GET", f"{API}/v1/reports/nearby?lat={lat}&lon={lon}&radius_m=50"
        )
        groups = [item["group_id"] for item in nearby["items"]]
        self.assertEqual(groups.count(original["group_id"]), 1)


    def test_group_member_follows_agency_status_of_canonical(self) -> None:
        lat = round(-23.55 + random.uniform(-0.05, 0.05), 6)
        lon = round(-46.63 + random.uniform(-0.05, 0.05), 6)
        text = f"Calçada afundada perto do ponto {uuid.uuid4().hex[:6]} (teste)"
        owner_token, member_token = citizen_token(), citizen_token()
        canonical = create_report(owner_token, lat, lon, text)
        wait_triage_settled(canonical, owner_token)
        member = create_report(member_token, lat, lon + 0.0001, text)
        wait_triage_settled(member, member_token)
        status, body, _ = request(
            "POST", f"{API}/v1/reports/{canonical}/triage", {"action": "confirm"}, owner_token
        )
        self.assertEqual(status, 200, body)
        api_key = (ROOT / "secrets" / "agency_api_keys.txt").read_text().split(",")[0].strip()

        req = urllib.request.Request(
            f"{API}/v1/agency/reports/{canonical}/status",
            data=json.dumps({
                "action": "in_progress",
                "deadline": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            }).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            self.assertEqual(response.status, 200)

        _, detail, _ = request("GET", f"{API}/v1/reports/{member}", token=member_token)
        self.assertEqual(detail["status"], "em_andamento")
        self.assertIsNotNone(detail["agency"])


def agency_status(report_id: str, payload: dict) -> int:
    api_key = (ROOT / "secrets" / "agency_api_keys.txt").read_text().split(",")[0].strip()
    req = urllib.request.Request(
        f"{API}/v1/agency/reports/{report_id}/status",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status


def resolved_report() -> str:
    """Cria um reporte e o resolve pelo órgão (a média de resposta precisa dele)."""
    token = citizen_token()
    lat = round(-23.55 + random.uniform(-0.05, 0.05), 6)
    lon = round(-46.63 + random.uniform(-0.05, 0.05), 6)
    report_id = create_report(
        token, lat, lon, f"Poste apagado na esquina {uuid.uuid4().hex[:6]} (teste)"
    )
    detail = wait_triage_settled(report_id, token)
    if detail.get("triage_state") == "awaiting_user":
        request("POST", f"{API}/v1/reports/{report_id}/triage", {"action": "confirm"}, token)
    deadline = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    assert agency_status(report_id, {"action": "in_progress", "deadline": deadline}) == 200
    assert agency_status(
        report_id, {"action": "resolved", "justification": "Lâmpada trocada (teste)."}
    ) == 200
    return report_id


class PublicMetricsSmokeTests(unittest.TestCase):
    """Indicadores públicos com reportes resolvidos no Oracle (tela e CSV do painel)."""

    @classmethod
    def setUpClass(cls) -> None:
        resolved_report()

    def test_public_metrics_report_average_response_in_hours(self) -> None:
        status, body, _ = request("GET", f"{API}/v1/public/metrics")

        self.assertEqual(status, 200, body)
        self.assertIsInstance(body["totals"]["avg_response_hours"], (int, float))
        self.assertGreaterEqual(body["totals"]["avg_response_hours"], 0)

    def test_public_metrics_export_csv(self) -> None:
        req = urllib.request.Request(f"{API}/v1/public/metrics?format=csv")
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            status, content_type = error.code, error.headers.get("Content-Type", "")

        self.assertEqual(status, 200)
        self.assertIn("text/csv", content_type)


UTC_SUFFIX = re.compile(r"(Z|\+00:00)$")


class ReportAddressSmokeTests(unittest.TestCase):
    """Endereço textual (V011 + PKG_REPORTES) e datas com fuso vindos do Oracle."""

    def test_address_round_trips_and_dates_carry_utc_offset(self) -> None:
        token = citizen_token()
        report_id = str(uuid.uuid4())
        lat = round(-23.55 + random.uniform(-0.05, 0.05), 6)
        lon = round(-46.63 + random.uniform(-0.05, 0.05), 6)
        status, created, _ = request("POST", f"{API}/v1/reports", {
            "id": report_id,
            "description": f"Calçada quebrada {uuid.uuid4().hex[:6]} (teste)",
            "category": "risco_urbano",
            "lat": lat,
            "lon": lon,
            "client_created_at": datetime.now(timezone.utc).isoformat(),
            "address": "  Rua Exemplo, 123 – Bairro, Cidade  ",
        }, token)
        self.assertEqual(status, 201, created)
        self.assertRegex(created["received_at"], UTC_SUFFIX)

        _, detail, _ = request("GET", f"{API}/v1/reports/{report_id}", token=token)
        self.assertEqual(detail["address"], "Rua Exemplo, 123 – Bairro, Cidade")
        self.assertRegex(detail["received_at"], UTC_SUFFIX)
        for event in detail["timeline"]:
            self.assertRegex(event["created_at"], UTC_SUFFIX)

        _, mine, _ = request("GET", f"{API}/v1/me/reports", token=token)
        item = next(entry for entry in mine["items"] if entry["id"] == report_id)
        self.assertEqual(item["address"], "Rua Exemplo, 123 – Bairro, Cidade")
        self.assertTrue(item["description"].startswith("Calçada quebrada"))
        self.assertIn("subcategory", item)
        self.assertRegex(item["received_at"], UTC_SUFFIX)

        # Mapa público: endereço fica fora da superfície sem autenticação.
        _, nearby, _ = request(
            "GET", f"{API}/v1/reports/nearby?lat={lat}&lon={lon}&radius_m=50"
        )
        public = next(entry for entry in nearby["items"] if entry["id"] == report_id)
        self.assertNotIn("address", public)

    def test_report_without_address_is_accepted_with_null(self) -> None:
        token = citizen_token()
        report_id = create_report(
            token,
            round(-23.55 + random.uniform(-0.05, 0.05), 6),
            round(-46.63 + random.uniform(-0.05, 0.05), 6),
            f"Sem endereço {uuid.uuid4().hex[:6]} (teste)",
        )

        _, detail, _ = request("GET", f"{API}/v1/reports/{report_id}", token=token)

        self.assertIn("address", detail)
        self.assertIsNone(detail["address"])


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
