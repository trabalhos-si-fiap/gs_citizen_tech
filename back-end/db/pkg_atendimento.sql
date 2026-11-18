CREATE OR REPLACE PACKAGE pkg_atendimento AS
    PROCEDURE marcar_atrasados;
END pkg_atendimento;
/

CREATE OR REPLACE PACKAGE BODY pkg_atendimento AS
    PROCEDURE marcar_atrasados IS
        CURSOR c_overdue IS
            SELECT report_id
            FROM (
                SELECT report_id,
                       type,
                       deadline,
                       ROW_NUMBER() OVER (
                           PARTITION BY report_id
                           ORDER BY id DESC
                       ) AS row_number
                FROM report_events
                WHERE type IN (
                    'recebido',
                    'encaminhado',
                    'em_andamento',
                    'resolvido'
                )
            ) latest
            WHERE row_number = 1
              AND type IN ('encaminhado', 'em_andamento')
              AND deadline < SYSTIMESTAMP
              AND NOT EXISTS (
                  SELECT 1
                  FROM job_queue job
                  WHERE job.report_id = latest.report_id
                    AND job.etapa = 'notify_overdue'
              )
            ORDER BY report_id;
        TYPE t_report_ids IS TABLE OF reports.id%TYPE;
        v_report_ids t_report_ids;
    BEGIN
        OPEN c_overdue;
        LOOP
            FETCH c_overdue BULK COLLECT INTO v_report_ids LIMIT 500;
            EXIT WHEN v_report_ids.COUNT = 0;

            FOR i IN 1 .. v_report_ids.COUNT LOOP
                pkg_jobs.enfileirar(v_report_ids(i), 'notify_overdue');
            END LOOP;
            COMMIT;
        END LOOP;
        CLOSE c_overdue;
    EXCEPTION
        WHEN OTHERS THEN
            IF c_overdue%ISOPEN THEN
                CLOSE c_overdue;
            END IF;
            RAISE;
    END marcar_atrasados;
END pkg_atendimento;
/
