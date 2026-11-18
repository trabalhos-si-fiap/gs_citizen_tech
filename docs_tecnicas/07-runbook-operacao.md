# Runbook de operação

## Ambiente local (Docker)

1. `cp .env.example .env` (configuração não secreta).
2. `./scripts/init-secrets.sh` (gera os segredos em `secrets/`, fora do git).
3. `docker compose up --build --wait`.
4. API em `http://localhost:8000/docs`, painel em `http://localhost:4200` e
   Mailpit em `http://localhost:8025`.
5. Smoke test: `python -m unittest discover -s tests/smoke -v`.

Topologia, segurança, migrations e solução de problemas estão em
[`09-containers-docker.md`](./09-containers-docker.md).

## Ambiente local sem Docker (modo memória)

- Copie `back-end/.env.example` para `back-end/.env`, defina os segredos e rode
  `uvicorn app.main:app` em `back-end/`. A API processa a fila sozinha
  (`INLINE_JOB_PROCESSING=true`).

## Worker Oracle

- Configure `REPORT_REPOSITORY=oracle` e credenciais Oracle.
- Aplique o banco com `python -m app.infrastructure.migrations`.
- Execute `python -m app.infrastructure.worker` em processo separado e
  `INLINE_JOB_PROCESSING=false` na API.
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
