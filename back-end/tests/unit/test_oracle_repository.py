import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import oracledb
from pydantic import SecretStr

from app.core.config import Settings
from app.core.geo import GeoBox
from app.infrastructure.database import OracleDatabase
from app.infrastructure.geohash import encode_geohash
from app.infrastructure.job_queue import OracleJobQueue
from app.models.classification import ClassificationResult, RouteDecision
from app.models.reports import ClientTimestampOutOfRange, NewReport, ReportStatus
from app.models.taxonomy import ReportCategory
from app.infrastructure.repositories import (
    OracleReportRepository,
    ReportIdConflict,
)


class FakeVariable:
    def __init__(self) -> None:
        self.value = None

    def getvalue(self):
        return self.value


class FakeCursor:
    def __init__(self) -> None:
        self.call_name = None
        self.call_parameters = None
        self.executed_query = None
        self.query_parameters = None
        self.closed = False
        self.call_error = None

    def var(self, database_type, *, size=None):
        return FakeVariable()

    def callproc(self, name, parameters):
        if self.call_error is not None:
            raise self.call_error
        self.call_name = name
        self.call_parameters = parameters
        if name == "PKG_REPORTES.registrar_reporte":
            parameters[-2].value = "RPT-2026-4KQ7TD"
            parameters[-1].value = 1
        elif name == "PKG_REPORTES.criar_comentario":
            parameters[-1].value = 37
        elif name == "PKG_REPORTES.confirmar":
            parameters[-1].value = 3

    def execute(self, query, **parameters):
        self.executed_query = query
        self.query_parameters = parameters

    def fetchone(self):
        return (datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc),)

    def fetchall(self):
        return [
            (
                37,
                "8d11c206-f849-4631-9c0f-d27a23fc7634",
                24,
                "Vi a situação hoje.",
                datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc),
            )
        ]

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.fake_cursor = FakeCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeDatabase:
    def __init__(self) -> None:
        self.fake_connection = FakeConnection()

    @contextmanager
    def connection(self):
        yield self.fake_connection


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.released = []
        self.closed = False

    def acquire(self):
        return self.connection

    def release(self, connection):
        self.released.append(connection)

    def close(self):
        self.closed = True


class OracleDatabaseTests(unittest.TestCase):
    def test_pool_uses_configured_credentials_and_releases_connections(self) -> None:
        config = Settings(
            db_user="app_user",
            db_password=SecretStr("a-database-password"),
            db_dsn="localhost:1521/FREEPDB1",
            db_pool_min=1,
            db_pool_max=4,
        )
        pool = FakePool()
        database = OracleDatabase(config)

        with patch(
            "app.infrastructure.database.oracledb.create_pool",
            return_value=pool,
        ) as create_pool:
            database.open()
            with database.connection() as connection:
                self.assertIs(connection, pool.connection)
            database.close()

        create_pool.assert_called_once_with(
            user="app_user",
            password="a-database-password",
            dsn="localhost:1521/FREEPDB1",
            min=1,
            max=4,
        )
        self.assertEqual(pool.released, [pool.connection])
        self.assertTrue(pool.closed)

    def test_pool_requires_database_credentials(self) -> None:
        with self.assertRaises(RuntimeError):
            OracleDatabase(Settings()).open()


