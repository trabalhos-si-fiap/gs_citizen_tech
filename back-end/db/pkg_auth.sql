CREATE OR REPLACE PACKAGE pkg_auth AS
    PROCEDURE solicitar_otp(
        p_email IN users.email%TYPE,
        p_code_hash IN otp_challenges.code_hash%TYPE,
        p_expires_at IN otp_challenges.expires_at%TYPE,
        p_consent_version IN users.consent_version%TYPE,
        p_accepted_age IN NUMBER
    );

    PROCEDURE validar_otp(
        p_email IN users.email%TYPE,
        p_code_hash IN otp_challenges.code_hash%TYPE,
        p_refresh_hash IN refresh_tokens.token_hash%TYPE,
        p_refresh_expires_at IN refresh_tokens.expires_at%TYPE,
        p_status OUT VARCHAR2,
        p_user_id OUT users.id%TYPE,
        p_role OUT users.role%TYPE,
        p_consent_version OUT users.consent_version%TYPE
    );

    PROCEDURE login_google(
        p_google_sub IN users.google_sub%TYPE,
        p_email IN users.email%TYPE,
        p_consent_version IN users.consent_version%TYPE,
        p_accepted_age IN NUMBER,
        p_refresh_hash IN refresh_tokens.token_hash%TYPE,
        p_refresh_expires_at IN refresh_tokens.expires_at%TYPE,
        p_status OUT VARCHAR2,
        p_user_id OUT users.id%TYPE,
        p_role OUT users.role%TYPE,
        p_stored_consent OUT users.consent_version%TYPE
    );

    PROCEDURE rotacionar_refresh_token(
        p_old_hash IN refresh_tokens.token_hash%TYPE,
        p_new_hash IN refresh_tokens.token_hash%TYPE,
        p_expires_at IN refresh_tokens.expires_at%TYPE,
        p_status OUT VARCHAR2,
        p_user_id OUT users.id%TYPE,
        p_role OUT users.role%TYPE,
        p_consent_version OUT users.consent_version%TYPE
    );
END pkg_auth;
/

