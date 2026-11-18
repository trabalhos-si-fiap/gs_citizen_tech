# Ready to Do — APIs prontas do backend × integração com o WEB

Mapeamento feito a partir do código em `back-end/app` (FastAPI) e `web/src/app` (Angular 21).
Base URL local: `http://localhost:8000` — docs interativas em `/docs`.

## 1. Resumo rápido

| Tela do WEB | Estado atual | Integração possível hoje? |
|---|---|---|
| `/indicadores` | **Já integrada** (`GET /v1/public/metrics`) | Sim, funcionando. Faltam só filtros de data |
| `/login` | Protótipo, não envia nada | **Parcial** — backend só tem OTP por e-mail e Google, não há login por senha/órgão |
| `/dashboard` | 100% dados ilustrativos | **Parcial** — só os 4 totais via métricas públicas |
| `/ocorrencias` | 100% dados ilustrativos | **Não** — não há endpoint de listagem geral para servidor. Só fila de moderação (exige token moderator) |
| `/ocorrencias/:id` | 100% dados ilustrativos | **Parcial** — leitura de detalhe/comentários possível, ver restrições |

## 2. Configuração necessária para integrar

- **CORS** (`main.py`): liberado para `http://localhost:4200`, `http://127.0.0.1:4200`, `http://localhost:8000`.
  Métodos: `GET, POST, PATCH, PUT, DELETE, OPTIONS`. Headers: `Authorization`, `Content-Type`, `X-Correlation-ID`.
  `X-API-Key` **não** está liberado.
- **Subir o backend em dev**: `cd back-end && cp .env.example .env && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload`
  (`.env.example` usa `REPORT_REPOSITORY=memory`; dados somem ao reiniciar).
- Todos os dados ficam vazios em memória até alguém criar reportes (via app mobile ou `/docs`).
- Auth: `Authorization: Bearer <access_token>`.
- Variável do WEB para trocar a API: `window.RECLAME_JA_API_URL` (hoje só lida em `public-metrics.component.ts`).

## 3. APIs prontas (todas as rotas existentes)

### 3.1 Públicas (sem token)

| Método | Rota | Descrição | Uso no WEB |
|---|---|---|---|
| GET | `/health`, `/api/health`, `/` | Health check | Pode alimentar o indicador "Servidor Oficial Ativo" do shell |
| GET | `/v1/public/metrics` | Métricas agregadas. Query: `from`, `to` (data), `category`, `agency_id`, `format=json\|csv` | **Já usado** em `/indicadores` |
| GET | `/v1/reports/{id}/comments` | Lista comentários (`limit` 1–100) | Pode ir no detalhe da ocorrência |
| PUT | `/v1/uploads/{token}` | Upload de foto por URL assinada | Só mobile/cidadão |
| GET | `/v1/photos/{token}` | Leitura de foto por URL assinada (15 min) | Pode exibir a foto no detalhe (URL vem em `photo_url`) |

Resposta de `/v1/public/metrics`:

```json
{
  "period": { "from": "2026-01-01|null", "to": "..." },
  "totals": { "reports": 0, "avg_response_hours": null, "resolution_rate": null, "recurrence": 0 },
  "by_agency": [
    { "agency": { "id": "...", "name": "..." }, "reports": 0, "avg_response_hours": null, "resolution_rate": null }
  ]
}
```

### 3.2 Autenticação

| Método | Rota | Descrição |
|---|---|---|
| POST | `/v1/auth/login` | `{email, consent?}` → 202 envia OTP de 6 dígitos. `{email, code}` → tokens. `{google_id_token, consent?}` → tokens |
| POST | `/v1/auth/refresh` | `{refresh_token}` → novos tokens (rotaciona) |

Resposta com tokens: `{access_token, refresh_token, expires_in, user:{id,email,role,consent_version,created_at}}`.

> Atenção: contas novas são sempre criadas com `role="citizen"` (`repositories.py`). Não existe endpoint para criar/promover `moderator`, `agency`, `manager` ou `admin`; isso só é possível direto no banco (`users.role`, constraint em `schema.sql`).

### 3.3 Cidadão (exigem Bearer com `role=citizen`)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/v1/reports` | Cria reporte (idempotente por UUID) |
| GET | `/v1/reports/{id}` | Detalhe + timeline + classificação + órgão + prazo + `photo_url` |
| POST | `/v1/reports/{id}/photo/complete` | Conclui upload (SHA-256) |
| POST | `/v1/reports/{id}/triage` | Solicitante confirma/corrige categoria |
| POST | `/v1/reports/{id}/comments` | Comenta (até 1000 chars) |
| POST | `/v1/reports/{id}/confirm` | "Vi isso" (+1) |
| POST | `/v1/reports/{id}/reopen` | Reabre reporte resolvido (só o solicitante) |
| POST | `/v1/reports/{id}/flag` | Sinaliza (`ofensivo`, `dados_pessoais`, `falso`, `duplicado_abusivo`, `outro`) |
| POST | `/v1/reports/{id}/nudge` | Cobra o órgão (só o solicitante) |
| GET | `/v1/me` · PATCH `/v1/me` · DELETE `/v1/me` | Conta, troca de e-mail, exclusão (LGPD) |
| GET | `/v1/me/export` | Exporta dados (LGPD) |
| GET | `/v1/me/reports` | Meus reportes, paginado por cursor, filtro `status` |
| PUT/DELETE | `/v1/me/devices` | Registra/remove token push |