class OracleRepositoryTests(unittest.TestCase):
    def test_geohash_matches_known_precision_five_value(self) -> None:
        self.assertEqual(encode_geohash(42.6, -5.6, precision=5), "ezs42")

    def test_create_calls_package_and_commits(self) -> None:
        database = FakeDatabase()
        repository = OracleReportRepository(database)
        report_id = uuid4()
        correlation_id = uuid4()
        report = NewReport(
            id=report_id,
            description="Buraco na via",
            has_photo=False,
            category=None,
            latitude=-23.55,
            longitude=-46.63,
            location_accuracy_m=None,
            anonymous=False,
            client_created_at=datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc),
            correlation_id=correlation_id,
            user_id=23,
            requester_user_id=23,
        )

        result = repository.create(report)

        cursor = database.fake_connection.fake_cursor
        self.assertEqual(cursor.call_name, "PKG_REPORTES.registrar_reporte")
        self.assertEqual(len(cursor.call_parameters), 15)
        self.assertEqual(cursor.call_parameters[0], str(report_id))
        self.assertEqual(cursor.call_parameters[1:3], [23, 23])
        self.assertEqual(cursor.call_parameters[7], encode_geohash(-23.55, -46.63))
        # push_token, has_photo e address (ausente em versões antigas do app).
        self.assertEqual(
            cursor.call_parameters[10:13],
            [None, 0, None],
        )
        self.assertEqual(
            cursor.executed_query,
            "SELECT received_at FROM reports WHERE id = :report_id",
        )
        self.assertEqual(cursor.query_parameters, {"report_id": str(report_id)})
        self.assertTrue(database.fake_connection.committed)
        self.assertFalse(database.fake_connection.rolled_back)
        self.assertTrue(cursor.closed)
        self.assertEqual(result.id, report_id)
        self.assertEqual(result.protocol, "RPT-2026-4KQ7TD")
        self.assertTrue(result.was_created)

    def test_create_sends_address_before_out_parameters(self) -> None:
        database = FakeDatabase()
        repository = OracleReportRepository(database)
        report = NewReport(
            id=uuid4(),
            description="Buraco na via",
            has_photo=False,
            category=None,
            latitude=-23.55,
            longitude=-46.63,
            location_accuracy_m=None,
            anonymous=False,
            client_created_at=datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc),
            correlation_id=uuid4(),
            user_id=23,
            requester_user_id=23,
            address="Rua Exemplo, 123 – Bairro, Cidade",
        )

        repository.create(report)

        cursor = database.fake_connection.fake_cursor
        # p_address entra depois de p_has_photo; os dois OUT continuam no fim.
        self.assertEqual(len(cursor.call_parameters), 15)
        self.assertEqual(
            cursor.call_parameters[12], "Rua Exemplo, 123 – Bairro, Cidade"
        )

    def test_business_errors_are_rolled_back_and_translated(self) -> None:
        class FakeOracleErrorInfo:
            def __init__(self, code: int) -> None:
                self.code = code

        class FakeDatabaseError(Exception):
            pass

        expected_errors = {
            20010: ClientTimestampOutOfRange,
            20011: ReportIdConflict,
        }
        for oracle_code, expected_error in expected_errors.items():
            with self.subTest(oracle_code=oracle_code):
                database = FakeDatabase()
                database.fake_connection.fake_cursor.call_error = FakeDatabaseError(
                    FakeOracleErrorInfo(oracle_code)
                )
                repository = OracleReportRepository(database)
                report = NewReport(
                    id=uuid4(),
                    description="Buraco na via",
                    has_photo=False,
                    category=None,
                    latitude=-23.55,
                    longitude=-46.63,
                    location_accuracy_m=None,
                    anonymous=False,
                    client_created_at=datetime(
                        2026,
                        11,
                        17,
                        15,
                        0,
                        tzinfo=timezone.utc,
                    ),
                    correlation_id=uuid4(),
                    user_id=23,
                    requester_user_id=23,
                )

                with patch("oracledb.DatabaseError", FakeDatabaseError):
                    with self.assertRaises(expected_error):
                        repository.create(report)

                self.assertFalse(database.fake_connection.committed)
                self.assertTrue(database.fake_connection.rolled_back)

    def test_create_comment_calls_package_and_commits(self) -> None:
        database = FakeDatabase()
        repository = OracleReportRepository(database)
        report_id = uuid4()

        comment = repository.create_comment(
            report_id,
            24,
            "Vi a situação hoje.",
        )

        cursor = database.fake_connection.fake_cursor
        self.assertEqual(cursor.call_name, "PKG_REPORTES.criar_comentario")
        self.assertEqual(
            cursor.call_parameters[:3],
            [str(report_id), 24, "Vi a situação hoje."],
        )
        self.assertEqual(comment.id, 37)
        self.assertEqual(comment.user_id, 24)
        self.assertTrue(database.fake_connection.committed)
        self.assertFalse(database.fake_connection.rolled_back)

    def test_list_comments_checks_report_and_returns_public_content(self) -> None:
        database = FakeDatabase()
        repository = OracleReportRepository(database)
        report_id = UUID("8d11c206-f849-4631-9c0f-d27a23fc7634")

        comments = repository.list_comments(report_id, limit=50)

        cursor = database.fake_connection.fake_cursor
        self.assertEqual(
            cursor.query_parameters,
            {"report_id": str(report_id), "limit": 50},
        )
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].content, "Vi a situação hoje.")
        self.assertEqual(comments[0].user_id, 24)

    def test_confirm_calls_package_and_commits(self) -> None:
        database = FakeDatabase()
        repository = OracleReportRepository(database)
        report_id = uuid4()

        count = repository.confirm(report_id, 24)

        cursor = database.fake_connection.fake_cursor
        self.assertEqual(cursor.call_name, "PKG_REPORTES.confirmar")
        self.assertEqual(
            cursor.call_parameters[:2],
            [str(report_id), 24],
        )
        self.assertEqual(count, 3)
        self.assertTrue(database.fake_connection.committed)
        self.assertFalse(database.fake_connection.rolled_back)

    def test_record_classification_calls_package_and_commits(self) -> None:
        database = FakeDatabase()
        repository = OracleReportRepository(database)
        report_id = uuid4()
        classification = ClassificationResult(
            category="risco_urbano",
            subcategory="buraco_via",
            urgency="media",
            confidence=0.85,
            immediate_risk=False,
            model="fake",
            source="ai",
        )

        repository.record_classification(report_id, classification)

        cursor = database.fake_connection.fake_cursor
        self.assertEqual(
            cursor.call_name,
            "PKG_REPORTES.registrar_classificacao",
        )
        self.assertEqual(cursor.call_parameters[0], str(report_id))
        self.assertIn('"category":"risco_urbano"', cursor.call_parameters[1])
        self.assertTrue(database.fake_connection.committed)

    def test_set_photo_key_calls_package_and_commits(self) -> None:
        database = FakeDatabase()
        repository = OracleReportRepository(database)
        report_id = uuid4()

        repository.set_photo_key(report_id, "objects/photo.jpg")

        cursor = database.fake_connection.fake_cursor
        self.assertEqual(cursor.call_name, "PKG_REPORTES.finalizar_foto")
        self.assertEqual(
            cursor.call_parameters,
            [str(report_id), "objects/photo.jpg"],
        )
        self.assertTrue(database.fake_connection.committed)
        self.assertFalse(database.fake_connection.rolled_back)

    def test_apply_triage_calls_routing_package_and_commits(self) -> None:
        database = FakeDatabase()
        repository = OracleReportRepository(database)
        report_id = uuid4()
        classification = ClassificationResult(
            category="risco_urbano",
            subcategory="esgoto_vazamento",
            urgency="media",
            confidence=0.85,
            immediate_risk=False,
            model="fake",
            source="user",
        )
        route = RouteDecision(
            rule_id="esgoto-saneamento",
            rule_version=1,
            territory_id="municipio_demo",
            agency_id="saneamento-demo",
            agency_name="Saneamento Demo",
            deadline_hours=120,
        )

        repository.apply_triage(
            report_id,
            23,
            "correct",
            classification,
            route,
            datetime(2026, 11, 22, tzinfo=timezone.utc),
        )

        cursor = database.fake_connection.fake_cursor
        self.assertEqual(
            cursor.call_name,
            "PKG_ROTEAMENTO.aplicar_triagem",
        )
        self.assertEqual(
            cursor.call_parameters[:3],
            [str(report_id), 23, "correct"],
        )
        self.assertIn(
            '"subcategory":"esgoto_vazamento"',
            cursor.call_parameters[3],
        )
        self.assertTrue(database.fake_connection.committed)

    def test_oracle_job_queue_uses_durable_package(self) -> None:
        database = FakeDatabase()
        queue = OracleJobQueue(database)
        report_id = uuid4()

        queue.enqueue(report_id, "classificar")
        cursor = database.fake_connection.fake_cursor
        self.assertEqual(cursor.call_name, "PKG_JOBS.enfileirar")
        self.assertEqual(cursor.call_parameters, [str(report_id), "classificar"])
        self.assertTrue(database.fake_connection.committed)

        database.fake_connection.committed = False
        self.assertIsNone(queue.reserve_next("worker-1", lease_seconds=90))
        self.assertEqual(cursor.call_name, "PKG_JOBS.reservar_proximo")
        self.assertTrue(database.fake_connection.committed)

        queue.complete(7, "worker-1")
        self.assertEqual(cursor.call_name, "PKG_JOBS.concluir")
        self.assertEqual(cursor.call_parameters, [7, "worker-1"])
        self.assertTrue(database.fake_connection.committed)

        queue.fail(7, "worker-1", "DatabaseError", max_attempts=6)
        self.assertEqual(cursor.call_name, "PKG_JOBS.falhar")
        self.assertEqual(
            cursor.call_parameters,
            [7, "worker-1", "DatabaseError", 6],
        )
        self.assertTrue(database.fake_connection.committed)