CREATE OR REPLACE PACKAGE BODY pkg_auth AS
    PROCEDURE solicitar_otp(
        p_email IN users.email%TYPE,
        p_code_hash IN otp_challenges.code_hash%TYPE,
        p_expires_at IN otp_challenges.expires_at%TYPE,
        p_consent_version IN users.consent_version%TYPE,
        p_accepted_age IN NUMBER
    ) IS
        v_user_count PLS_INTEGER;
    BEGIN
        SELECT COUNT(*)
        INTO v_user_count
        FROM users
        WHERE email = p_email
          AND deleted_at IS NULL;

        IF v_user_count = 0
           AND (
               p_consent_version IS NULL
               OR p_accepted_age IS NULL
               OR p_accepted_age != 1
           ) THEN
            RAISE_APPLICATION_ERROR(
                -20020,
                'Consentimento e confirmação de idade obrigatórios'
            );
        END IF;

        MERGE INTO otp_challenges dst
        USING (SELECT p_email AS email FROM dual) src
        ON (dst.email = src.email)
        WHEN MATCHED THEN
            UPDATE SET
                code_hash = p_code_hash,
                expires_at = p_expires_at,
                attempts = 0,
                consent_version = p_consent_version,
                created_at = SYSTIMESTAMP
        WHEN NOT MATCHED THEN
            INSERT (
                email,
                code_hash,
                expires_at,
                attempts,
                consent_version
            )
            VALUES (
                p_email,
                p_code_hash,
                p_expires_at,
                0,
                p_consent_version
            );
    END solicitar_otp;

    PROCEDURE validar_otp(
        p_email IN users.email%TYPE,
        p_code_hash IN otp_challenges.code_hash%TYPE,
        p_refresh_hash IN refresh_tokens.token_hash%TYPE,
        p_refresh_expires_at IN refresh_tokens.expires_at%TYPE,
        p_status OUT VARCHAR2,
        p_user_id OUT users.id%TYPE,
        p_role OUT users.role%TYPE,
        p_consent_version OUT users.consent_version%TYPE
    ) IS
        v_code_hash otp_challenges.code_hash%TYPE;
        v_expires_at otp_challenges.expires_at%TYPE;
        v_attempts otp_challenges.attempts%TYPE;
        v_challenge_consent otp_challenges.consent_version%TYPE;
    BEGIN
        p_status := 'invalid';
        BEGIN
            SELECT code_hash, expires_at, attempts, consent_version
            INTO v_code_hash, v_expires_at, v_attempts, v_challenge_consent
            FROM otp_challenges
            WHERE email = p_email
            FOR UPDATE;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RETURN;
        END;

        IF v_expires_at <= SYSTIMESTAMP OR v_attempts >= 5 THEN
            DELETE FROM otp_challenges WHERE email = p_email;
            p_status := 'expired';
            RETURN;
        END IF;

        IF v_code_hash != p_code_hash THEN
            UPDATE otp_challenges
            SET attempts = attempts + 1
            WHERE email = p_email;
            RETURN;
        END IF;

        DELETE FROM otp_challenges WHERE email = p_email;

        BEGIN
            SELECT id, role, consent_version
            INTO p_user_id, p_role, p_consent_version
            FROM users
            WHERE email = p_email
              AND deleted_at IS NULL
            FOR UPDATE;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                INSERT INTO users (
                    email,
                    role,
                    consent_version,
                    consent_at
                )
                VALUES (
                    p_email,
                    'citizen',
                    v_challenge_consent,
                    SYSTIMESTAMP
                )
                RETURNING id, role, consent_version
                INTO p_user_id, p_role, p_consent_version;
        END;

        INSERT INTO refresh_tokens (
            token_hash,
            user_id,
            expires_at
        )
        VALUES (
            p_refresh_hash,
            p_user_id,
            p_refresh_expires_at
        );
        p_status := 'ok';
    END validar_otp;

    PROCEDURE login_google(
        p_google_sub IN users.google_sub%TYPE,
        p_email IN users.email%TYPE,
        p_consent_version IN users.consent_version%TYPE,
        p_accepted_age IN NUMBER,
        p_refresh_hash IN refresh_tokens.token_hash%TYPE,
        p_refresh_expires_at IN refresh_tokens.expires_at%TYPE,
        p_status OUT VARCHAR2,
        p_user_id OUT users.id%TYPE,
        p_role OUT users.role%TYPE,
        p_stored_consent OUT users.consent_version%TYPE
    ) IS
        v_existing_sub users.google_sub%TYPE;
        v_email_user_id users.id%TYPE;
    BEGIN
        p_status := 'conflict';
        BEGIN
            SELECT id, role, consent_version
            INTO p_user_id, p_role, p_stored_consent
            FROM users
            WHERE google_sub = p_google_sub
              AND deleted_at IS NULL
            FOR UPDATE;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                BEGIN
                    SELECT id, google_sub, role, consent_version
                    INTO p_user_id, v_existing_sub, p_role, p_stored_consent
                    FROM users
                    WHERE email = p_email
                      AND deleted_at IS NULL
                    FOR UPDATE;

                    IF v_existing_sub IS NOT NULL
                       AND v_existing_sub != p_google_sub THEN
                        RETURN;
                    END IF;

                    IF v_existing_sub IS NULL THEN
                        UPDATE users
                        SET google_sub = p_google_sub
                        WHERE id = p_user_id;
                    END IF;
                EXCEPTION
                    WHEN NO_DATA_FOUND THEN
                        IF p_consent_version IS NULL
                           OR p_accepted_age IS NULL
                           OR p_accepted_age != 1 THEN
                            p_status := 'consent_required';
                            RETURN;
                        END IF;

                        INSERT INTO users (
                            email,
                            google_sub,
                            role,
                            consent_version,
                            consent_at
                        )
                        VALUES (
                            p_email,
                            p_google_sub,
                            'citizen',
                            p_consent_version,
                            SYSTIMESTAMP
                        )
                        RETURNING id, role, consent_version
                        INTO p_user_id, p_role, p_stored_consent;
                END;
        END;

        BEGIN
            SELECT id
            INTO v_email_user_id
            FROM users
            WHERE email = p_email
              AND deleted_at IS NULL;

            IF v_email_user_id != p_user_id THEN
                p_status := 'conflict';
                RETURN;
            END IF;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                NULL;
        END;

        INSERT INTO refresh_tokens (
            token_hash,
            user_id,
            expires_at
        )
        VALUES (
            p_refresh_hash,
            p_user_id,
            p_refresh_expires_at
        );
        p_status := 'ok';
    END login_google;

    PROCEDURE rotacionar_refresh_token(
        p_old_hash IN refresh_tokens.token_hash%TYPE,
        p_new_hash IN refresh_tokens.token_hash%TYPE,
        p_expires_at IN refresh_tokens.expires_at%TYPE,
        p_status OUT VARCHAR2,
        p_user_id OUT users.id%TYPE,
        p_role OUT users.role%TYPE,
        p_consent_version OUT users.consent_version%TYPE
    ) IS
        v_user_id refresh_tokens.user_id%TYPE;
        v_old_expires_at refresh_tokens.expires_at%TYPE;
        v_revoked_at refresh_tokens.revoked_at%TYPE;
    BEGIN
        p_status := 'invalid';
        BEGIN
            SELECT user_id, expires_at, revoked_at
            INTO v_user_id, v_old_expires_at, v_revoked_at
            FROM refresh_tokens
            WHERE token_hash = p_old_hash
            FOR UPDATE;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RETURN;
        END;

        IF v_revoked_at IS NOT NULL OR v_old_expires_at <= SYSTIMESTAMP THEN
            RETURN;
        END IF;

        UPDATE refresh_tokens
        SET revoked_at = SYSTIMESTAMP
        WHERE token_hash = p_old_hash;

        SELECT id, role, consent_version
        INTO p_user_id, p_role, p_consent_version
        FROM users
        WHERE id = v_user_id
          AND deleted_at IS NULL;

        INSERT INTO refresh_tokens (
            token_hash,
            user_id,
            expires_at,
            rotated_from
        )
        VALUES (
            p_new_hash,
            p_user_id,
            p_expires_at,
            p_old_hash
        );
        p_status := 'ok';
    END rotacionar_refresh_token;
END pkg_auth;
/
