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

## Roteiro de demonstração (ponta a ponta)

Fluxo: cidadão cria o reporte no app → IA classifica → roteamento ao órgão →
servidor atende, redireciona ou modera no painel web → cidadão acompanha no app.

### Preparação (uma vez)

1. Suba a stack (seção anterior). Para a IA local:
   `docker compose --profile ai up -d ollama` e
   `docker compose exec ollama ollama pull qwen2.5:3b`. Sem o modelo, o
   `.env.example` já usa `AI_FALLBACK=fake` (classificação por palavras-chave);
   avise isso na apresentação.
2. Cadastre os servidores (login depois é por código no e-mail):

   ```bash
   ./scripts/provision-staff.sh zeladoria.demo@prefeitura.gov.br agency prefeitura-demo-zeladoria
   ./scripts/provision-staff.sh saneamento.demo@prefeitura.gov.br agency saneamento-demo
   ./scripts/provision-staff.sh moderadora.demo@prefeitura.gov.br moderator
   ./scripts/provision-staff.sh gestora.demo@prefeitura.gov.br manager
   ```

3. Celular Android com depuração USB: `adb reverse tcp:8000 tcp:8000` e o app
   de debug instalado (`mobile/README.md`). Os códigos de acesso chegam no
   Mailpit (`http://localhost:8025`).

### Passo a passo (cerca de 8 minutos)

| # | Onde | Ação | O que mostrar |
|---|---|---|---|
| 1 | App | Entrar com um e-mail de cidadão (código no Mailpit) | Login OTP |
| 2 | App | Novo reporte: "Vazamento de esgoto na calçada da escola", com foto e localização | Envio, protocolo |
| 3 | App | Abrir o reporte | Classificação sugerida pela IA (categoria, subcategoria, urgência) e confirmação |
| 4 | Web | Entrar como `zeladoria.demo` → Gestão de Ocorrências | Reporte encaminhado à Zeladoria, com prazo |
| 5 | Web | Detalhe → Redirecionar para "Saneamento Demo" com justificativa | Timeline registra quem, quando e por quê; a Zeladoria perde o acesso |
| 6 | App | Detalhe do reporte aberto (atualiza a cada 20 s) | Novo órgão, novo prazo e o redirecionamento na linha do tempo |
| 7 | Web | Entrar como `saneamento.demo` → Iniciar atendimento com prazo, depois Resolver com justificativa | Status no app muda para "Em andamento" e "Resolvido" |
| 8 | App | Outro cidadão sinaliza um reporte qualquer | Reporte sai do mapa e vai para a fila |
| 9 | Web | Entrar como `moderadora.demo` → Moderação → abrir → Aprovar ou Rejeitar com justificativa | Decisão auditada; rejeitado some do mapa |
| 10 | Web | Entrar como `gestora.demo` → Visão Geral (7 dias / 30 dias / 12 semanas) e Indicadores públicos | Série abertos × concluídos, categorias, órgãos, regiões, CSV |

Se algo falhar na hora: `docker compose logs api worker --since 5m` e a fila em
`job_queue` (etapa e `last_error`).

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
