MERGE INTO territories target
USING (
    SELECT 'municipio_demo' territory_id, 'Município Demo' name FROM dual
) source
ON (target.territory_id = source.territory_id)
WHEN MATCHED THEN UPDATE SET target.name = source.name, target.active = 1
WHEN NOT MATCHED THEN
    INSERT (territory_id, name, active)
    VALUES (source.territory_id, source.name, 1);

MERGE INTO agencies target
USING (
    SELECT 'prefeitura-demo-zeladoria' agency_id,
           'Prefeitura Demo — Zeladoria' name,
           'zeladoria@example.org' contact_email
    FROM dual
) source
ON (target.agency_id = source.agency_id)
WHEN MATCHED THEN
    UPDATE SET target.name = source.name, target.contact_email = source.contact_email,
               target.active = 1
WHEN NOT MATCHED THEN
    INSERT (agency_id, name, contact_email, active)
    VALUES (source.agency_id, source.name, source.contact_email, 1);

MERGE INTO agencies target
USING (
    SELECT 'saneamento-demo' agency_id,
           'Saneamento Demo' name,
           'saneamento@example.org' contact_email
    FROM dual
) source
ON (target.agency_id = source.agency_id)
WHEN MATCHED THEN
    UPDATE SET target.name = source.name, target.contact_email = source.contact_email,
               target.active = 1
WHEN NOT MATCHED THEN
    INSERT (agency_id, name, contact_email, active)
    VALUES (source.agency_id, source.name, source.contact_email, 1);

MERGE INTO agencies target
USING (
    SELECT 'operadora-demo' agency_id,
           'Operadora Demo' name,
           'transporte@example.org' contact_email
    FROM dual
) source
ON (target.agency_id = source.agency_id)
WHEN MATCHED THEN
    UPDATE SET target.name = source.name, target.contact_email = source.contact_email,
               target.active = 1
WHEN NOT MATCHED THEN
    INSERT (agency_id, name, contact_email, active)
    VALUES (source.agency_id, source.name, source.contact_email, 1);

MERGE INTO agencies target
USING (
    SELECT 'ouvidoria-saude-demo' agency_id,
           'Ouvidoria Demo — Saúde' name,
           'saude@example.org' contact_email
    FROM dual
) source
ON (target.agency_id = source.agency_id)
WHEN MATCHED THEN
    UPDATE SET target.name = source.name, target.contact_email = source.contact_email,
               target.active = 1
WHEN NOT MATCHED THEN
    INSERT (agency_id, name, contact_email, active)
    VALUES (source.agency_id, source.name, source.contact_email, 1);

MERGE INTO responsibility_rules target
USING (
    SELECT 'risco-urbano-geral' rule_id, 1 version, 'municipio_demo' territory_id,
           'risco_urbano' category, CAST(NULL AS VARCHAR2(64)) subcategory,
           'prefeitura-demo-zeladoria' agency_id, 72 deadline_hours
    FROM dual
    UNION ALL
    SELECT 'esgoto-saneamento', 1, 'municipio_demo', 'risco_urbano',
           'esgoto_vazamento', 'saneamento-demo', 120 FROM dual
    UNION ALL
    SELECT 'transporte-operadora', 1, 'municipio_demo', 'transporte_publico',
           CAST(NULL AS VARCHAR2(64)), 'operadora-demo', 72 FROM dual
    UNION ALL
    SELECT 'saude-ouvidoria', 1, 'municipio_demo', 'saude_atendimento',
           CAST(NULL AS VARCHAR2(64)), 'ouvidoria-saude-demo', 240 FROM dual
) source
ON (target.rule_id = source.rule_id AND target.version = source.version)
WHEN MATCHED THEN
    UPDATE SET target.territory_id = source.territory_id,
               target.category = source.category,
               target.subcategory = source.subcategory,
               target.agency_id = source.agency_id,
               target.deadline_hours = source.deadline_hours,
               target.valid_from = TO_TIMESTAMP_TZ(
                   '2026-01-01 00:00:00 +00:00',
                   'YYYY-MM-DD HH24:MI:SS TZH:TZM'
               ),
               target.valid_to = NULL,
               target.active = 1
WHEN NOT MATCHED THEN
    INSERT (
        rule_id, version, territory_id, category, subcategory, agency_id,
        deadline_hours, valid_from, active
    )
    VALUES (
        source.rule_id, source.version, source.territory_id, source.category,
        source.subcategory, source.agency_id, source.deadline_hours,
        TO_TIMESTAMP_TZ(
            '2026-01-01 00:00:00 +00:00',
            'YYYY-MM-DD HH24:MI:SS TZH:TZM'
        ),
        1
    );

COMMIT;
