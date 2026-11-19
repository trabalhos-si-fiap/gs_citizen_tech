"""Filas de jobs em memória e Oracle."""

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from app.infrastructure.database import OracleDatabase


@dataclass(frozen=True)
class ReportJob:
    id: int
    report_id: UUID
    stage: str
    attempts: int


class JobQueue(Protocol):
    handles_terminal_failure: bool

    def enqueue(self, report_id: UUID, stage: str) -> None: ...

    def reserve_next(self, worker_id: str, lease_seconds: int) -> ReportJob | None: ...

    def complete(self, job_id: int, worker_id: str) -> None: ...

    def fail(
        self,
        job_id: int,
        worker_id: str,
        error_code: str,
        max_attempts: int,
    ) -> bool: ...


@dataclass
class _QueuedJob:
    id: int
    report_id: UUID
    stage: str
    status: str
    attempts: int
    next_run_at: datetime
    locked_by: str | None = None
    lease_until: datetime | None = None
    error_code: str | None = None


class InMemoryJobQueue:
    """Fila volátil restrita ao desenvolvimento e aos testes."""

    handles_terminal_failure = False

    def __init__(self, *, clock=lambda: datetime.now(timezone.utc)) -> None:
        self._clock = clock
        self._jobs: dict[tuple[UUID, str], _QueuedJob] = {}
        self._jobs_by_id: dict[int, _QueuedJob] = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def enqueue(self, report_id: UUID, stage: str) -> None:
        with self._lock:
            key = (report_id, stage)
            if key in self._jobs:
                return
            job = _QueuedJob(
                id=self._next_id,
                report_id=report_id,
                stage=stage,
                status="pending",
                attempts=0,
                next_run_at=self._clock(),
            )
            self._next_id += 1
            self._jobs[key] = job
            self._jobs_by_id[job.id] = job

    def reserve_next(self, worker_id: str, lease_seconds: int) -> ReportJob | None:
        with self._lock:
            now = self._clock()
            candidates = [
                job
                for job in self._jobs.values()
                if (
                    job.stage in {
                        "classificar",
                        "process_photo",
                        "notify_agency",
                        "notify_overdue",
                    }
                    or job.stage.startswith("notify_status_")
                    or job.stage.startswith("notify_agency_")
                )
                and (
                    (job.status == "pending" and job.next_run_at <= now)
                    or (
                        job.status == "processing"
                        and job.lease_until is not None
                        and job.lease_until <= now
                    )
                )
            ]
            if not candidates:
                return None
            job = min(candidates, key=lambda item: (item.next_run_at, item.id))
            job.status = "processing"
            job.attempts += 1
            job.locked_by = worker_id
            job.lease_until = now + timedelta(seconds=lease_seconds)
            return ReportJob(job.id, job.report_id, job.stage, job.attempts)

    def complete(self, job_id: int, worker_id: str) -> None:
        with self._lock:
            job = self._jobs_by_id.get(job_id)
            if job is None:
                raise RuntimeError("Job inexistente.")
            if job.status == "completed":
                return
            if job.status != "processing" or job.locked_by != worker_id:
                raise RuntimeError("Job não está reservado.")
            job.status = "completed"
            job.locked_by = None
            job.lease_until = None
            job.error_code = None

    def fail(
        self,
        job_id: int,
        worker_id: str,
        error_code: str,
        max_attempts: int,
    ) -> bool:
        with self._lock:
            job = self._jobs_by_id.get(job_id)
            if (
                job is None
                or job.status != "processing"
                or job.locked_by != worker_id
            ):
                raise RuntimeError("Job não está reservado.")
            job.error_code = error_code[:256]
            job.locked_by = None
            job.lease_until = None
            if job.attempts >= max_attempts:
                job.status = "failed"
                return True

            delay_minutes = {1: 1, 2: 5, 3: 15}.get(job.attempts, 60)
            job.status = "pending"
            job.next_run_at = self._clock() + timedelta(minutes=delay_minutes)
            return False


class OracleJobQueue:
    """Adaptador para jobs duráveis reservados com lease e SKIP LOCKED."""

    handles_terminal_failure = True

    def __init__(self, database: OracleDatabase) -> None:
        self._database = database

    def enqueue(self, report_id: UUID, stage: str) -> None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.callproc(
                    "PKG_JOBS.enfileirar",
                    [str(report_id), stage],
                )
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def reserve_next(self, worker_id: str, lease_seconds: int) -> ReportJob | None:
        import oracledb

        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                job_id = cursor.var(oracledb.DB_TYPE_NUMBER)
                report_id = cursor.var(oracledb.DB_TYPE_VARCHAR, size=36)
                stage = cursor.var(oracledb.DB_TYPE_VARCHAR, size=64)
                attempts = cursor.var(oracledb.DB_TYPE_NUMBER)
                cursor.callproc(
                    "PKG_JOBS.reservar_proximo",
                    [
                        worker_id,
                        lease_seconds,
                        job_id,
                        report_id,
                        stage,
                        attempts,
                    ],
                )
                connection.commit()
                committed = True
                reserved_id = job_id.getvalue()
                if reserved_id is None:
                    return None
                return ReportJob(
                    id=int(reserved_id),
                    report_id=UUID(report_id.getvalue()),
                    stage=stage.getvalue(),
                    attempts=int(attempts.getvalue()),
                )
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()

    def complete(self, job_id: int, worker_id: str) -> None:
        self._call_job_procedure(
            "PKG_JOBS.concluir",
            [job_id, worker_id],
        )

    def fail(
        self,
        job_id: int,
        worker_id: str,
        error_code: str,
        max_attempts: int,
    ) -> bool:
        self._call_job_procedure(
            "PKG_JOBS.falhar",
            [job_id, worker_id, error_code[:256], max_attempts],
        )
        return False

    def _call_job_procedure(self, name: str, parameters: list[object]) -> None:
        with self._database.connection() as connection:
            cursor = connection.cursor()
            committed = False
            try:
                cursor.callproc(name, parameters)
                connection.commit()
                committed = True
            finally:
                cursor.close()
                if not committed:
                    connection.rollback()
