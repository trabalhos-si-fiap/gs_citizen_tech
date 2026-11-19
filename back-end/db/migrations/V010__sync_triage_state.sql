-- reports.triage_state divergia dos eventos: PKG_ROTEAMENTO, PKG_JOBS e
-- PKG_REPORTES gravavam eventos de triagem sem atualizar a coluna. Agora os
-- pacotes chamam pkg_reportes.sincronizar_triagem; esta migration recalcula a
-- coluna dos reportes existentes com a mesma regra de
-- pkg_reportes.estado_triagem (as migrations rodam antes dos pacotes, então a
-- regra é repetida aqui em SQL):
--   1. sinalização/envio à moderação sem decisão posterior -> in_moderation;
--   2. senão, o último evento de triagem decide;
--   3. sem evento de triagem -> pending_classification.
MERGE INTO reports target
USING (
    SELECT r.id,
           CASE
               WHEN flags.last_flag > NVL(flags.last_decision, 0)
                   THEN 'in_moderation'
               WHEN last_event.type IS NULL THEN 'pending_classification'
               WHEN last_event.type = 'classificado' THEN 'awaiting_user'
               WHEN last_event.type IN ('classificacao_confirmada', 'classificacao_corrigida')
                    AND last_event.actor = 'system' THEN 'auto_confirmed'
               WHEN last_event.type IN ('classificacao_confirmada', 'classificacao_corrigida')
                   THEN 'confirmed'
               WHEN last_event.type = 'vinculado_grupo' THEN 'auto_confirmed'
               WHEN last_event.type = 'moderacao_aprovada' THEN 'confirmed'
               ELSE 'rejected'
           END AS triage_state
    FROM reports r
    OUTER APPLY (
        SELECT MAX(CASE WHEN e.type IN ('sinalizado', 'enviado_moderacao') THEN e.id END) AS last_flag,
               MAX(CASE WHEN e.type IN ('moderacao_aprovada', 'moderacao_rejeitada') THEN e.id END) AS last_decision
        FROM report_events e
        WHERE e.report_id = r.id
    ) flags
    OUTER APPLY (
        SELECT e.type, e.actor
        FROM report_events e
        WHERE e.report_id = r.id
          AND e.type IN (
              'classificado',
              'classificacao_confirmada',
              'classificacao_corrigida',
              'vinculado_grupo',
              'moderacao_aprovada',
              'moderacao_rejeitada'
          )
        ORDER BY e.id DESC
        FETCH FIRST 1 ROW ONLY
    ) last_event
) source
ON (target.id = source.id)
WHEN MATCHED THEN UPDATE SET target.triage_state = source.triage_state
    WHERE target.triage_state <> source.triage_state;