### 3.4 Órgão / Moderação

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/v1/agency/reports/{id}/status` | Header `X-API-Key` (`AGENCY_API_KEYS` no `.env`) | Body `{action: in_progress\|resolved\|contest, deadline?, justification?}`. Retorna o detalhe do reporte (com `timeline=[]` e `agency=null`) |
| GET | `/v1/moderation/reports` | Bearer com `role` `moderator` ou `admin` | Fila de moderação (`limit` 1–100). Retorna `{items:[ReportSummary], count}` |

## 4. O que dá para integrar no WEB agora (ready to do)

### 4.1 Pronto e sem bloqueio

1. **Filtros de período em `/indicadores`**: a API aceita `from` e `to`; o componente só envia `category`, `agency_id` e `format`. Basta adicionar dois inputs de data em `public-metrics.component.ts`.
2. **Dashboard — cards de resumo**: ligar `totals.reports`, `totals.resolution_rate` e `totals.avg_response_hours` de `/v1/public/metrics` nos cards "Demandas Ativas" / "SLA Resolvido". Observação: a API devolve **total**, não "ativas", "em atendimento" ou "alertas críticos".
3. **Dashboard / Relatórios — tabela por órgão**: usar `by_agency` (já existe em `/indicadores`).
4. **Exportar CSV**: já funciona em `/indicadores` (`format=csv`). Pode ser reaproveitado no botão "Exportar Relatório Diário" do dashboard (hoje exibe aviso demonstrativo).
5. **Status do servidor no shell**: chamar `GET /health` para trocar o "Servidor Oficial Ativo" fixo por estado real.
6. **Camada de API Angular**: criar um `ApiService` com `HttpClient` + interceptor `Authorization` (hoje o WEB usa `fetch` direto e não tem `provideHttpClient`).

### 4.2 Possível com ressalvas

7. **Login real de servidor** (`/login`): o backend só oferece OTP por e-mail e Google.
   - Dá para trocar o campo senha por fluxo de código: `POST /v1/auth/login {email}` → `POST /v1/auth/login {email, code}`; guardar `access_token` e `refresh_token`; renovar com `/v1/auth/refresh`.
   - Para o token servir ao WEB, o usuário precisa ter `role=moderator|admin` no banco. O seletor "Órgão/Secretaria" não é usado por nenhuma API.
   - Primeiro acesso exige `consent: {version, accepted_age}`.
8. **Fila de moderação**: `GET /v1/moderation/reports` pode alimentar uma lista na tela `/ocorrencias`, mas só mostra reportes `in_moderation` / sinalizados, e os campos são `id, protocol, status, category, lat, lon, received_at, group_id, confirmation_count`. Não vêm título, endereço, prioridade, SLA nem descrição.
9. **Detalhe da ocorrência**: `GET /v1/reports/{id}` devolve tudo que a tela precisa (descrição, `photo_url`, lat/lon, classificação, órgão, prazo, timeline), **porém exige `role=citizen`**. Um token de moderador recebe 403. O `ReportDetailResponse` retornado em `/v1/agency/reports/{id}/status` vem com `timeline` vazia e `agency=null`.
10. **Comentários**: `GET /v1/reports/{id}/comments` é público e pode ser exibido no detalhe.
11. **Mudança de status** (botão "Confirmar Alteração de Status"): existe `POST /v1/agency/reports/{id}/status`, mas usa `X-API-Key` secreta de servidor. Não deve ser colocada no navegador, e o CORS atual não permite o header `X-API-Key`. Precisaria de um proxy/BFF ou de uma rota nova com Bearer. Mapeamento de ações: Em Execução → `in_progress`, Resolvido → `resolved`, Indeferido → `contest` (exige `justification`). "Em Análise Técnica" não tem equivalente.

## 5. Lacunas (o WEB mostra, mas o backend não tem API)

- Listagem geral de ocorrências para servidor (filtros por prioridade, categoria, subprefeitura, SLA, busca por protocolo e paginação).
- Contadores operacionais: ativas, em atendimento, alertas críticos, aguardando triagem.
- Série temporal "aberturas vs. conclusões", ranking por bairro, proporção por tipologia (o `/metrics` só traz totais e por órgão).
- Login por senha / escolha de secretaria; criação e gestão de usuários servidores.
- Autorização por órgão (servidor ver apenas os reportes do seu órgão).
- Ação de moderação (aprovar/rejeitar) sobre a fila; só existe a listagem.
- Direcionar a outro órgão (re-roteamento manual).
- Enviar mensagem oficial ao cidadão (o push só dispara em mudança de status/prazo).
- Contato interno / diretório municipal, anexar vistoria e documentos, impressão.
- Campos de prioridade e SLA em horas restantes (a API só entrega `deadline` e `classification.urgency`).

## 6. Ordem sugerida de implementação

1. `ApiService` + `HttpClient` + configuração de URL da API (4.1 item 6).
2. Datas em `/indicadores` e dashboard ligado a `/v1/public/metrics` (4.1 itens 1–4).
3. Login por OTP com armazenamento/refresh de token (4.2 item 7), usando usuário moderador criado no banco.
4. Fila de moderação em `/ocorrencias` (4.2 item 8).
5. Decisões de backend antes de seguir: rota de listagem para servidor, permissão de leitura do detalhe para `moderator`/`agency`, e status via Bearer em vez de `X-API-Key`.
