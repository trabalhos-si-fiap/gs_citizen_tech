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
        self.assertEqual(len(cursor.call_parameters), 14)
        self.assertEqual(cursor.call_parameters[0], str(report_id))
        self.assertEqual(cursor.call_parameters[1:3], [23, 23])
        self.assertEqual(cursor.call_parameters[7], encode_geohash(-23.55, -46.63))
        self.assertEqual(
            cursor.call_parameters[10:12],
            [None, 0],
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
        self.assertIn("r.triage_state <> 'in_moderation'", query)
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
