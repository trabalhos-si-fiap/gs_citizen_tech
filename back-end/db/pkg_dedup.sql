CREATE OR REPLACE PACKAGE pkg_dedup AS
    -- Vincula um reporte recém-classificado ao grupo de um reporte equivalente
    -- (RT-36, RT-37). A busca e a comparação de texto ficam na API.
    PROCEDURE vincular(
        p_report_id IN reports.id%TYPE,
        p_group_id IN report_groups.id%TYPE,
        p_similarity IN NUMBER,
        p_distance_m IN NUMBER
    );
END pkg_dedup;
/

CREATE OR REPLACE PACKAGE BODY pkg_dedup AS
    PROCEDURE vincular(
        p_report_id IN reports.id%TYPE,
        p_group_id IN report_groups.id%TYPE,
        p_similarity IN NUMBER,
        p_distance_m IN NUMBER
    ) IS
        v_old_group report_groups.id%TYPE;
        v_canonical report_groups.canonical_report_id%TYPE;
        v_members report_groups.member_count%TYPE;
        v_exists PLS_INTEGER;
        v_payload CLOB;
    BEGIN
        BEGIN
            SELECT group_id
            INTO v_old_group
            FROM reports
            WHERE id = p_report_id
            FOR UPDATE;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20040, 'Reporte não encontrado');
        END;

        -- Só antes da triagem: depois dela o reporte já seguiu seu próprio fluxo.
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
        IF v_exists > 0 OR v_old_group = p_group_id THEN
            RAISE_APPLICATION_ERROR(-20043, 'Triagem já concluída');
        END IF;

        BEGIN
            SELECT canonical_report_id
            INTO v_canonical
            FROM report_groups
            WHERE id = p_group_id
            FOR UPDATE;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20040, 'Grupo não encontrado');
        END;

        SELECT member_count
        INTO v_members
        FROM report_groups
        WHERE id = v_old_group
        FOR UPDATE;

        -- Confirmações do grupo antigo migram para o novo, sem duplicar usuário.
        INSERT INTO confirmations (target_id, user_id, created_at)
        SELECT p_group_id, c.user_id, c.created_at
        FROM confirmations c
        WHERE c.target_id = v_old_group
          AND NOT EXISTS (
              SELECT 1 FROM confirmations n
              WHERE n.target_id = p_group_id AND n.user_id = c.user_id
          );
        DELETE FROM confirmations WHERE target_id = v_old_group;

        UPDATE reports
        SET group_id = p_group_id,
            triage_state = 'auto_confirmed'
        WHERE id = p_report_id;

        UPDATE report_groups
        SET member_count = member_count + v_members,
            confirmation_count = (
                SELECT COUNT(*) FROM confirmations WHERE target_id = p_group_id
            )
        WHERE id = p_group_id;

        DELETE FROM report_groups WHERE id = v_old_group;

        SELECT JSON_OBJECT(
                   'group_id' VALUE p_group_id,
                   'canonical_report_id' VALUE v_canonical,
                   'similarity' VALUE ROUND(p_similarity, 2),
                   'distance_m' VALUE ROUND(p_distance_m)
                   RETURNING CLOB
               )
        INTO v_payload
        FROM dual;

        INSERT INTO report_events (report_id, type, actor, payload)
        VALUES (p_report_id, 'vinculado_grupo', 'system', v_payload);
    END vincular;
END pkg_dedup;
/
