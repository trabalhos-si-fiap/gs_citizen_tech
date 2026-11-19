-- Decisões da fila de moderação no painel (B4): aprovar (com reclassificação
-- e encaminhamento opcionais) ou rejeitar, sempre com justificativa.
ALTER TABLE report_events DROP CONSTRAINT ck_report_events_type;

ALTER TABLE report_events ADD CONSTRAINT ck_report_events_type CHECK (
    type IN (
        'recebido',
        'encaminhado',
        'em_andamento',
        'resolvido',
        'reaberto',
        'contestado',
        'classificado',
        'classificacao_confirmada',
        'classificacao_corrigida',
        'enviado_moderacao',
        'vinculado_grupo',
        'confirmacao_adicionada',
        'cobrado',
        'sinalizado',
        'moderacao_aprovada',
        'moderacao_rejeitada'
    )
);