class OracleNotificationTokenTests(unittest.TestCase):
    def test_tokens_come_from_registered_devices(self) -> None:
        # notification_links também tem push_token; sem qualificar, o Oracle
        # recusa a consulta (ORA-00918) e nenhum aviso de status sai.
        database = FakeDatabase()
        cursor = database.fake_connection.fake_cursor
        cursor.fetchall = lambda: [("device-token",)]

        tokens = OracleReportRepository(database).list_notification_tokens(
            UUID("8d11c206-f849-4631-9c0f-d27a23fc7634")
        )

        query = " ".join(cursor.executed_query.split())
        self.assertIn("SELECT DISTINCT device.push_token", query)
        self.assertEqual(tokens, ["device-token"])


class OracleAreaQueryTests(unittest.TestCase):
    def test_list_in_area_filters_box_and_hides_moderation(self) -> None:
        report_id = "8d11c206-f849-4631-9c0f-d27a23fc7634"
        received_at = datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc)
        database = FakeDatabase()
        cursor = database.fake_connection.fake_cursor
        cursor.fetchall = lambda: [
            (
                report_id,
                "RPT-2026-4KQ7TD",
                "em_andamento",
                "risco_urbano",
                -23.5501,
                -46.6331,
                received_at,
                "grupo-9",
                4,
                "buraco_via",
            )
        ]
        repository = OracleReportRepository(database)
        box = GeoBox(min_lat=-23.56, max_lat=-23.54, min_lon=-46.64, max_lon=-46.62)

        found = repository.list_in_area(box, max_items=50)

        self.assertEqual(
            cursor.query_parameters,
            {
                "min_lat": -23.56,
                "max_lat": -23.54,
                "min_lon": -46.64,
                "max_lon": -46.62,
                "max_items": 50,
            },
        )
        query = " ".join(cursor.executed_query.split())
        self.assertIn("r.lat BETWEEN :min_lat AND :max_lat", query)
        self.assertIn("r.lon BETWEEN :min_lon AND :max_lon", query)
        self.assertIn("r.triage_state NOT IN ('in_moderation', 'rejected')", query)
        self.assertIn("ORDER BY r.received_at DESC", query)
        self.assertTrue(cursor.closed)
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertEqual(item.id, UUID(report_id))
        self.assertEqual(item.status, ReportStatus.IN_PROGRESS)
        self.assertEqual(item.category, ReportCategory.URBAN_RISK)
        self.assertEqual((item.latitude, item.longitude), (-23.5501, -46.6331))
        self.assertEqual(item.group_id, "grupo-9")
        self.assertEqual(item.confirmation_count, 4)
        self.assertEqual(item.subcategory, "buraco_via")


