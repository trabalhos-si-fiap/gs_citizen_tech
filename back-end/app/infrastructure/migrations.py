"""Aplicação versionada dos scripts Oracle em `back-end/db`.

Ordem de execução:

1. Scripts versionados, uma única vez cada, registrados em `schema_migrations`:
   `schema.sql` (versão 001) seguido de `migrations/V<NNN>__*.sql`.
   `schema.sql` é consolidado: o cabeçalho `-- baseline-version: NNN` indica
   até qual migration ele já contém. Em banco vazio essas migrations são
   apenas registradas, sem executar; em banco existente seguem normalmente.
2. Scripts repetíveis, a cada execução, por serem idempotentes:
   `seed_routing.sql`, `pkg_*.sql` e `jobs_scheduler.sql`.
3. Recompilação dos objetos inválidos e verificação final; qualquer objeto
   ainda inválido falha a execução.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PLSQL_START = re.compile(
    r"^\s*(DECLARE|BEGIN|CREATE\s+(OR\s+REPLACE\s+)?"
    r"(EDITIONABLE\s+|NONEDITIONABLE\s+)?"
    r"(PACKAGE|PROCEDURE|FUNCTION|TRIGGER|TYPE)\b)",
    re.IGNORECASE,
)
_VERSIONED_NAME = re.compile(r"^V(\d+)__.+\.sql$")
_BASELINE_HEADER = re.compile(r"^--\s*baseline-version:\s*(\d+)\s*$", re.MULTILINE)

_CREATE_HISTORY_TABLE = """
DECLARE
    v_count PLS_INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM user_tables
    WHERE table_name = 'SCHEMA_MIGRATIONS';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE 'CREATE TABLE schema_migrations (
            version VARCHAR2(16) PRIMARY KEY,
            script VARCHAR2(255) NOT NULL,
            applied_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
        )';
    END IF;
END;"""


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SqlScript:
    path: Path
    version: str | None = None
    baseline: str | None = None


@dataclass(frozen=True)
class DiscoveredScripts:
    versioned: list[SqlScript]
    repeatable: list[SqlScript]


def _strip_line_comment(line: str) -> str:
    in_string = False
    for index, char in enumerate(line):
        if char == "'":
            in_string = not in_string
        elif not in_string and line.startswith("--", index):
            return line[:index]
    return line


def split_sql_script(script: str) -> list[str]:
    """Divide um script no estilo SQL*Plus em comandos executáveis.

    Comandos SQL terminam em `;` no fim da linha. Blocos PL/SQL terminam
    em uma linha contendo apenas `/` e preservam os `;` internos.
    """

    statements: list[str] = []
    buffer: list[str] = []
    in_plsql = False

    def flush(text: str) -> None:
        cleaned = text.strip()
        if cleaned:
            statements.append(cleaned)

    for raw_line in script.splitlines():
        if not buffer and not raw_line.strip():
            continue
        if not buffer and _PLSQL_START.match(raw_line):
            in_plsql = True

        if in_plsql:
            if raw_line.strip() == "/":
                flush("\n".join(buffer))
                buffer = []
                in_plsql = False
            else:
                buffer.append(raw_line.rstrip())
            continue

        line = _strip_line_comment(raw_line).rstrip()
        if not line.strip():
            continue
        if line.endswith(";"):
            buffer.append(line[:-1])
            flush("\n".join(buffer))
            buffer = []
        else:
            buffer.append(line)

    flush("\n".join(buffer))
    return statements


def discover_scripts(db_dir: Path) -> DiscoveredScripts:
    schema = db_dir / "schema.sql"
    header = _BASELINE_HEADER.search(schema.read_text(encoding="utf-8"))
    baseline = header.group(1).zfill(3) if header else "001"
    versioned = [SqlScript(schema, "001", baseline)]
    migrations_dir = db_dir / "migrations"
    migrations = []
    if migrations_dir.is_dir():
        for path in migrations_dir.glob("V*__*.sql"):
            match = _VERSIONED_NAME.match(path.name)
            if match:
                migrations.append(SqlScript(path, match.group(1).zfill(3)))
    versioned.extend(sorted(migrations, key=lambda script: int(script.version)))

    repeatable: list[SqlScript] = []
    seed = db_dir / "seed_routing.sql"
    if seed.is_file():
        repeatable.append(SqlScript(seed))
    repeatable.extend(SqlScript(path) for path in sorted(db_dir.glob("pkg_*.sql")))
    scheduler = db_dir / "jobs_scheduler.sql"
    if scheduler.is_file():
        repeatable.append(SqlScript(scheduler))
    return DiscoveredScripts(versioned, repeatable)


class MigrationRunner:
    def __init__(self, connection: Any, db_dir: Path) -> None:
        self._connection = connection
        self._db_dir = db_dir

    def run(self) -> list[str]:
        scripts = discover_scripts(self._db_dir)
        with self._connection.cursor() as cursor:
            cursor.execute(_CREATE_HISTORY_TABLE)
            cursor.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cursor.fetchall()}

        newly_applied: list[str] = []
        baseline = scripts.versioned[0].baseline or "001"
        fresh_database = not applied
        for script in scripts.versioned:
            if script.version in applied:
                continue
            covered = (
                fresh_database
                and script.version != "001"
                and int(script.version) <= int(baseline)
            )
            if covered:
                logger.info("%s já incluída no schema.sql.", script.path.name)
            else:
                self._apply(script)
            self._record(script)
            newly_applied.append(script.version)
            logger.info("Migração %s registrada.", script.path.name)

        for script in scripts.repeatable:
            self._apply(script)
            self._connection.commit()

        self._assert_no_invalid_objects()
        return newly_applied

    def _record(self, script: SqlScript) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO schema_migrations (version, script) "
                "VALUES (:version, :script)",
                {"version": script.version, "script": script.path.name},
            )
        self._connection.commit()

    def _apply(self, script: SqlScript) -> None:
        statements = split_sql_script(script.path.read_text(encoding="utf-8"))
        with self._connection.cursor() as cursor:
            for index, statement in enumerate(statements, start=1):
                try:
                    cursor.execute(statement)
                except Exception as error:
                    raise MigrationError(
                        f"{script.path.name}, comando {index}: {error}"
                    ) from error

    def _assert_no_invalid_objects(self) -> None:
        with self._connection.cursor() as cursor:
            # Packages são aplicados em ordem alfabética; dependentes criados
            # antes de suas dependências ficam INVALID até serem recompilados.
            cursor.execute(
                "BEGIN DBMS_UTILITY.COMPILE_SCHEMA("
                "schema => USER, compile_all => FALSE); END;"
            )
            cursor.execute(
                "SELECT object_type, object_name FROM user_objects "
                "WHERE status = 'INVALID' ORDER BY object_type, object_name"
            )
            invalid = cursor.fetchall()
        if invalid:
            names = ", ".join(f"{kind} {name}" for kind, name in invalid)
            raise MigrationError(f"Objetos PL/SQL inválidos: {names}")


def main() -> None:
    import oracledb

    from app.core.config import settings

    password = settings.db_password.get_secret_value()
    if not settings.db_user or not settings.db_dsn or not password:
        raise MigrationError("DB_USER, DB_PASSWORD e DB_DSN são obrigatórios.")

    db_dir = Path(__file__).resolve().parents[2] / "db"
    with oracledb.connect(
        user=settings.db_user,
        password=password,
        dsn=settings.db_dsn,
    ) as connection:
        applied = MigrationRunner(connection, db_dir).run()
    logger.info("Banco atualizado; versões novas: %s", applied or "nenhuma")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
