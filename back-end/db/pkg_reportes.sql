CREATE OR REPLACE PACKAGE pkg_reportes AS
    PROCEDURE registrar_reporte(
        p_id IN reports.id%TYPE,
        p_user_id IN reports.user_id%TYPE,
        p_requester_user_id IN users.id%TYPE,
        p_category IN reports.category%TYPE,
        p_description IN reports.description%TYPE,
        p_lat IN reports.lat%TYPE,
        p_lon IN reports.lon%TYPE,
        p_geohash IN reports.geohash%TYPE,
        p_client_at IN reports.client_created_at%TYPE,
        p_correlation IN reports.correlation_id%TYPE,
        p_push_token IN notification_links.push_token%TYPE,
        p_has_photo IN NUMBER,
        p_protocol OUT reports.protocol%TYPE,
        p_created OUT NUMBER
    );

    PROCEDURE confirmar(
        p_report_id IN reports.id%TYPE,
        p_user_id IN users.id%TYPE,
        p_confirmation_count OUT report_groups.confirmation_count%TYPE
    );

    PROCEDURE criar_comentario(
        p_report_id IN report_comments.report_id%TYPE,
        p_user_id IN report_comments.user_id%TYPE,
        p_content IN report_comments.content%TYPE,
        p_comment_id OUT report_comments.id%TYPE
    );

    PROCEDURE registrar_classificacao(
        p_report_id IN reports.id%TYPE,
        p_payload IN CLOB
    );

    PROCEDURE finalizar_foto(
        p_report_id IN reports.id%TYPE,
        p_photo_key IN reports.photo_key%TYPE
    );

    FUNCTION gerar_protocolo RETURN VARCHAR2;

    -- Estado de triagem derivado dos eventos (fonte de verdade). Em moderação
    -- enquanto houver sinalização/envio à moderação sem decisão posterior;
    -- fora disso, vale o último evento de triagem.
    FUNCTION estado_triagem(p_report_id IN reports.id%TYPE) RETURN VARCHAR2;

    -- Grava estado_triagem em reports.triage_state (lida por mapa, fila,
    -- moderação e detalhe). Chame após inserir qualquer evento de triagem.
    PROCEDURE sincronizar_triagem(p_report_id IN reports.id%TYPE);
END pkg_reportes;
/

