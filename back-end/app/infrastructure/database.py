"""Pool de conexões Oracle em modo thin."""

from collections.abc import Iterator
from contextlib import contextmanager

import oracledb

from app.core.config import Settings


class OracleDatabase:
    def __init__(self, config: Settings) -> None:
        self._config = config
        self._pool: oracledb.ConnectionPool | None = None

    def open(self) -> None:
        if self._pool is not None:
            return
        if not self._config.db_user or not self._config.db_dsn:
            raise RuntimeError("DB_USER e DB_DSN são necessários para Oracle.")
        password = self._config.db_password.get_secret_value()
        if not password:
            raise RuntimeError("DB_PASSWORD é necessário para Oracle.")

        self._pool = oracledb.create_pool(
            user=self._config.db_user,
            password=password,
            dsn=self._config.db_dsn,
            min=self._config.db_pool_min,
            max=self._config.db_pool_max,
        )

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    @contextmanager
    def connection(self) -> Iterator[oracledb.Connection]:
        if self._pool is None:
            raise RuntimeError("O pool Oracle ainda não foi iniciado.")

        connection = self._pool.acquire()
        try:
            yield connection
        finally:
            self._pool.release(connection)
