ALTER TABLE job_queue ADD (
    locked_by VARCHAR2(128),
    lease_until TIMESTAMP WITH TIME ZONE,
    last_error VARCHAR2(256)
);

ALTER TABLE job_queue ADD CONSTRAINT ck_job_queue_status CHECK (
    status IN ('pending', 'processing', 'completed', 'failed')
);

ALTER TABLE job_queue ADD CONSTRAINT ck_job_queue_attempts CHECK (attempts >= 0);

DROP INDEX ix_job_queue_status_run;

CREATE INDEX ix_job_queue_status_run
    ON job_queue (status, next_run_at, lease_until, id);

COMMIT;