# O driver devolve TIMESTAMP sem fuso; por convenção do projeto, em UTC.
NAIVE_RECEIVED_AT = datetime(2026, 11, 19, 23, 29, 25, 789511)
UTC_RECEIVED_AT = NAIVE_RECEIVED_AT.replace(tzinfo=timezone.utc)
ADDRESS = "Rua Exemplo, 123 – Bairro, Cidade"


def scripted_cursor(database, *, fetchone=(), fetchall=()):
    """Respostas em ordem para cada fetchone/fetchall; guarda as consultas."""
    cursor = database.fake_connection.fake_cursor
    one, many, queries = iter(fetchone), iter(fetchall), []
    original_execute = cursor.execute

    def execute(query, **parameters):
        queries.append(" ".join(query.split()))
        original_execute(query, **parameters)

    cursor.execute = execute
    cursor.fetchone = lambda: next(one)
    cursor.fetchall = lambda: next(many)
    return cursor, queries


class OracleReportViewsTests(unittest.TestCase):
    """Endereço, descrição, subcategoria e datas em UTC nas visões do reporte."""

    report_id = "8d11c206-f849-4631-9c0f-d27a23fc7634"

    def test_user_reports_carry_description_subcategory_address_and_utc(self) -> None:
        database = FakeDatabase()
        _, queries = scripted_cursor(
            database,
            fetchall=[[(
                self.report_id, "RPT-2026-4KQ7TD", "encaminhado", "risco_urbano",
                -23.573806, -46.623157, NAIVE_RECEIVED_AT, "12", 2,
                "Vazamento de esgoto na rua.", "esgoto_vazamento", ADDRESS,
            )]],
        )

        [item] = OracleReportRepository(database).list_user_reports(
            23, limit=20, cursor_id=None, status=None
        )

        self.assertIn("r.address", queries[-1])
        self.assertIn("'$.subcategory'", queries[-1])
        self.assertEqual(item.description, "Vazamento de esgoto na rua.")
        self.assertEqual(item.subcategory, "esgoto_vazamento")
        self.assertEqual(item.address, ADDRESS)
        self.assertEqual(item.received_at, UTC_RECEIVED_AT)
        self.assertIs(item.received_at.tzinfo, timezone.utc)

    def test_detail_carries_address_and_utc_datetimes(self) -> None:
        database = FakeDatabase()
        naive_event_at = datetime(2026, 11, 19, 23, 30)
        naive_deadline = datetime(2026, 11, 22, 23, 30)
        _, queries = scripted_cursor(
            database,
            fetchone=[(
                self.report_id, "RPT-2026-4KQ7TD", "encaminhado", "risco_urbano",
                "Vazamento", -23.573806, -46.623157, NAIVE_RECEIVED_AT, 23, 0,
                "confirmed", "12", 2, self.report_id, ADDRESS,
            )],
            fetchall=[
                [(1, "recebido", "system", None, naive_event_at)],
                [(
                    "encaminhado",
                    '{"agency_id": "saneamento-demo", "agency_name": "Saneamento"}',
                    naive_deadline,
                    "system",
                )],
            ],
        )

        detail = OracleReportRepository(database).get_detail(UUID(self.report_id))

        self.assertIn("r.address", queries[0])
        self.assertEqual(detail.summary.address, ADDRESS)
        self.assertEqual(detail.summary.received_at, UTC_RECEIVED_AT)
        self.assertIs(detail.summary.received_at.tzinfo, timezone.utc)
        self.assertIs(detail.timeline[0].created_at.tzinfo, timezone.utc)
        self.assertEqual(
            detail.deadline, naive_deadline.replace(tzinfo=timezone.utc)
        )

    def test_staff_list_carries_address_and_utc_received_at(self) -> None:
        database = FakeDatabase()
        _, queries = scripted_cursor(
            database,
            fetchall=[[(
                self.report_id, "RPT-2026-4KQ7TD", "encaminhado", "risco_urbano",
                "alta", "false", "Vazamento", -23.573806, -46.623157,
                NAIVE_RECEIVED_AT, None, "saneamento-demo", "Saneamento", 2,
                ADDRESS,
            )]],
        )

        [item] = OracleReportRepository(database).list_staff_reports(
            None, None, None, False, None, 20, None
        )

        self.assertIn("r.address", queries[-1])
        self.assertEqual(item.address, ADDRESS)
        self.assertEqual(item.received_at, UTC_RECEIVED_AT)
        self.assertIs(item.received_at.tzinfo, timezone.utc)


