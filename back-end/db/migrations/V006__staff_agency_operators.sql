-- Vínculo entre servidores com papel 'agency' e o órgão em que atuam.
-- Papéis manager, moderator e admin enxergam todos os órgãos e não precisam
-- de vínculo. O escopo é consultado no servidor a cada requisição.
CREATE TABLE agency_operators (
    user_id NUMBER NOT NULL,
    agency_id VARCHAR2(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT pk_agency_operators PRIMARY KEY (user_id),
    CONSTRAINT fk_agency_operators_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_agency_operators_agency FOREIGN KEY (agency_id)
        REFERENCES agencies (agency_id)
);

CREATE INDEX ix_agency_operators_agency ON agency_operators (agency_id);
