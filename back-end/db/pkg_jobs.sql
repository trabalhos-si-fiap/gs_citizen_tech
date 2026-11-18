CREATE OR REPLACE PACKAGE pkg_jobs AS
    PROCEDURE enfileirar(
        p_report_id IN reports.id%TYPE,
        p_etapa IN job_queue.etapa%TYPE
    );

    PROCEDURE reservar_proximo(
        p_worker_id IN job_queue.locked_by%TYPE,
        p_lease_seconds IN NUMBER,
        p_job_id OUT job_queue.id%TYPE,
        p_report_id OUT job_queue.report_id%TYPE,
        p_etapa OUT job_queue.etapa%TYPE,
        p_attempts OUT job_queue.attempts%TYPE
    );

    PROCEDURE concluir(
        p_job_id IN job_queue.id%TYPE,
        p_worker_id IN job_queue.locked_by%TYPE
    );

    PROCEDURE falhar(
        p_job_id IN job_queue.id%TYPE,
        p_worker_id IN job_queue.locked_by%TYPE,
        p_error IN job_queue.last_error%TYPE,
        p_max_attempts IN NUMBER
    );

    PROCEDURE enviar_moderacao(
        p_report_id IN reports.id%TYPE,
        p_reason IN VARCHAR2 DEFAULT 'classification_job_failed'
    );
END pkg_jobs;
/

CREATE OR REPLACE PACKAGE BODY pkg_jobs AS
    PROCEDURE enfileirar(
        p_report_id IN reports.id%TYPE,
        p_etapa IN job_queue.etapa%TYPE
    ) IS
    BEGIN
        INSERT INTO job_queue (report_id, etapa)
        VALUES (p_report_id, p_etapa);
    EXCEPTION
        WHEN DUP_VAL_ON_INDEX THEN
            NULL;
    END enfileirar;

    PROCEDURE reservar_proximo(
        p_worker_id IN job_queue.locked_by%TYPE,
        p_lease_seconds IN NUMBER,
        p_job_id OUT job_queue.id%TYPE,
        p_report_id OUT job_queue.report_id%TYPE,
        p_etapa OUT job_queue.etapa%TYPE,
        p_attempts OUT job_queue.attempts%TYPE
    ) IS
        CURSOR c_jobs IS
            SELECT id, report_id, etapa, attempts
            FROM job_queue
            WHERE (
                  etapa IN (
                      'classificar',
                      'process_photo',
                      'notify_agency',
                      'notify_overdue'
                  )
                  OR SUBSTR(etapa, 1, 14) = 'notify_status_'
              )
              AND (
                  (status = 'pending' AND next_run_at <= SYSTIMESTAMP)
                  OR
                  (status = 'processing' AND lease_until <= SYSTIMESTAMP)
              )
            ORDER BY next_run_at, id
            FOR UPDATE SKIP LOCKED;
        v_attempts job_queue.attempts%TYPE;
    BEGIN
        p_job_id := NULL;
        p_report_id := NULL;
        p_etapa := NULL;
        p_attempts := NULL;

        OPEN c_jobs;
        FETCH c_jobs INTO p_job_id, p_report_id, p_etapa, v_attempts;
        IF c_jobs%NOTFOUND THEN
            CLOSE c_jobs;
            RETURN;
        END IF;

        p_attempts := v_attempts + 1;
        UPDATE job_queue
        SET status = 'processing',
            attempts = p_attempts,
            locked_by = p_worker_id,
            lease_until = SYSTIMESTAMP
                + NUMTODSINTERVAL(p_lease_seconds, 'SECOND'),
            last_error = NULL
        WHERE CURRENT OF c_jobs;
        CLOSE c_jobs;
    END reservar_proximo;

    PROCEDURE concluir(
        p_job_id IN job_queue.id%TYPE,
        p_worker_id IN job_queue.locked_by%TYPE
    ) IS
        v_existing PLS_INTEGER;
    BEGIN
        UPDATE job_queue
        SET status = 'completed',
            locked_by = NULL,
            lease_until = NULL,
            last_error = NULL
        WHERE id = p_job_id
          AND status = 'processing'
          AND locked_by = p_worker_id;

        IF SQL%ROWCOUNT = 0 THEN
            SELECT COUNT(*)
            INTO v_existing
            FROM job_queue
            WHERE id = p_job_id
              AND status = 'completed';
            IF v_existing = 0 THEN
                RAISE_APPLICATION_ERROR(-20044, 'Job não pertence ao worker');
            END IF;
        END IF;
    END concluir;

    PROCEDURE enviar_moderacao(
        p_report_id IN reports.id%TYPE,
        p_reason IN VARCHAR2
    ) IS
        v_existing_events PLS_INTEGER;
    BEGIN
        SELECT COUNT(*)
        INTO v_existing_events
        FROM report_events
        WHERE report_id = p_report_id
          AND type = 'enviado_moderacao';
        IF v_existing_events = 0 THEN
            INSERT INTO report_events (
                report_id, type, actor, payload
            ) VALUES (
                p_report_id,
                'enviado_moderacao',
                'system',
                JSON_OBJECT(
                    'reason' VALUE p_reason
                    RETURNING CLOB
                )
            );
        END IF;
    END enviar_moderacao;

    PROCEDURE falhar(
        p_job_id IN job_queue.id%TYPE,
        p_worker_id IN job_queue.locked_by%TYPE,
        p_error IN job_queue.last_error%TYPE,
        p_max_attempts IN NUMBER
    ) IS
        v_report_id job_queue.report_id%TYPE;
        v_etapa job_queue.etapa%TYPE;
        v_attempts job_queue.attempts%TYPE;
        v_delay_minutes PLS_INTEGER;
    BEGIN
        BEGIN
            SELECT report_id, etapa, attempts
            INTO v_report_id, v_etapa, v_attempts
            FROM job_queue
            WHERE id = p_job_id
              AND status = 'processing'
              AND locked_by = p_worker_id
            FOR UPDATE;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20044, 'Job não pertence ao worker');
        END;

        IF v_attempts >= p_max_attempts THEN
            UPDATE job_queue
            SET status = 'failed',
                locked_by = NULL,
                lease_until = NULL,
                last_error = SUBSTR(p_error, 1, 256)
            WHERE id = p_job_id;

            IF v_etapa = 'classificar' THEN
                enviar_moderacao(v_report_id);
            ELSIF v_etapa = 'notify_agency' THEN
                enviar_moderacao(v_report_id, 'agency_notification_failed');
            END IF;
            RETURN;
        END IF;

        v_delay_minutes := CASE v_attempts
            WHEN 1 THEN 1
            WHEN 2 THEN 5
            WHEN 3 THEN 15
            ELSE 60
        END;
        UPDATE job_queue
        SET status = 'pending',
            next_run_at = SYSTIMESTAMP
                + NUMTODSINTERVAL(v_delay_minutes, 'MINUTE'),
            locked_by = NULL,
            lease_until = NULL,
            last_error = SUBSTR(p_error, 1, 256)
        WHERE id = p_job_id;
    END falhar;
END pkg_jobs;
/
