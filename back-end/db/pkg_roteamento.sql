CREATE OR REPLACE PACKAGE pkg_roteamento AS
    PROCEDURE aplicar_triagem(
        p_report_id IN reports.id%TYPE,
        p_user_id IN users.id%TYPE,
        p_action IN VARCHAR2,
        p_classification IN CLOB
    );
END pkg_roteamento;
/

CREATE OR REPLACE PACKAGE BODY pkg_roteamento AS
    PROCEDURE aplicar_triagem(
        p_report_id IN reports.id%TYPE,
        p_user_id IN users.id%TYPE,
        p_action IN VARCHAR2,
        p_classification IN CLOB
    ) IS
        v_territory_id reports.territory_id%TYPE;
        v_category reports.category%TYPE;
        v_subcategory VARCHAR2(64);
        v_agency_id agencies.agency_id%TYPE;
        v_agency_name agencies.name%TYPE;
        v_rule_id responsibility_rules.rule_id%TYPE;
        v_rule_version responsibility_rules.version%TYPE;
        v_deadline_hours responsibility_rules.deadline_hours%TYPE;
        v_deadline TIMESTAMP WITH TIME ZONE;
        v_event_type report_events.type%TYPE;
        v_status_event_id report_events.id%TYPE;
        v_payload CLOB;
        v_exists PLS_INTEGER;
        v_actor report_events.actor%TYPE;
    BEGIN
        -- 'auto': confirmação automática pelo sistema após
        -- TRIAGE_AUTO_CONFIRM_MINUTES (D10), sem usuário.
        IF p_action NOT IN ('confirm', 'correct', 'auto')
           OR (p_action = 'auto' AND p_user_id IS NOT NULL)
           OR (p_action <> 'auto' AND p_user_id IS NULL) THEN
            RAISE_APPLICATION_ERROR(-20044, 'Ação de triagem inválida');
        END IF;

        BEGIN
            SELECT territory_id
            INTO v_territory_id
            FROM reports
            WHERE id = p_report_id
            FOR UPDATE;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20040, 'Reporte não encontrado');
        END;

        IF p_action <> 'auto' THEN
            SELECT COUNT(*)
            INTO v_exists
            FROM notification_links
            WHERE report_id = p_report_id
              AND user_id = p_user_id;
            IF v_exists = 0 THEN
                RAISE_APPLICATION_ERROR(-20041, 'Solicitante não autorizado');
            END IF;
        END IF;

        SELECT COUNT(*)
        INTO v_exists
        FROM report_events
        WHERE report_id = p_report_id
          AND type = 'classificado';
        IF v_exists = 0 THEN
            RAISE_APPLICATION_ERROR(-20043, 'Reporte ainda não classificado');
        END IF;

        SELECT COUNT(*)
        INTO v_exists
        FROM report_events
        WHERE report_id = p_report_id
          AND type IN (
              'classificacao_confirmada',
              'classificacao_corrigida',
              'enviado_moderacao',
              'vinculado_grupo'
          );
        IF v_exists > 0 THEN
            RAISE_APPLICATION_ERROR(-20043, 'Triagem já concluída');
        END IF;

        v_category := JSON_VALUE(
            p_classification,
            '$.category' RETURNING VARCHAR2(32) ERROR ON ERROR
        );
        v_subcategory := JSON_VALUE(
            p_classification,
            '$.subcategory' RETURNING VARCHAR2(64) NULL ON ERROR
        );
        IF v_category NOT IN (
            'risco_urbano',
            'transporte_publico',
            'saude_atendimento',
            'a_classificar'
        ) THEN
            RAISE_APPLICATION_ERROR(-20043, 'Categoria de triagem inválida');
        END IF;

        v_event_type := CASE
            WHEN p_action = 'correct' THEN 'classificacao_corrigida'
            ELSE 'classificacao_confirmada'
        END;
        v_actor := CASE
            WHEN p_action = 'auto' THEN 'system'
            ELSE 'citizen:' || TO_CHAR(p_user_id)
        END;
        INSERT INTO report_events (report_id, type, actor, payload)
        VALUES (
            p_report_id,
            v_event_type,
            v_actor,
            p_classification
        );

        BEGIN
            SELECT r.rule_id,
                   r.version,
                   r.deadline_hours,
                   r.agency_id,
                   a.name
            INTO v_rule_id,
                 v_rule_version,
                 v_deadline_hours,
                 v_agency_id,
                 v_agency_name
            FROM responsibility_rules r
            JOIN agencies a ON a.agency_id = r.agency_id
            WHERE r.territory_id = v_territory_id
              AND r.category = v_category
              AND (r.subcategory = v_subcategory OR r.subcategory IS NULL)
              AND r.active = 1
              AND a.active = 1
              AND SYSTIMESTAMP >= r.valid_from
              AND (r.valid_to IS NULL OR SYSTIMESTAMP < r.valid_to)
            ORDER BY
                CASE WHEN r.subcategory IS NOT NULL THEN 0 ELSE 1 END,
                r.version DESC
            FETCH FIRST 1 ROW ONLY;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                INSERT INTO report_events (report_id, type, actor, payload)
                VALUES (
                    p_report_id,
                    'enviado_moderacao',
                    'system',
                    p_classification
                );
                RETURN;
        END;

        v_deadline := SYSTIMESTAMP
            + NUMTODSINTERVAL(v_deadline_hours, 'HOUR');
        SELECT JSON_OBJECT(
                   'rule_id' VALUE v_rule_id,
                   'rule_version' VALUE v_rule_version,
                   'territory_id' VALUE v_territory_id,
                   'agency_id' VALUE v_agency_id,
                   'agency_name' VALUE v_agency_name
                   RETURNING CLOB
               )
        INTO v_payload
        FROM dual;

        INSERT INTO report_events (
            report_id, type, actor, deadline, payload
        ) VALUES (
            p_report_id,
            'encaminhado',
            'system',
            v_deadline,
            v_payload
        ) RETURNING id INTO v_status_event_id;

        pkg_jobs.enfileirar(p_report_id, 'notify_agency');
        pkg_jobs.enfileirar(
            p_report_id,
            'notify_status_' || TO_CHAR(v_status_event_id)
        );
    END aplicar_triagem;
END pkg_roteamento;
/
