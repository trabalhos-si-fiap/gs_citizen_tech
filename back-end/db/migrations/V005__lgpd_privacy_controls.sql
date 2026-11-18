ALTER TABLE report_comments MODIFY user_id NUMBER NULL;

DROP TRIGGER trg_reports_immutable;
DROP TRIGGER trg_report_comments_immutable;

CREATE OR REPLACE TRIGGER trg_reports_privacy_updates
BEFORE UPDATE ON reports
FOR EACH ROW
BEGIN
    IF :NEW.user_id != :OLD.user_id
       AND :NEW.user_id IS NULL
       AND :NEW.description = :OLD.description
       AND :NEW.category = :OLD.category
       AND :NEW.lat = :OLD.lat
       AND :NEW.lon = :OLD.lon
       AND :NEW.triage_state = :OLD.triage_state
    THEN
        NULL;
    ELSE
        RAISE_APPLICATION_ERROR(-20100, 'Reports are immutable.');
    END IF;
END;
/