class OracleStaffSearchTests(unittest.TestCase):
    def test_search_matches_protocol_description_or_address_ignoring_case(self) -> None:
        database = FakeDatabase()
        cursor, queries = scripted_cursor(database, fetchall=[[]])

        OracleReportRepository(database).list_staff_reports(
            None, None, None, False, "  Rua Exemplo ", 20, None
        )

        self.assertIn(
            "AND (INSTR(LOWER(protocol), :q) > 0"
            " OR INSTR(LOWER(description), :q) > 0"
            " OR INSTR(LOWER(address), :q) > 0)",
            queries[-1],
        )
        self.assertEqual(cursor.query_parameters["q"], "rua exemplo")


class OracleUtcTimestampTests(unittest.TestCase):
    """Demais datas de reporte que a API devolve saem do Oracle com fuso UTC."""

    report_id = "8d11c206-f849-4631-9c0f-d27a23fc7634"

    def test_created_report_received_at_is_utc(self) -> None:
        database = FakeDatabase()
        scripted_cursor(database, fetchone=[(NAIVE_RECEIVED_AT,)])
        report = NewReport(
            id=uuid4(),
            description="Buraco na via",
            has_photo=False,
            category=None,
            latitude=-23.55,
            longitude=-46.63,
            location_accuracy_m=None,
            anonymous=False,
            client_created_at=datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc),
            correlation_id=uuid4(),
            user_id=23,
            requester_user_id=23,
        )

        persisted = OracleReportRepository(database).create(report)

        self.assertEqual(persisted.received_at, UTC_RECEIVED_AT)

    def test_moderation_queue_received_at_is_utc(self) -> None:
        database = FakeDatabase()
        scripted_cursor(database, fetchall=[[(
            self.report_id, "RPT-2026-4KQ7TD", "risco_urbano", -23.57, -46.62,
            NAIVE_RECEIVED_AT, "12", 0, "recebido",
        )]])

        [item] = OracleReportRepository(database).list_moderation(limit=10)

        self.assertEqual(item.received_at, UTC_RECEIVED_AT)

    def test_public_map_received_at_is_utc(self) -> None:
        database = FakeDatabase()
        scripted_cursor(database, fetchall=[[(
            self.report_id, "RPT-2026-4KQ7TD", "recebido", "risco_urbano",
            -23.57, -46.62, NAIVE_RECEIVED_AT, "12", 0, None,
        )]])
        box = GeoBox(min_lat=-23.6, max_lat=-23.5, min_lon=-46.7, max_lon=-46.6)

        [item] = OracleReportRepository(database).list_in_area(box, max_items=10)

        self.assertEqual(item.received_at, UTC_RECEIVED_AT)

    def test_comment_created_at_is_utc(self) -> None:
        database = FakeDatabase()
        scripted_cursor(
            database,
            fetchone=[(NAIVE_RECEIVED_AT,), (1,)],
            fetchall=[[(37, self.report_id, 24, "Vi hoje.", NAIVE_RECEIVED_AT)]],
        )
        repository = OracleReportRepository(database)

        created = repository.create_comment(UUID(self.report_id), 24, "Vi hoje.")
        [listed] = repository.list_comments(UUID(self.report_id), limit=50)

        self.assertEqual(created.created_at, UTC_RECEIVED_AT)
        self.assertEqual(listed.created_at, UTC_RECEIVED_AT)

    def test_export_writes_report_and_comment_dates_with_utc_offset(self) -> None:
        database = FakeDatabase()
        scripted_cursor(database, fetchall=[
            [(
                self.report_id, "RPT-2026-4KQ7TD", "Buraco", "risco_urbano",
                -23.57, -46.62, NAIVE_RECEIVED_AT, "confirmed", None,
            )],
            [],
            [(37, self.report_id, "Vi hoje.", NAIVE_RECEIVED_AT)],
        ])

        exported = OracleReportRepository(database).export_user_data(23)

        expected = UTC_RECEIVED_AT.isoformat()
        self.assertEqual(exported["reports"][0]["received_at"], expected)
        self.assertEqual(exported["comments"][0]["created_at"], expected)

    def test_export_includes_report_address(self) -> None:
        database = FakeDatabase()
        _, queries = scripted_cursor(database, fetchall=[
            [(
                self.report_id, "RPT-2026-4KQ7TD", "Buraco", "risco_urbano",
                -23.57, -46.62, NAIVE_RECEIVED_AT, "confirmed", ADDRESS,
            )],
            [],
            [],
        ])

        exported = OracleReportRepository(database).export_user_data(23)

        self.assertIn("received_at, triage_state, address", queries[0])
        self.assertEqual(exported["reports"][0]["address"], ADDRESS)


