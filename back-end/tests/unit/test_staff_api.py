import base64
import hashlib
import hmac
import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import settings
from app.main import app
from app.models.classification import ClassificationResult, TriageRequest
from app.models.reports import NewReport, ReportStatus
from app.models.taxonomy import ReportCategory
from app.services.staff_service import provision_dev_staff

JWT_SECRET = "staff-test-secret-that-is-at-least-32-bytes"
ZELADORIA = "prefeitura-demo-zeladoria"
SANEAMENTO = "saneamento-demo"


def access_token(user_id: int, role: str) -> str:
    def segment(value: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(value, separators=(",", ":")).encode("utf-8")
        ).rstrip(b"=").decode("ascii")

    header = segment({"alg": "HS256", "typ": "JWT"})
    payload = segment(
        {"sub": str(user_id), "role": role, "exp": int(time.time()) + 60}
    )
    signing_input = f"{header}.{payload}"
    signature = hmac.new(
        JWT_SECRET.encode("ascii"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    )
    encoded = base64.urlsafe_b64encode(signature.digest()).rstrip(b"=")
    return f"{signing_input}.{encoded.decode('ascii')}"


class StaffApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.previous_secret = settings.jwt_secret
        settings.jwt_secret = SecretStr(JWT_SECRET)
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )
        self.reports = app.state.report_service._repository
        self.auth = app.state.staff_service._auth
        tag = uuid4().hex[:8]
        self.zeladoria = self.auth.provision_staff(
            f"zeladoria-{tag}@prefeitura.test", "agency", ZELADORIA
        )
        self.saneamento = self.auth.provision_staff(
            f"saneamento-{tag}@prefeitura.test", "agency", SANEAMENTO
        )
        self.manager = self.auth.provision_staff(
            f"gestor-{tag}@prefeitura.test", "manager"
        )
        self.moderator = self.auth.provision_staff(
            f"mod-{tag}@prefeitura.test", "moderator"
        )
        self.orphan = self.auth.provision_staff(
            f"orfao-{tag}@prefeitura.test", "agency", None
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        settings.jwt_secret = self.previous_secret

    def headers(self, user) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token(user.id, user.role)}"}

    def create_forwarded_report(
        self,
        *,
        agency_id: str = ZELADORIA,
        description: str = "Cratera na pista",
        category: ReportCategory = ReportCategory.URBAN_RISK,
        subcategory: str | None = None,
        citizen_id: int = 5001,
    ):
        """Cria um reporte já classificado, confirmado e encaminhado ao órgão."""
        report_id = uuid4()
        self.reports.create(
            NewReport(
                id=report_id,
                description=description,
                has_photo=False,
                category=category,
                latitude=-23.55,
                longitude=-46.63,
                location_accuracy_m=None,
                anonymous=False,
                client_created_at=datetime.now(timezone.utc),
                correlation_id=uuid4(),
                user_id=citizen_id,
                requester_user_id=citizen_id,
            )
        )
        classification = ClassificationResult(
            category=category,
            subcategory=subcategory,
            urgency="alta",
            confidence=0.9,
            immediate_risk=False,
            model="test",
            source="user",
        )
        self.reports.record_classification(report_id, classification)
        route = app.state.report_service._routing_service.find_rule(
            category, subcategory
        )
        route = route.model_copy(
            update={
                "agency_id": agency_id,
                "agency_name": dict(
                    app.state.staff_service._routing.list_agencies()
                )[agency_id],
            }
        )
        self.reports.apply_triage(
            report_id,
            citizen_id,
            TriageRequest(action="confirm").action,
            classification,
            route,
            datetime.now(timezone.utc) + timedelta(hours=72),
        )
        return report_id

    # --- autenticação e papéis -------------------------------------------

    async def test_requires_authentication(self) -> None:
        for path in ("/v1/staff/me", "/v1/staff/summary", "/v1/staff/reports"):
            response = await self.client.get(path)
            self.assertEqual(response.status_code, 401, path)

    async def test_citizen_token_is_forbidden(self) -> None:
        response = await self.client.get(
            "/v1/staff/reports",
            headers={"Authorization": f"Bearer {access_token(5001, 'citizen')}"},
        )
        self.assertEqual(response.status_code, 403)

    async def test_forged_role_claim_is_ignored_when_db_role_is_citizen(self) -> None:
        citizen = self.auth._users_by_id.get(1)
        user = citizen or self.auth.provision_staff(
            f"cidadao-{uuid4().hex[:8]}@x.test", "agency", ZELADORIA
        )
        # Token diz 'manager', mas o banco diz outra coisa: o papel do banco vence.
        self.auth.provision_staff(user.email, "agency", None)
        response = await self.client.get(
            "/v1/staff/me",
            headers={"Authorization": f"Bearer {access_token(user.id, 'manager')}"},
        )
        self.assertEqual(response.status_code, 403)

    async def test_agency_staff_without_agency_link_is_forbidden(self) -> None:
        response = await self.client.get(
            "/v1/staff/reports", headers=self.headers(self.orphan)
        )
        self.assertEqual(response.status_code, 403)

    async def test_profile_exposes_role_scope_and_agency(self) -> None:
        agency = await self.client.get(
            "/v1/staff/me", headers=self.headers(self.zeladoria)
        )
        self.assertEqual(agency.status_code, 200)
        body = agency.json()
        self.assertEqual(body["role"], "agency")
        self.assertEqual(body["scope"], "agency")
        self.assertEqual(body["agency"]["id"], ZELADORIA)

        manager = await self.client.get(
            "/v1/staff/me", headers=self.headers(self.manager)
        )
        self.assertEqual(manager.json()["scope"], "all")
        self.assertIsNone(manager.json()["agency"])

    async def test_agencies_are_scoped_by_role(self) -> None:
        own = await self.client.get(
            "/v1/staff/agencies", headers=self.headers(self.zeladoria)
        )
        self.assertEqual([a["id"] for a in own.json()["items"]], [ZELADORIA])
        everything = await self.client.get(
            "/v1/staff/agencies", headers=self.headers(self.manager)
        )
        ids = {a["id"] for a in everything.json()["items"]}
        self.assertTrue({ZELADORIA, SANEAMENTO} <= ids)

    async def test_all_agencies_are_listed_as_redirect_targets(self) -> None:
        targets = await self.client.get(
            "/v1/staff/agencies?scope=all", headers=self.headers(self.zeladoria)
        )

        ids = {a["id"] for a in targets.json()["items"]}
        self.assertTrue({ZELADORIA, SANEAMENTO} <= ids)

    # --- listagem e escopo -----------------------------------------------

    async def test_list_is_limited_to_own_agency(self) -> None:
        mine = self.create_forwarded_report(agency_id=ZELADORIA)
        other = self.create_forwarded_report(agency_id=SANEAMENTO)

        response = await self.client.get(
            "/v1/staff/reports?limit=100", headers=self.headers(self.zeladoria)
        )
        ids = {item["id"] for item in response.json()["items"]}
        self.assertIn(str(mine), ids)
        self.assertNotIn(str(other), ids)

        everything = await self.client.get(
            "/v1/staff/reports?limit=100", headers=self.headers(self.manager)
        )
        ids = {item["id"] for item in everything.json()["items"]}
        self.assertTrue({str(mine), str(other)} <= ids)

    async def test_list_filters_and_pagination(self) -> None:
        marker = uuid4().hex[:10]
        first = self.create_forwarded_report(description=f"alfa {marker}")
        second = self.create_forwarded_report(description=f"beta {marker}")
        headers = self.headers(self.manager)

        found = await self.client.get(
            f"/v1/staff/reports?q={marker}&limit=1", headers=headers
        )
        body = found.json()
        self.assertEqual(len(body["items"]), 1)
        self.assertIsNotNone(body["next_cursor"])

        page_two = await self.client.get(
            f"/v1/staff/reports?q={marker}&limit=1&cursor={body['next_cursor']}",
            headers=headers,
        )
        seen = {body["items"][0]["id"], page_two.json()["items"][0]["id"]}
        self.assertEqual(seen, {str(first), str(second)})
        self.assertIsNone(page_two.json()["next_cursor"])

        by_status = await self.client.get(
            f"/v1/staff/reports?q={marker}&status=resolvido", headers=headers
        )
        self.assertEqual(by_status.json()["items"], [])

        bad_cursor = await self.client.get(
            f"/v1/staff/reports?cursor={uuid4()}", headers=headers
        )
        self.assertEqual(bad_cursor.status_code, 400)

    async def test_summary_counts_by_status_within_scope(self) -> None:
        before = (
            await self.client.get(
                "/v1/staff/summary", headers=self.headers(self.zeladoria)
            )
        ).json()
        self.create_forwarded_report(agency_id=ZELADORIA)
        self.create_forwarded_report(agency_id=SANEAMENTO)
        after = (
            await self.client.get(
                "/v1/staff/summary", headers=self.headers(self.zeladoria)
            )
        ).json()
        self.assertEqual(after["total"], before["total"] + 1)
        self.assertEqual(
            after["by_status"]["encaminhado"],
            before["by_status"]["encaminhado"] + 1,
        )

    # --- detalhe ---------------------------------------------------------

    async def test_detail_hides_reports_from_other_agencies(self) -> None:
        other = self.create_forwarded_report(agency_id=SANEAMENTO)
        response = await self.client.get(
            f"/v1/staff/reports/{other}", headers=self.headers(self.zeladoria)
        )
        self.assertEqual(response.status_code, 404)
        allowed = await self.client.get(
            f"/v1/staff/reports/{other}", headers=self.headers(self.saneamento)
        )
        self.assertEqual(allowed.status_code, 200)

    async def test_detail_masks_citizen_identity_in_timeline(self) -> None:
        report_id = self.create_forwarded_report(citizen_id=7777)
        response = await self.client.get(
            f"/v1/staff/reports/{report_id}", headers=self.headers(self.zeladoria)
        )
        actors = {event["actor"] for event in response.json()["timeline"]}
        self.assertIn("citizen", actors)
        self.assertNotIn("citizen:7777", actors)
        self.assertNotIn("7777", response.text)

    # --- mudança de status -----------------------------------------------

    async def test_status_flow_in_progress_then_resolved(self) -> None:
        report_id = self.create_forwarded_report()
        headers = self.headers(self.zeladoria)
        deadline = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

        started = await self.client.post(
            f"/v1/staff/reports/{report_id}/status",
            json={"action": "in_progress", "deadline": deadline},
            headers=headers,
        )
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["status"], "em_andamento")
        agency_events = [
            e for e in started.json()["timeline"] if e["type"] == "em_andamento"
        ]
        self.assertEqual(agency_events[-1]["actor"], f"agency:{ZELADORIA}")

        resolved = await self.client.post(
            f"/v1/staff/reports/{report_id}/status",
            json={"action": "resolved", "justification": "Pista recapeada"},
            headers=headers,
        )
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["status"], "resolvido")

    async def test_status_rejects_invalid_transitions_and_inputs(self) -> None:
        report_id = self.create_forwarded_report()
        headers = self.headers(self.zeladoria)
        url = f"/v1/staff/reports/{report_id}/status"

        skip = await self.client.post(
            url,
            json={"action": "resolved", "justification": "ok"},
            headers=headers,
        )
        self.assertEqual(skip.status_code, 409)

        no_deadline = await self.client.post(
            url, json={"action": "in_progress"}, headers=headers
        )
        self.assertEqual(no_deadline.status_code, 422)

        past = await self.client.post(
            url,
            json={
                "action": "in_progress",
                "deadline": (
                    datetime.now(timezone.utc) - timedelta(hours=1)
                ).isoformat(),
            },
            headers=headers,
        )
        self.assertEqual(past.status_code, 422)

        no_reason = await self.client.post(
            url, json={"action": "contest"}, headers=headers
        )
        self.assertEqual(no_reason.status_code, 422)

    async def test_contest_does_not_change_status(self) -> None:
        report_id = self.create_forwarded_report()
        response = await self.client.post(
            f"/v1/staff/reports/{report_id}/status",
            json={"action": "contest", "justification": "Fora da competência"},
            headers=self.headers(self.zeladoria),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], ReportStatus.FORWARDED.value)
        self.assertEqual(response.json()["timeline"][-1]["type"], "contestado")

    async def test_status_is_blocked_outside_scope_and_for_read_only_roles(self) -> None:
        report_id = self.create_forwarded_report(agency_id=SANEAMENTO)
        payload = {
            "action": "contest",
            "justification": "Fora da competência",
        }
        url = f"/v1/staff/reports/{report_id}/status"

        outside = await self.client.post(
            url, json=payload, headers=self.headers(self.zeladoria)
        )
        self.assertEqual(outside.status_code, 404)

        manager = await self.client.post(
            url, json=payload, headers=self.headers(self.manager)
        )
        self.assertEqual(manager.status_code, 403)

        moderator = await self.client.post(
            url, json=payload, headers=self.headers(self.moderator)
        )
        self.assertEqual(moderator.status_code, 403)

    # --- bootstrap de desenvolvimento ------------------------------------

    def test_dev_staff_bootstrap_validates_input(self) -> None:
        known = {ZELADORIA}
        with self.assertRaises(RuntimeError):
            provision_dev_staff(self.auth, "a@b.test:citizen", known)
        with self.assertRaises(RuntimeError):
            provision_dev_staff(self.auth, "a@b.test:agency:inexistente", known)
        provision_dev_staff(
            self.auth, f"dev-{uuid4().hex[:6]}@b.test:agency:{ZELADORIA}", known
        )


    # --- redirecionamento a outro órgão (B3) -------------------------------

    async def redirect(self, report_id, user, **body):
        return await self.client.post(
            f"/v1/staff/reports/{report_id}/redirect",
            json=body,
            headers=self.headers(user),
        )

    async def test_agency_redirects_own_report_to_other_agency(self) -> None:
        report_id = self.create_forwarded_report()

        response = await self.redirect(
            report_id,
            self.zeladoria,
            agency_id=SANEAMENTO,
            justification="Vazamento é da rede de esgoto",
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "encaminhado")
        self.assertEqual(body["agency"]["id"], SANEAMENTO)
        last = body["timeline"][-1]
        self.assertEqual(last["type"], "encaminhado")
        self.assertEqual(last["actor"], f"agency:{ZELADORIA}")
        self.assertEqual(last["justification"], "Vazamento é da rede de esgoto")
        new_owner = await self.client.get(
            f"/v1/staff/reports/{report_id}", headers=self.headers(self.saneamento)
        )
        self.assertEqual(new_owner.status_code, 200)
        old_owner = await self.client.get(
            f"/v1/staff/reports/{report_id}", headers=self.headers(self.zeladoria)
        )
        self.assertEqual(old_owner.status_code, 404)
        stages = {stage for (job_report, stage) in app.state.report_worker._queue._jobs if job_report == report_id}
        self.assertIn(f"notify_agency_{last['id']}", stages)

    async def test_redirect_resets_in_progress_to_forwarded(self) -> None:
        report_id = self.create_forwarded_report()
        deadline = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        await self.client.post(
            f"/v1/staff/reports/{report_id}/status",
            json={"action": "in_progress", "deadline": deadline},
            headers=self.headers(self.zeladoria),
        )

        response = await self.redirect(
            report_id, self.manager, agency_id=SANEAMENTO, justification="Outro órgão"
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "encaminhado")
        self.assertIsNotNone(response.json()["deadline"])

    async def test_redirect_validates_target_and_justification(self) -> None:
        report_id = self.create_forwarded_report()
        cases = [
            ({"agency_id": SANEAMENTO}, 422),
            ({"agency_id": SANEAMENTO, "justification": "  "}, 422),
            ({"agency_id": "orgao-inexistente", "justification": "x"}, 422),
            ({"agency_id": ZELADORIA, "justification": "mesmo órgão"}, 409),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                response = await self.redirect(report_id, self.zeladoria, **body)
                self.assertEqual(response.status_code, expected, response.text)

    async def test_redirect_permissions(self) -> None:
        report_id = self.create_forwarded_report()

        moderator = await self.redirect(
            report_id, self.moderator, agency_id=SANEAMENTO, justification="x"
        )
        other_agency = await self.redirect(
            report_id, self.saneamento, agency_id=SANEAMENTO, justification="x"
        )

        self.assertEqual(moderator.status_code, 403)
        self.assertEqual(other_agency.status_code, 404)

    async def test_resolved_report_cannot_be_redirected(self) -> None:
        report_id = self.create_forwarded_report()
        headers = self.headers(self.zeladoria)
        deadline = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        await self.client.post(
            f"/v1/staff/reports/{report_id}/status",
            json={"action": "in_progress", "deadline": deadline},
            headers=headers,
        )
        await self.client.post(
            f"/v1/staff/reports/{report_id}/status",
            json={"action": "resolved", "justification": "feito"},
            headers=headers,
        )

        response = await self.redirect(
            report_id, self.zeladoria, agency_id=SANEAMENTO, justification="x"
        )

        self.assertEqual(response.status_code, 409)


    # --- moderação (B4) ---------------------------------------------------

    def create_report_in_moderation(self, *, subcategory=None):
        """Reporte classificado sem órgão (ex.: baixa confiança) na fila."""
        report_id = uuid4()
        self.reports.create(
            NewReport(
                id=report_id,
                description="Situação estranha na praça",
                has_photo=False,
                category=None,
                latitude=-23.55,
                longitude=-46.63,
                location_accuracy_m=None,
                anonymous=False,
                client_created_at=datetime.now(timezone.utc),
                correlation_id=uuid4(),
                user_id=5002,
                requester_user_id=5002,
            )
        )
        self.reports.record_classification(
            report_id,
            ClassificationResult(
                category=ReportCategory.TO_CLASSIFY,
                subcategory="a_classificar",
                urgency=None,
                confidence=0.2,
                immediate_risk=None,
                model="test",
                source="ai",
            ),
        )
        self.reports.mark_for_moderation(report_id)
        return report_id

    async def moderate(self, report_id, decision, user, **body):
        return await self.client.post(
            f"/v1/staff/moderation/{report_id}/{decision}",
            json=body,
            headers=self.headers(user),
        )

    async def test_moderation_queue_lists_reports_for_moderators(self) -> None:
        report_id = self.create_report_in_moderation()

        queue = await self.client.get(
            "/v1/staff/moderation", headers=self.headers(self.moderator)
        )
        forbidden = await self.client.get(
            "/v1/staff/moderation", headers=self.headers(self.zeladoria)
        )

        self.assertEqual(queue.status_code, 200, queue.text)
        self.assertIn(str(report_id), [item["id"] for item in queue.json()["items"]])
        self.assertEqual(forbidden.status_code, 403)

    async def test_approve_with_category_forwards_to_responsible_agency(self) -> None:
        report_id = self.create_report_in_moderation()

        response = await self.moderate(
            report_id,
            "approve",
            self.moderator,
            category="risco_urbano",
            subcategory="buraco_via",
            justification="Foto mostra buraco na via",
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "encaminhado")
        self.assertEqual(body["triage_state"], "confirmed")
        self.assertEqual(body["agency"]["id"], ZELADORIA)
        self.assertEqual(body["classification"]["subcategory"], "buraco_via")
        approved = [e for e in body["timeline"] if e["type"] == "moderacao_aprovada"]
        self.assertEqual(approved[-1]["justification"], "Foto mostra buraco na via")
        queue = await self.client.get(
            "/v1/staff/moderation", headers=self.headers(self.moderator)
        )
        self.assertNotIn(str(report_id), [i["id"] for i in queue.json()["items"]])

    async def test_approve_flagged_forwarded_report_keeps_its_agency(self) -> None:
        report_id = self.create_forwarded_report()
        self.reports.mark_for_moderation(report_id)

        response = await self.moderate(
            report_id, "approve", self.moderator, justification="Denúncia improcedente"
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["agency"]["id"], ZELADORIA)
        self.assertEqual(response.json()["triage_state"], "confirmed")

    async def test_approve_without_category_for_unrouted_report_is_422(self) -> None:
        report_id = self.create_report_in_moderation()

        response = await self.moderate(
            report_id, "approve", self.moderator, justification="ok"
        )

        self.assertEqual(response.status_code, 422)

    async def test_reject_hides_report_and_records_justification(self) -> None:
        report_id = self.create_report_in_moderation()

        response = await self.moderate(
            report_id, "reject", self.moderator, justification="Conteúdo ofensivo"
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["triage_state"], "rejected")
        rejected = response.json()["timeline"][-1]
        self.assertEqual(rejected["type"], "moderacao_rejeitada")
        self.assertEqual(rejected["justification"], "Conteúdo ofensivo")
        again = await self.moderate(
            report_id, "reject", self.moderator, justification="de novo"
        )
        self.assertEqual(again.status_code, 409)

    async def test_moderation_requires_moderator_and_justification(self) -> None:
        report_id = self.create_report_in_moderation()

        agency = await self.moderate(
            report_id, "reject", self.zeladoria, justification="x"
        )
        empty = await self.moderate(
            report_id, "reject", self.moderator, justification=" "
        )

        self.assertEqual(agency.status_code, 403)
        self.assertEqual(empty.status_code, 422)


    # --- analítica (B6/B7) ------------------------------------------------

    async def test_analytics_is_scoped_to_the_agency(self) -> None:
        self.create_forwarded_report(agency_id=ZELADORIA)
        self.create_forwarded_report(agency_id=SANEAMENTO)

        own = await self.client.get(
            "/v1/staff/analytics", headers=self.headers(self.zeladoria)
        )
        everyone = await self.client.get(
            "/v1/staff/analytics?bucket=week", headers=self.headers(self.manager)
        )

        self.assertEqual(own.status_code, 200, own.text)
        own_agencies = {a["agency"]["id"] for a in own.json()["by_agency"]}
        self.assertEqual(own_agencies, {ZELADORIA})
        self.assertEqual(len(own.json()["timeseries"]), 30)
        all_agencies = {a["agency"]["id"] for a in everyone.json()["by_agency"]}
        self.assertLessEqual({ZELADORIA, SANEAMENTO}, all_agencies)
        self.assertEqual(everyone.json()["period"]["bucket"], "week")

    async def test_analytics_rejects_inverted_period(self) -> None:
        response = await self.client.get(
            "/v1/staff/analytics?from=2026-11-10&to=2026-11-01",
            headers=self.headers(self.manager),
        )

        self.assertEqual(response.status_code, 422)


class StaffDeadlineTests(unittest.TestCase):
    def test_naive_deadline_from_oracle_is_treated_as_utc(self) -> None:
        from datetime import datetime, timedelta, timezone

        from app.models.reports import ReportStatus
        from app.models.staff import is_due_soon, is_overdue

        now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
        past = (now - timedelta(hours=1)).replace(tzinfo=None)
        soon = (now + timedelta(hours=1)).replace(tzinfo=None)

        self.assertTrue(is_overdue(ReportStatus.FORWARDED, past, now))
        self.assertTrue(is_due_soon(ReportStatus.IN_PROGRESS, soon, now))


if __name__ == "__main__":
    unittest.main()
