CREATE TABLE audit_log (
    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_user_id NUMBER,
    action VARCHAR2(64) NOT NULL,
    resource_type VARCHAR2(64) NOT NULL,
    resource_id VARCHAR2(128),
    justification VARCHAR2(2000),
    correlation_id VARCHAR2(36),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE INDEX ix_audit_log_created ON audit_log (created_at, id);