class OracleModerationQueueTests(unittest.TestCase):
    """Fila, decisão e detalhe leem reports.triage_state, mantida pelo
    PKG_REPORTES.sincronizar_triagem a partir dos eventos."""

    @staticmethod
    def _recording_cursor(database):
        cursor = database.fake_connection.fake_cursor
        queries, calls = [], []
        original_execute = cursor.execute

        def execute(query, **parameters):
            queries.append(" ".join(query.split()))
            original_execute(query, **parameters)

        def callproc(name, parameters):
            calls.append((name, parameters))

        cursor.execute = execute
        cursor.callproc = callproc
        return cursor, queries, calls

    def test_list_moderation_only_returns_pending_reports(self) -> None:
        # Sinalizado e já decidido não volta à fila: sem ação possível, o
        # detalhe na web aparecia sem botões.
        database = FakeDatabase()
        cursor = database.fake_connection.fake_cursor
        cursor.fetchall = lambda: []
        repository = OracleReportRepository(database)

        repository.list_moderation(limit=25)

        query = " ".join(cursor.executed_query.split())
        self.assertIn("WHERE r.triage_state = 'in_moderation'", query)
        self.assertNotIn("OR EXISTS", query)
        self.assertEqual(cursor.query_parameters, {"limit": 25})

    def test_resolve_moderation_rejects_report_not_in_moderation(self) -> None:
        database = FakeDatabase()
        cursor, _, calls = self._recording_cursor(database)
        cursor.fetchone = lambda: ("confirmed",)
        repository = OracleReportRepository(database)

        from app.infrastructure.repositories import TriageConflict

        with self.assertRaises(TriageConflict):
            repository.resolve_moderation(
                uuid4(), "reject", "Conteúdo ofensivo",
                actor="moderator:1", actor_user_id=1,
                classification=None, route=None, deadline=None,
            )

        self.assertEqual(calls, [])
        self.assertFalse(database.fake_connection.committed)

    def test_resolve_moderation_syncs_triage_state_from_events(self) -> None:
        database = FakeDatabase()
        cursor, queries, calls = self._recording_cursor(database)
        cursor.fetchone = lambda: ("in_moderation",)
        repository = OracleReportRepository(database)
        report_id = uuid4()

        with patch.object(repository, "get_detail", return_value=None):
            repository.resolve_moderation(
                report_id, "reject", "Conteúdo ofensivo",
                actor="moderator:1", actor_user_id=1,
                classification=None, route=None, deadline=None,
            )

        self.assertEqual(
            calls, [("PKG_REPORTES.sincronizar_triagem", [str(report_id)])]
        )
        self.assertFalse(any(q.startswith("UPDATE reports") for q in queries))
        self.assertTrue(database.fake_connection.committed)

    def test_flag_report_syncs_triage_state_from_events(self) -> None:
        database = FakeDatabase()
        cursor, queries, calls = self._recording_cursor(database)
        answers = iter([(1,), None])
        cursor.fetchone = lambda: next(answers)
        repository = OracleReportRepository(database)
        report_id = uuid4()

        repository.flag_report(report_id, 7, "falso", None)

        self.assertIn(
            ("PKG_REPORTES.sincronizar_triagem", [str(report_id)]), calls
        )
        self.assertFalse(any(q.startswith("UPDATE reports") for q in queries))
        self.assertTrue(database.fake_connection.committed)


