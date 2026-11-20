-- Endereço textual do reporte ("Rua Exemplo, 123 – Bairro, Cidade"), obtido
-- no aparelho por geocodificação reversa do ponto GPS. Opcional: versões
-- antigas do app não enviam e o geocodificador pode falhar. É texto livre
-- vindo do cidadão (não confiável) e, como o restante do conteúdo enviado,
-- não muda depois do registro.
ALTER TABLE reports ADD (address VARCHAR2(200 CHAR));

-- Mesmo gatilho da V007, agora protegendo também o endereço.
CREATE OR REPLACE TRIGGER trg_reports_privacy_updates
BEFORE UPDATE ON reports
FOR EACH ROW
DECLARE
    FUNCTION differs(p_new VARCHAR2, p_old VARCHAR2) RETURN BOOLEAN IS
    BEGIN
        IF p_new IS NULL AND p_old IS NULL THEN
            RETURN FALSE;
        ELSIF p_new IS NULL OR p_old IS NULL THEN
            RETURN TRUE;
        END IF;
        RETURN p_new <> p_old;
    END;

    FUNCTION differs(p_new NUMBER, p_old NUMBER) RETURN BOOLEAN IS
    BEGIN
        IF p_new IS NULL AND p_old IS NULL THEN
            RETURN FALSE;
        ELSIF p_new IS NULL OR p_old IS NULL THEN
            RETURN TRUE;
        END IF;
        RETURN p_new <> p_old;
    END;

    FUNCTION differs(
        p_new TIMESTAMP WITH TIME ZONE,
        p_old TIMESTAMP WITH TIME ZONE
    ) RETURN BOOLEAN IS
    BEGIN
        IF p_new IS NULL AND p_old IS NULL THEN
            RETURN FALSE;
        ELSIF p_new IS NULL OR p_old IS NULL THEN
            RETURN TRUE;
        END IF;
        RETURN p_new <> p_old;
    END;
BEGIN
    IF differs(:NEW.id, :OLD.id)
       OR differs(:NEW.protocol, :OLD.protocol)
       OR differs(:NEW.territory_id, :OLD.territory_id)
       OR differs(:NEW.category, :OLD.category)
       OR differs(:NEW.description, :OLD.description)
       OR differs(:NEW.address, :OLD.address)
       OR differs(:NEW.lat, :OLD.lat)
       OR differs(:NEW.lon, :OLD.lon)
       OR differs(:NEW.geohash, :OLD.geohash)
       OR differs(:NEW.client_created_at, :OLD.client_created_at)
       OR differs(:NEW.received_at, :OLD.received_at)
       OR differs(:NEW.correlation_id, :OLD.correlation_id)
       OR differs(:NEW.has_photo, :OLD.has_photo)
       -- user_id só pode ser removido (anonimização LGPD), nunca trocado.
       OR (:NEW.user_id IS NOT NULL AND differs(:NEW.user_id, :OLD.user_id))
       -- photo_key é gravada uma única vez.
       OR (:OLD.photo_key IS NOT NULL AND differs(:NEW.photo_key, :OLD.photo_key))
    THEN
        RAISE_APPLICATION_ERROR(-20100, 'Reports are immutable.');
    END IF;
END;
/
