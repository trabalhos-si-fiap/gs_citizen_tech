ALTER TABLE job_queue MODIFY (etapa VARCHAR2(64));

CREATE TABLE notification_devices (
    push_token VARCHAR2(512) PRIMARY KEY,
    user_id NUMBER NOT NULL,
    platform VARCHAR2(16) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT fk_notification_devices_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_notification_devices_platform CHECK (
        platform IN ('android', 'ios')
    )
);

CREATE INDEX ix_notification_devices_user ON notification_devices (user_id);

COMMIT;