class OracleTriageSweepTests(unittest.TestCase):
    def test_list_triage_due_selects_classified_reports_without_triage(self) -> None:
        report_id = "8d11c206-f849-4631-9c0f-d27a23fc7634"
        cutoff = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
        database = FakeDatabase()
        cursor = database.fake_connection.fake_cursor
        cursor.fetchall = lambda: [(report_id,)]
        repository = OracleReportRepository(database)

        due = repository.list_triage_due(cutoff, limit=25)

        self.assertEqual(due, [UUID(report_id)])
        self.assertEqual(cursor.query_parameters, {"cutoff": cutoff, "limit": 25})
        query = " ".join(cursor.executed_query.split())
        self.assertIn("c.type = 'classificado'", query)
        self.assertIn("c.created_at <= :cutoff", query)
        self.assertIn(
            "'classificacao_confirmada', 'classificacao_corrigida', 'enviado_moderacao'",
            query,
        )
        self.assertTrue(cursor.closed)

    def test_auto_triage_calls_package_without_citizen(self) -> None:
        database = FakeDatabase()
        repository = OracleReportRepository(database)
        report_id = uuid4()
        result = ClassificationResult(
            category="risco_urbano",
            subcategory=None,
            urgency="media",
            confidence=0.9,
            immediate_risk=False,
            model="fake",
            source="ai",
        )

        repository.apply_triage(report_id, None, "auto", result, None, None)

        cursor = database.fake_connection.fake_cursor
        self.assertEqual(cursor.call_name, "PKG_ROTEAMENTO.aplicar_triagem")
        self.assertEqual(cursor.call_parameters[:3], [str(report_id), None, "auto"])
        self.assertTrue(database.fake_connection.committed)



