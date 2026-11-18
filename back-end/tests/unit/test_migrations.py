import tempfile
import unittest
from pathlib import Path

from app.infrastructure.migrations import (
    MigrationError,
    MigrationRunner,
    discover_scripts,
    split_sql_script,
)


class SplitSqlScriptTests(unittest.TestCase):
    def test_plain_statements_are_split_without_trailing_semicolon(self) -> None:
        script = """
CREATE TABLE a (id NUMBER);

CREATE INDEX ix_a ON a (id);
COMMIT;
"""
        self.assertEqual(
            split_sql_script(script),
            ["CREATE TABLE a (id NUMBER)", "CREATE INDEX ix_a ON a (id)", "COMMIT"],
        )

    def test_plsql_block_ends_at_slash_and_keeps_inner_semicolons(self) -> None:
        script = """CREATE OR REPLACE PACKAGE pkg AS
    PROCEDURE p;
END pkg;
/

CREATE TABLE b (id NUMBER);
"""
        self.assertEqual(
            split_sql_script(script),
            [
                "CREATE OR REPLACE PACKAGE pkg AS\n    PROCEDURE p;\nEND pkg;",
                "CREATE TABLE b (id NUMBER)",
            ],
        )

    def test_anonymous_blocks_and_triggers_are_plsql(self) -> None:
        script = """DECLARE
    v NUMBER;
BEGIN
    NULL;
END;
/
CREATE OR REPLACE TRIGGER trg
BEFORE UPDATE ON t
FOR EACH ROW
BEGIN
    NULL;
END;
/
"""
        statements = split_sql_script(script)

        self.assertEqual(len(statements), 2)
        self.assertTrue(statements[0].startswith("DECLARE"))
        self.assertTrue(statements[0].endswith("END;"))
        self.assertTrue(statements[1].startswith("CREATE OR REPLACE TRIGGER trg"))

    def test_comment_only_chunks_are_ignored(self) -> None:
        script = "-- só comentário\n\nCREATE TABLE c (id NUMBER); -- fim\n"

        self.assertEqual(split_sql_script(script), ["CREATE TABLE c (id NUMBER)"])


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection
        self._rows: list[tuple] = []

    def execute(self, statement: str, params: dict | None = None) -> None:
        self._connection.executed.append(statement)
        normalized = " ".join(statement.split()).upper()
        if normalized.startswith("SELECT VERSION FROM SCHEMA_MIGRATIONS"):
            self._rows = [(version,) for version in self._connection.applied]
        elif normalized.startswith("INSERT INTO SCHEMA_MIGRATIONS"):
            self._connection.applied.append(params["version"])
        elif normalized.startswith("SELECT OBJECT_TYPE, OBJECT_NAME FROM USER_OBJECTS"):
            self._rows = list(self._connection.invalid_objects)
        else:
            self._rows = []
        if statement in self._connection.fail_on:
            raise RuntimeError("ORA-00942")

    def fetchall(self) -> list[tuple]:
        return self._rows

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_: object) -> None:
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.applied: list[str] = []
        self.invalid_objects: list[tuple[str, str]] = []
        self.fail_on: set[str] = set()
        self.commits = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1


class MigrationRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "migrations").mkdir()
        (self.root / "schema.sql").write_text("CREATE TABLE base (id NUMBER);\n")
        (self.root / "migrations" / "V002__add.sql").write_text(
            "ALTER TABLE base ADD (x NUMBER);\n"
        )
        (self.root / "seed_routing.sql").write_text("INSERT INTO base VALUES (1);\n")
        (self.root / "pkg_a.sql").write_text(
            "CREATE OR REPLACE PACKAGE pkg_a AS\n    PROCEDURE p;\nEND pkg_a;\n/\n"
        )
        (self.root / "jobs_scheduler.sql").write_text("BEGIN\n    NULL;\nEND;\n/\n")
        self.connection = FakeConnection()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_discover_orders_baseline_then_versioned_then_repeatables(self) -> None:
        scripts = discover_scripts(self.root)

        self.assertEqual(
            [(script.version, script.path.name) for script in scripts.versioned],
            [("001", "schema.sql"), ("002", "V002__add.sql")],
        )
        self.assertEqual(
            [script.path.name for script in scripts.repeatable],
            ["seed_routing.sql", "pkg_a.sql", "jobs_scheduler.sql"],
        )

    def test_fresh_database_applies_all_versions_and_records_them(self) -> None:
        MigrationRunner(self.connection, self.root).run()

        self.assertEqual(self.connection.applied, ["001", "002"])
        self.assertIn("CREATE TABLE base (id NUMBER)", self.connection.executed)
        self.assertIn("ALTER TABLE base ADD (x NUMBER)", self.connection.executed)

    def test_applied_versions_are_skipped_but_repeatables_always_run(self) -> None:
        self.connection.applied = ["001", "002"]

        MigrationRunner(self.connection, self.root).run()

        self.assertNotIn("CREATE TABLE base (id NUMBER)", self.connection.executed)
        self.assertIn("INSERT INTO base VALUES (1)", self.connection.executed)
        self.assertTrue(
            any(
                statement.startswith("CREATE OR REPLACE PACKAGE pkg_a")
                for statement in self.connection.executed
            )
        )

    def test_fresh_database_skips_migrations_already_in_baseline_schema(self) -> None:
        (self.root / "schema.sql").write_text(
            "-- baseline-version: 002\nCREATE TABLE base (id NUMBER, x NUMBER);\n"
        )
        (self.root / "migrations" / "V003__more.sql").write_text(
            "ALTER TABLE base ADD (y NUMBER);\n"
        )

        MigrationRunner(self.connection, self.root).run()

        self.assertEqual(self.connection.applied, ["001", "002", "003"])
        self.assertNotIn("ALTER TABLE base ADD (x NUMBER)", self.connection.executed)
        self.assertIn("ALTER TABLE base ADD (y NUMBER)", self.connection.executed)

    def test_existing_database_still_applies_migrations_after_its_version(self) -> None:
        (self.root / "schema.sql").write_text(
            "-- baseline-version: 002\nCREATE TABLE base (id NUMBER, x NUMBER);\n"
        )
        self.connection.applied = ["001"]

        MigrationRunner(self.connection, self.root).run()

        self.assertIn("ALTER TABLE base ADD (x NUMBER)", self.connection.executed)

    def test_failed_statement_stops_and_does_not_record_version(self) -> None:
        self.connection.fail_on = {"ALTER TABLE base ADD (x NUMBER)"}

        with self.assertRaises(MigrationError) as context:
            MigrationRunner(self.connection, self.root).run()

        self.assertIn("V002__add.sql", str(context.exception))
        self.assertEqual(self.connection.applied, ["001"])

    def test_invalid_objects_are_recompiled_before_validation(self) -> None:
        MigrationRunner(self.connection, self.root).run()

        executed = [" ".join(s.split()).upper() for s in self.connection.executed]
        recompile = next(
            index for index, s in enumerate(executed) if "DBMS_UTILITY.COMPILE_SCHEMA" in s
        )
        validation = next(
            index for index, s in enumerate(executed) if "FROM USER_OBJECTS" in s
        )
        self.assertIn("COMPILE_ALL => FALSE", executed[recompile])
        self.assertLess(recompile, validation)

    def test_invalid_plsql_objects_fail_the_run(self) -> None:
        self.connection.invalid_objects = [("PACKAGE BODY", "PKG_A")]

        with self.assertRaises(MigrationError) as context:
            MigrationRunner(self.connection, self.root).run()

        self.assertIn("PKG_A", str(context.exception))


if __name__ == "__main__":
    unittest.main()
