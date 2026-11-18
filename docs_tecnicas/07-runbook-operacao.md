# Runbook de operação

## Ambiente local

1. Copie `back-end/.env.example` para `back-end/.env`.
2. Defina segredo JWT, segredo de upload e chaves de órgão.
3. Execute `docker compose up --build`.
4. Use `http://localhost:8000/docs` para a API e `http://localhost:8025` para MailHog.

## Worker Oracle

- Configure `REPORT_REPOSITORY=oracle` e credenciais Oracle.
- Execute `python -m app.infrastructure.worker` em processo separado.
- Não execute a validação visual com provedor externo enquanto `VISUAL_VERIFICATION_ENABLED=false`.

## Segurança

- Não registre tokens FCM no corpo dos eventos nem em logs.
- Use TLS em todos os ambientes publicados.
- Restrinja `AGENCY_API_KEYS` por implantação e rotacione chaves periodicamente.
- Preserve a trilha `audit_log`; operações administrativas exigem justificativa quando aplicável.

## Backup e restauração

- Faça snapshot consistente do Oracle, do volume de fotos e das tabelas de fila.
- Restaure banco e fotos em um ambiente isolado antes de voltar a aceitar tráfego.
- Teste semanalmente um restore sintético e compare a integridade de reportes, eventos e fotos.