class OracleDedupTests(unittest.TestCase):
    def test_list_dedup_candidates_filters_area_window_and_open_groups(self) -> None:
        target = uuid4()
        candidate = "8d11c206-f849-4631-9c0f-d27a23fc7634"
        since = datetime(2026, 11, 4, tzinfo=timezone.utc)
        database = FakeDatabase()
        cursor = database.fake_connection.fake_cursor
        cursor.fetchall = lambda: [
            (candidate, 12, -23.5501, -46.6331, "Buraco na calçada",
             "risco_urbano", "buraco")
        ]
        repository = OracleReportRepository(database)
        box = GeoBox(min_lat=-23.56, max_lat=-23.54, min_lon=-46.64, max_lon=-46.62)

        found = repository.list_dedup_candidates(target, box, since, 50)

        self.assertEqual(cursor.query_parameters, {
            "report_id": str(target),
            "min_lat": -23.56, "max_lat": -23.54,
            "min_lon": -46.64, "max_lon": -46.62,
            "since": since, "max_items": 50,
        })
        query = " ".join(cursor.executed_query.split())
        self.assertIn("r.received_at >= :since", query)
        self.assertIn("r.group_id <> (SELECT group_id FROM reports WHERE id = :report_id)", query)
        self.assertIn("'resolvido'", query)
        self.assertIn("'in_moderation'", query)
        item = found[0]
        self.assertEqual(item.report_id, UUID(candidate))
        self.assertEqual(item.group_id, "12")
        self.assertEqual(item.category, ReportCategory.URBAN_RISK)
        self.assertEqual(item.subcategory, "buraco")
        self.assertTrue(cursor.closed)

    def test_link_to_group_calls_dedup_package(self) -> None:
        database = FakeDatabase()
        repository = OracleReportRepository(database)
        report_id = uuid4()

        repository.link_to_group(report_id, "12", similarity=0.91, distance_m=18.4)

        cursor = database.fake_connection.fake_cursor
        self.assertEqual(cursor.call_name, "PKG_DEDUP.vincular")
        self.assertEqual(cursor.call_parameters, [str(report_id), 12, 0.91, 18.4])
        self.assertTrue(database.fake_connection.committed)


if __name__ == "__main__":
    unittest.main()
