-- Provisiona um servidor municipal. O login é feito depois pelo fluxo OTP
-- normal (POST /v1/auth/login), sem senha.
--
-- Uso no SQL*Plus / SQLcl:
--   @db/provision_staff.sql servidor@prefeitura.gov.br agency prefeitura-demo-zeladoria
--   @db/provision_staff.sql gestor@prefeitura.gov.br manager -
--
-- Parâmetros: &1 = e-mail, &2 = papel (agency|manager|moderator|admin),
-- &3 = agency_id (obrigatório para 'agency'; use - para os demais papéis).
DEFINE staff_email = '&1'
DEFINE staff_role = '&2'
DEFINE staff_agency = '&3'

MERGE INTO users target
USING (SELECT LOWER('&staff_email') AS email FROM dual) source
ON (target.email = source.email AND target.deleted_at IS NULL)
WHEN MATCHED THEN UPDATE SET target.role = '&staff_role'
WHEN NOT MATCHED THEN
    INSERT (email, role) VALUES (source.email, '&staff_role');

MERGE INTO agency_operators target
USING (
    SELECT u.id AS user_id, '&staff_agency' AS agency_id
    FROM users u
    WHERE u.email = LOWER('&staff_email')
      AND u.deleted_at IS NULL
      AND '&staff_role' = 'agency'
      AND '&staff_agency' <> '-'
) source
ON (target.user_id = source.user_id)
WHEN MATCHED THEN UPDATE SET target.agency_id = source.agency_id
WHEN NOT MATCHED THEN
    INSERT (user_id, agency_id) VALUES (source.user_id, source.agency_id);

COMMIT;