CREATE OR REPLACE PACKAGE BODY pkg_reportes AS
    c_alfabeto CONSTANT VARCHAR2(31) :=
        '23456789ABCDEFGHJKMNPQRSTUVWXYZ';

    FUNCTION gerar_protocolo RETURN VARCHAR2 IS
        v_sufixo VARCHAR2(6);
    BEGIN
        FOR i IN 1 .. 6 LOOP
            v_sufixo := v_sufixo || SUBSTR(
                c_alfabeto,
                TRUNC(DBMS_RANDOM.VALUE(1, LENGTH(c_alfabeto) + 1)),
                1
            );
        END LOOP;

        RETURN 'RPT-' || TO_CHAR(SYSDATE, 'YYYY') || '-' || v_sufixo;
    END gerar_protocolo;

    PROCEDURE registrar_reporte(
        p_id IN reports.id%TYPE,
        p_user_id IN reports.user_id%TYPE,
        p_requester_user_id IN users.id%TYPE,
        p_category IN reports.category%TYPE,
        p_description IN reports.description%TYPE,
        p_lat IN reports.lat%TYPE,
        p_lon IN reports.lon%TYPE,
        p_geohash IN reports.geohash%TYPE,
        p_client_at IN reports.client_created_at%TYPE,
        p_correlation IN reports.correlation_id%TYPE,
        p_push_token IN notification_links.push_token%TYPE,
        p_has_photo IN NUMBER,
        p_protocol OUT reports.protocol%TYPE,
        p_created OUT NUMBER
    ) IS
        v_existing_user reports.user_id%TYPE;
        v_existing_requester users.id%TYPE;
        v_group_id report_groups.id%TYPE;
        v_attempts PLS_INTEGER := 0;
    BEGIN
        IF p_requester_user_id IS NULL THEN
            RAISE_APPLICATION_ERROR(-20012, 'requester_user_id obrigatório');
        END IF;

        IF p_user_id IS NOT NULL AND p_user_id != p_requester_user_id THEN
            RAISE_APPLICATION_ERROR(-20012, 'user_id inválido');
        END IF;

        IF p_client_at > SYSTIMESTAMP + INTERVAL '1' MINUTE
           OR p_client_at < SYSTIMESTAMP - INTERVAL '30' DAY THEN
            RAISE_APPLICATION_ERROR(
                -20010,
                'client_created_at fora da janela'
            );
        END IF;

        BEGIN
            INSERT INTO report_groups (
                canonical_report_id,
                member_count,
                confirmation_count
            )
            VALUES (p_id, 1, 0)
            RETURNING id INTO v_group_id;
        EXCEPTION
            WHEN DUP_VAL_ON_INDEX THEN
                BEGIN
                    SELECT protocol, user_id
                    INTO p_protocol, v_existing_user
                    FROM reports
                    WHERE id = p_id;
                    SELECT user_id
                    INTO v_existing_requester
                    FROM notification_links
                    WHERE report_id = p_id;
                EXCEPTION
                    WHEN NO_DATA_FOUND THEN
                        RAISE;
                END;

                IF NVL(v_existing_requester, -1) != p_requester_user_id
                   OR NVL(v_existing_user, -1) != NVL(p_user_id, -1) THEN
                    RAISE_APPLICATION_ERROR(
                        -20011,
                        'id do reporte pertence a outra conta'
                    );
                END IF;

                p_created := 0;
                RETURN;
        END;

        LOOP
            p_protocol := gerar_protocolo;
            BEGIN
                INSERT INTO reports (
                    id,
                    protocol,
                    user_id,
                    group_id,
                    category,
                    description,
                    lat,
                    lon,
                    geohash,
                    client_created_at,
                    received_at,
                    correlation_id,
                    has_photo
                ) VALUES (
                    p_id,
                    p_protocol,
                    p_user_id,
                    v_group_id,
                    p_category,
                    p_description,
                    p_lat,
                    p_lon,
                    p_geohash,
                    p_client_at,
                    SYSTIMESTAMP,
                    p_correlation,
                    p_has_photo
                );
                p_created := 1;
                EXIT;
            EXCEPTION
                WHEN DUP_VAL_ON_INDEX THEN
                    BEGIN
                        SELECT protocol, user_id
                        INTO p_protocol, v_existing_user
                        FROM reports
                        WHERE id = p_id;
                        SELECT user_id
                        INTO v_existing_requester
                        FROM notification_links
                        WHERE report_id = p_id;
                    EXCEPTION
                        WHEN NO_DATA_FOUND THEN
                            v_attempts := v_attempts + 1;
                            IF v_attempts >= 5 THEN
                                RAISE;
                            END IF;
                            CONTINUE;
                    END;

                    IF NVL(v_existing_requester, -1) != p_requester_user_id
                       OR NVL(v_existing_user, -1) != NVL(p_user_id, -1) THEN
                        RAISE_APPLICATION_ERROR(
                            -20011,
                            'id do reporte pertence a outra conta'
                        );
                    END IF;

                    p_created := 0;
                    RETURN;
            END;
        END LOOP;

        INSERT INTO report_events (report_id, type, actor)
        VALUES (p_id, 'recebido', 'system');

        IF p_requester_user_id IS NOT NULL THEN
            INSERT INTO notification_links (report_id, user_id, push_token)
            VALUES (p_id, p_requester_user_id, p_push_token);
        END IF;

        IF p_has_photo = 0 THEN
            INSERT INTO job_queue (report_id, etapa)
            VALUES (p_id, 'classificar');
        END IF;
    END registrar_reporte;

    PROCEDURE finalizar_foto(
        p_report_id IN reports.id%TYPE,
        p_photo_key IN reports.photo_key%TYPE
    ) IS
        v_existing_key reports.photo_key%TYPE;
    BEGIN
        BEGIN
            SELECT photo_key
            INTO v_existing_key
            FROM reports
            WHERE id = p_report_id
              AND has_photo = 1
            FOR UPDATE;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(
                    -20045,
                    'Reporte não encontrado ou sem foto'
                );
        END;

        IF v_existing_key IS NOT NULL AND v_existing_key != p_photo_key THEN
            RAISE_APPLICATION_ERROR(-20046, 'Foto já finalizada');
        END IF;

        UPDATE reports
        SET photo_key = p_photo_key
        WHERE id = p_report_id
          AND photo_key IS NULL;
    END finalizar_foto;

    PROCEDURE confirmar(
        p_report_id IN reports.id%TYPE,
        p_user_id IN users.id%TYPE,
        p_confirmation_count OUT report_groups.confirmation_count%TYPE
    ) IS
        v_group_id reports.group_id%TYPE;
        v_requester_id users.id%TYPE;
    BEGIN
        BEGIN
            SELECT group_id
            INTO v_group_id
            FROM reports
            WHERE id = p_report_id;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20040, 'Reporte não encontrado');
        END;

        SELECT user_id
        INTO v_requester_id
        FROM notification_links
        WHERE report_id = p_report_id;

        IF v_requester_id = p_user_id THEN
            RAISE_APPLICATION_ERROR(
                -20041,
                'Autor não pode confirmar o próprio reporte'
            );
        END IF;

        BEGIN
            INSERT INTO confirmations (target_id, user_id)
            VALUES (v_group_id, p_user_id);
        EXCEPTION
            WHEN DUP_VAL_ON_INDEX THEN
                RAISE_APPLICATION_ERROR(
                    -20042,
                    'Usuário já confirmou este grupo'
                );
        END;

        UPDATE report_groups
        SET confirmation_count = confirmation_count + 1
        WHERE id = v_group_id
        RETURNING confirmation_count INTO p_confirmation_count;

        INSERT INTO report_events (report_id, type, actor)
        VALUES (
            p_report_id,
            'confirmacao_adicionada',
            'citizen:' || TO_CHAR(p_user_id)
        );
    END confirmar;

    PROCEDURE criar_comentario(
        p_report_id IN report_comments.report_id%TYPE,
        p_user_id IN report_comments.user_id%TYPE,
        p_content IN report_comments.content%TYPE,
        p_comment_id OUT report_comments.id%TYPE
    ) IS
        v_report_exists PLS_INTEGER;
    BEGIN
        SELECT COUNT(*)
        INTO v_report_exists
        FROM reports
        WHERE id = p_report_id;

        IF v_report_exists = 0 THEN
            RAISE_APPLICATION_ERROR(-20040, 'Reporte não encontrado');
        END IF;

        INSERT INTO report_comments (report_id, user_id, content)
        VALUES (p_report_id, p_user_id, p_content)
        RETURNING id INTO p_comment_id;
    END criar_comentario;

    PROCEDURE registrar_classificacao(
        p_report_id IN reports.id%TYPE,
        p_payload IN CLOB
    ) IS
        v_exists PLS_INTEGER;
        v_category VARCHAR2(32);
    BEGIN
        BEGIN
            SELECT 1
            INTO v_exists
            FROM reports
            WHERE id = p_report_id
            FOR UPDATE;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20040, 'Reporte não encontrado');
        END;

        v_category := JSON_VALUE(
            p_payload,
            '$.category' RETURNING VARCHAR2(32) ERROR ON ERROR
        );
        IF v_category NOT IN (
            'risco_urbano',
            'transporte_publico',
            'saude_atendimento',
            'a_classificar'
        ) THEN
            RAISE_APPLICATION_ERROR(-20043, 'Classificação inválida');
        END IF;

        SELECT COUNT(*)
        INTO v_exists
        FROM report_events
        WHERE report_id = p_report_id
          AND type IN (
              'classificado',
              'classificacao_confirmada',
              'classificacao_corrigida'
          );
        IF v_exists > 0 THEN
            RETURN;
        END IF;

        INSERT INTO report_events (report_id, type, actor, payload)
        VALUES (p_report_id, 'classificado', 'system', p_payload);
        sincronizar_triagem(p_report_id);
    END registrar_classificacao;

    FUNCTION estado_triagem(p_report_id IN reports.id%TYPE) RETURN VARCHAR2 IS
        v_last_flag report_events.id%TYPE;
        v_last_decision report_events.id%TYPE;
        v_type report_events.type%TYPE;
        v_actor report_events.actor%TYPE;
    BEGIN
        SELECT MAX(CASE WHEN type IN ('sinalizado', 'enviado_moderacao') THEN id END),
               MAX(CASE WHEN type IN ('moderacao_aprovada', 'moderacao_rejeitada') THEN id END)
        INTO v_last_flag, v_last_decision
        FROM report_events
        WHERE report_id = p_report_id;
        IF v_last_flag > NVL(v_last_decision, 0) THEN
            RETURN 'in_moderation';
        END IF;

        BEGIN
            SELECT type, actor
            INTO v_type, v_actor
            FROM report_events
            WHERE report_id = p_report_id
              AND type IN (
                  'classificado',
                  'classificacao_confirmada',
                  'classificacao_corrigida',
                  'vinculado_grupo',
                  'moderacao_aprovada',
                  'moderacao_rejeitada'
              )
            ORDER BY id DESC
            FETCH FIRST 1 ROW ONLY;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RETURN 'pending_classification';
        END;

        RETURN CASE
            WHEN v_type = 'classificado' THEN 'awaiting_user'
            WHEN v_type IN ('classificacao_confirmada', 'classificacao_corrigida')
                 AND v_actor = 'system' THEN 'auto_confirmed'
            WHEN v_type IN ('classificacao_confirmada', 'classificacao_corrigida')
                 THEN 'confirmed'
            WHEN v_type = 'vinculado_grupo' THEN 'auto_confirmed'
            WHEN v_type = 'moderacao_aprovada' THEN 'confirmed'
            ELSE 'rejected'
        END;
    END estado_triagem;

    PROCEDURE sincronizar_triagem(p_report_id IN reports.id%TYPE) IS
        v_state reports.triage_state%TYPE;
    BEGIN
        v_state := estado_triagem(p_report_id);
        UPDATE reports
        SET triage_state = v_state
        WHERE id = p_report_id
          AND triage_state <> v_state;
    END sincronizar_triagem;
END pkg_reportes;
/
