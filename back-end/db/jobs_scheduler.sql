DECLARE
    v_job_count PLS_INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO v_job_count
    FROM user_scheduler_jobs
    WHERE job_name = 'JOB_ATRASADOS';

    IF v_job_count = 0 THEN
        DBMS_SCHEDULER.CREATE_JOB(
            job_name => 'JOB_ATRASADOS',
            job_type => 'STORED_PROCEDURE',
            job_action => 'PKG_ATENDIMENTO.MARCAR_ATRASADOS',
            start_date => SYSTIMESTAMP,
            repeat_interval => 'FREQ=MINUTELY;INTERVAL=15',
            enabled => TRUE,
            auto_drop => FALSE
        );
    ELSE
        DBMS_SCHEDULER.SET_ATTRIBUTE(
            name => 'JOB_ATRASADOS',
            attribute => 'repeat_interval',
            value => 'FREQ=MINUTELY;INTERVAL=15'
        );
        DBMS_SCHEDULER.ENABLE('JOB_ATRASADOS');
    END IF;
END;
/
