import unittest
from contextlib import contextmanager
from datetime import datetime, timezone

from app.models.auth import AuthUser
from app.infrastructure.repositories import OracleAuthRepository


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
        self.closed = False

    def var(self, database_type, *, size=None):
        return FakeVariable()

    def callproc(self, name, parameters):
        self.call_name = name
        self.call_parameters = parameters
        if name == "PKG_AUTH.validar_otp":
            parameters[4].value = "ok"
            parameters[5].value = 7
            parameters[6].value = "citizen"
            parameters[7].value = "v1"
        elif name == "PKG_AUTH.rotacionar_refresh_token":
            parameters[3].value = "ok"
            parameters[4].value = 7
            parameters[5].value = "citizen"
            parameters[6].value = "v1"
        elif name == "PKG_AUTH.login_google":
            parameters[6].value = "ok"
            parameters[7].value = 7
            parameters[8].value = "citizen"
            parameters[9].value = "v1"

    def execute(self, query, **parameters):
        self.executed_query = query

    def fetchone(self):
        created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        if self.executed_query.startswith("SELECT created_at"):
            return (created_at,)
        return "person@example.com", created_at

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


class OracleAuthRepositoryTests(unittest.TestCase):
    def test_verify_otp_calls_package_and_returns_user(self) -> None:
        database = FakeDatabase()
        repository = OracleAuthRepository(database)

        user = repository.verify_otp(
            "person@example.com",
            "otp-hash",
            refresh_token_hash="refresh-hash",
            refresh_expires_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(
            database.fake_connection.fake_cursor.call_name,
            "PKG_AUTH.validar_otp",
        )
        self.assertIsInstance(user, AuthUser)
        self.assertEqual(user.id, 7)
        self.assertEqual(user.consent_version, "v1")
        self.assertTrue(database.fake_connection.committed)
        self.assertFalse(database.fake_connection.rolled_back)

    def test_refresh_rotation_calls_package_and_returns_user(self) -> None:
        database = FakeDatabase()
        repository = OracleAuthRepository(database)

        user = repository.rotate_refresh_token(
            "old-hash",
            "new-hash",
            expires_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(
            database.fake_connection.fake_cursor.call_name,
            "PKG_AUTH.rotacionar_refresh_token",
        )
        self.assertIsInstance(user, AuthUser)
        self.assertEqual(user.email, "person@example.com")
        self.assertTrue(database.fake_connection.committed)
        self.assertFalse(database.fake_connection.rolled_back)

    def test_google_login_calls_package_and_returns_user(self) -> None:
        database = FakeDatabase()
        repository = OracleAuthRepository(database)

        user = repository.login_google(
            "google-sub",
            "person@example.com",
            consent_version="v1",
            accepted_age=True,
            refresh_token_hash="refresh-hash",
            refresh_expires_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(
            database.fake_connection.fake_cursor.call_name,
            "PKG_AUTH.login_google",
        )
        self.assertIsInstance(user, AuthUser)
        self.assertEqual(user.id, 7)
        self.assertEqual(user.email, "person@example.com")
        self.assertTrue(database.fake_connection.committed)
        self.assertFalse(database.fake_connection.rolled_back)


if __name__ == "__main__":
    unittest.main()
