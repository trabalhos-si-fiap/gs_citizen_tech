# Guia de Integração Front-end ↔ Back-end

Como o app **Flutter** e a API **FastAPI** se conectam. Contrato completo em `04-openapi.yaml`. Regras de origem em `01` (RN) e `02` (RT).

## 1. Visão da conexão

```
┌──────────── App Flutter ────────────┐                 ┌──────────── Backend FastAPI ───────────┐
│ UI (features) ──► Repositórios      │                 │ Rotas /v1 ─► Serviços ─► Portas        │
│                      │              │                 │                    │                   │
│            ┌─────────▼────────┐     │   HTTPS/JSON    │          Fila de jobs (classificar,    │
│            │ SQLite (Drift)   │     │ ◄─────────────► │          deduplicar, rotear, notificar)│
│            │ reports, outbox, │     │  Bearer JWT     │                    │                   │
│            │ cache mapa       │     │                 │      DynamoDB · S3 · IA · E-mail · Push│
│            └─────────▲────────┘     │                 └───────────────────────────────────────┘
│              SyncEngine (outbox)    │   PUT foto (URL assinada)  ──►  Storage
│              ApiClient (Dio)        │ ◄── Push (FCM) / polling de status
└──────────────────────────────────────┘
```

Regra de ouro: **a UI nunca chama a rede diretamente**. Ela lê e escreve no banco local; o `SyncEngine` conversa com a API. Assim o app funciona offline (RT-03, RT-08).

## 2. Convenções do contrato

| Tema | Convenção |
| :-- | :-- |
| Base URL | `API_BASE_URL` por ambiente. Emulador Android: `http://10.0.2.2:8000`; simulador iOS: `http://localhost:8000` |
| Formato | JSON UTF-8, campos em `snake_case` |
| Datas | ISO 8601 em UTC com `Z` (`2026-11-09T15:30:00Z`); o app converte para America/Sao_Paulo na exibição |
| IDs | `Report.id` = UUID v4 gerado **no app**; protocolo gerado no servidor |
| Coordenadas | `lat`, `lon` em graus decimais (WGS84), 6 casas |
| Autenticação | `Authorization: Bearer <access_token>`; órgãos: `X-API-Key` |
| Correlação | `X-Correlation-ID: <uuid>` em toda chamada ligada a um reporte (RT-55) |
| Idioma | Mensagens de erro em pt-BR; `code` estável em inglês/snake_case para o app decidir o comportamento |
| Versão do app | `X-App-Version: 1.0.0+3` (diagnóstico e política de versão mínima) |
| Paginação | `limit` e `cursor` opaco; resposta `{ "items": [], "next_cursor": null }` |
| Limite de taxa | `429` com `Retry-After` (segundos) |
| Idempotência | `POST /v1/reports` com o mesmo `id` devolve **200** com o reporte existente |
| Compatibilidade | Mudanças na v1 só aditivas; o app ignora campos desconhecidos |

### 2.1 Catálogo de erros e comportamento do app

| HTTP | `code` | Significado | O app faz |
| :-- | :-- | :-- | :-- |
| 400 | `bad_request` | Corpo malformado | Erro de programação: log e mensagem genérica |
| 401 | `invalid_credentials` / `otp_invalid` / `otp_expired` | Login falhou | Mostra erro no campo do código |
| 401 | `token_expired` | Access token expirado | **Renova e repete uma vez**; se falhar, vai ao login |
| 403 | `forbidden` | Sem permissão | Mensagem "Você não tem permissão para isso" |
| 404 | `not_found` | Recurso inexistente | Remove item do cache local se for o caso |
| 409 | `invalid_transition`, `reopen_not_allowed`, `already_confirmed`, `already_flagged`, `nudge_not_allowed` | Regra de negócio | Mostra a mensagem do servidor e atualiza a tela |
| 410 | `reopen_window_expired` | Prazo de reabertura passou | Esconde o botão "Reabrir" |
| 413 | `payload_too_large` | Foto acima do limite | Recomprime e reenvia |
| 422 | `validation_error` | Campo inválido (`field` indica qual) | Destaca o campo; **não** reenvia automaticamente |
| 429 | `rate_limited` | Limite de taxa | Respeita `Retry-After`; entra em backoff |
| 5xx | `internal_error`, `service_unavailable` | Falha do servidor | **Reenvio com backoff** (a fila local mantém o item) |

Regra de reenvio: erros de rede e **5xx/429** são **transitórios** (reenviar); **4xx** (exceto 401 com refresh e 429) são **definitivos** (marcar item como `failed` com a mensagem e exibir ao usuário).

## 3. Autenticação ponta a ponta

```
App                                   API
 │ POST /v1/auth/login {email,consent} ─►│ gera OTP, envia e-mail (MailHog em dev)
 │ ◄── 202 {status: otp_sent}            │
 │ POST /v1/auth/login {email,code} ────►│ valida OTP
 │ ◄── 200 {access,refresh,user}         │
 │ guarda tokens em flutter_secure_storage
 │ GET /v1/me/reports  (Bearer access) ─►│
 │ ◄── 401 token_expired                 │
 │ POST /v1/auth/refresh {refresh} ─────►│ rotaciona: invalida o refresh antigo
 │ ◄── 200 novos tokens                  │
 │ repete a chamada original ───────────►│
```

**App (Dio):** um `AuthInterceptor` que (1) injeta o `Authorization`, (2) ao receber 401 `token_expired`, chama `refresh` **uma única vez em paralelo** (usar um `Completer`/lock para que várias requisições simultâneas esperem o mesmo refresh) e repete a requisição; (3) se o refresh falhar, limpa os tokens e navega ao login preservando o outbox (os reportes pendentes **não** são apagados).

**Google:** o app obtém o `id_token` com `google_sign_in` e envia em `google_id_token`.

**Dica de dev:** em `ENV=dev`, o OTP também é impresso no log do backend e fica visível no MailHog (`http://localhost:8025`).

## 4. Contratos por fluxo (exemplos)

### 4.1 Criar reporte

```http
POST /v1/reports
Authorization: Bearer …
X-Correlation-ID: 6f1c…
Content-Type: application/json

{
  "id": "0b8f7f0e-3d1e-4b6e-9d58-6a4c1f6e2a11",
  "description": "Árvore inclinada sobre a calçada, parece que vai cair.",
  "has_photo": true,
  "category": "risco_urbano",
  "lat": -23.600123,
  "lon": -46.919876,
  "location_accuracy_m": 12,
  "anonymous": false,
  "client_created_at": "2026-11-09T15:24:10Z"
}
```

```json
// 201 Created (ou 200 se o id já existia)
{
  "id": "0b8f7f0e-3d1e-4b6e-9d58-6a4c1f6e2a11",
  "protocol": "RPT-2026-4KQ7TD",
  "status": "recebido",
  "received_at": "2026-11-09T15:24:12Z",
  "triage_state": "pending_classification",
  "upload": {
    "url": "https://…/signed-put",
    "method": "PUT",
    "headers": { "Content-Type": "image/jpeg" },
    "max_bytes": 1000000,
    "expires_at": "2026-11-09T15:34:12Z"
  }
}
```

### 4.2 Enviar a foto (segundo plano) e concluir

1. `PUT {upload.url}` com o corpo binário da foto e os `headers` devolvidos (sem `Authorization` quando a URL é do S3; em dev, `PUT /v1/uploads/{token}` também dispensa o Bearer porque o token da URL já autoriza).
2. `POST /v1/reports/{id}/photo/complete` com `{"sha256": "<hex>"}` → **202**.
3. Se a URL expirou (403/410 do storage), o app **repete `POST /v1/reports`** com o mesmo `id` para obter nova URL (idempotente).

### 4.3 Consultar a classificação (triagem)

O app consulta `GET /v1/reports/{id}` a cada 2 s, até 15 s, enquanto `triage_state == "pending_classification"`. Depois disso, para de consultar e mostra o seletor manual (IA indisponível, RT-30); o push ou a próxima abertura da tela retomam a consulta.

```json
// GET /v1/reports/{id}  (trecho)
{
  "id": "0b8f…",
  "protocol": "RPT-2026-4KQ7TD",
  "status": "recebido",
  "triage_state": "awaiting_user",
  "classification": {
    "category": "risco_urbano", "subcategory": "arvore_risco",
    "urgency": "alta", "confidence": 0.91, "immediate_risk": false, "source": "ai"
  },
  "agency": { "id": "prefeitura-demo-zeladoria", "name": "Prefeitura Demo — Zeladoria" },
  "deadline": "2026-11-12T15:24:12Z",
  "timeline": [ { "id": "01J…", "type": "recebido", "actor": "system", "created_at": "2026-11-09T15:24:12Z" } ]
}
```

- `triage_state`: `pending_classification` → (`awaiting_user` | `in_moderation`) → (`confirmed` | `auto_confirmed`).
- Se `classification.immediate_risk == true`, o app abre a **tela de Emergência** por cima (RN-28, D9).
- `classification.source == "none"` significa IA indisponível: mostrar o seletor manual.

### 4.4 Confirmar ou corrigir

```http
POST /v1/reports/{id}/triage
{ "action": "confirm" }
# ou
{ "action": "correct", "category": "risco_urbano", "subcategory": "calcada_danificada" }
```

Resposta: `ReportDetail` com o novo `agency` (recalculado pela matriz) e, após o encaminhamento, `status: "encaminhado"`. O encaminhamento é assíncrono: o app mostra o **Protocolo** imediatamente e atualiza o status quando mudar.

### 4.5 Ações de acompanhamento

| Ação | Chamada | Pré-condição (o app esconde o botão; o servidor valida) |
| :-- | :-- | :-- |
| Reabrir | `POST /v1/reports/{id}/reopen` | `can_reopen == true` |
| Cobrar novamente | `POST /v1/reports/{id}/nudge` | `can_nudge == true` (atrasado) |
| Confirmar (+1) | `POST /v1/reports/{id}/confirm` | Não é o autor; ainda não confirmou |
| Sinalizar | `POST /v1/reports/{id}/flag` | — |

O app usa **`can_reopen`** e **`can_nudge`** vindos do servidor; **não recalcula prazos localmente**.

### 4.6 Mapa e listas

- Mapa: `GET /v1/reports/nearby?lat=…&lon=…&radius_m=1000` ao mover/parar o mapa (*debounce* de 500 ms). Cache local por célula geohash (TTL 10 min) para uso offline.
- Meus reportes: `GET /v1/me/reports?limit=20&cursor=…`; mesclar com os reportes locais pendentes (que ainda não existem no servidor).

### 4.7 Atualização de status pelo órgão

```http
POST /v1/agency/reports/{id}/status
X-API-Key: <chave do órgão>
{ "action": "in_progress", "deadline": "2026-11-15T12:00:00Z" }
{ "action": "resolved",    "justification": "Poda realizada em 12/11." }
{ "action": "contest",     "justification": "Fora da competência do município." }
```

Efeito: grava o evento, atualiza a projeção e dispara **push** ao cidadão (via `NotificationLink`) com o payload `{ "type": "status_changed", "report_id": "…", "status": "em_andamento" }`.

## 5. Notificações push

1. Após o login, o app pede permissão; se concedida, obtém o token FCM e chama `PUT /v1/me/devices`.
2. Ao receber push (`onMessage`/`onMessageOpenedApp`), o app chama `GET /v1/reports/{id}` e atualiza o banco local; o push **não carrega dados do reporte além do ID e do status**.
3. Permissão negada: o app **segue funcionando**, atualizando por consulta ao abrir "Meus reportes" e em intervalos quando em primeiro plano (a cada 60 s) (RT-15).

## 6. Offline-first e sincronização (RT-03, RT-08, RT-09, RT-10, RN-11)

### 6.1 Esquema local (Drift/SQLite)

| Tabela | Colunas principais |
| :-- | :-- |
| `local_reports` | `id` (UUID), `protocol` (nulo até sincronizar), `local_code`, `description`, `category`, `lat`, `lon`, `anonymous`, `photo_path`, `photo_sha256`, `client_created_at`, `correlation_id`, `sync_state`, `server_status`, `triage_state`, `last_error`, `attempts`, `next_attempt_at`, `server_json` (último `ReportDetail`) |
| `outbox` | `id`, `report_id`, `op` (`create`, `photo_upload`, `photo_complete`, `triage`, `reopen`, `nudge`, `confirm`, `flag`), `payload_json`, `attempts`, `next_attempt_at`, `state` (`pending`, `in_flight`, `done`, `failed`), `created_at` |
| `map_cache` | `cell` (geohash), `fetched_at`, `items_json` |
| `kv` | pares chave-valor (consentimento aceito, última sincronização) |

`sync_state` do reporte: `pending_create` → `created` → `pending_photo` → `photo_uploaded` → `synced`; ou `failed`.

### 6.2 Algoritmo do `SyncEngine`

Gatilhos: reporte criado, app em primeiro plano, **conectividade restaurada** (`connectivity_plus`), temporizador de backoff e tarefa periódica em segundo plano (`workmanager`, mínimo de 15 min).

```dart
Future<void> drain() async {
  if (_running || !await _hasNetwork()) return;     // uma execução por vez
  _running = true;
  try {
    while (true) {
      final op = await outbox.nextDue(now());       // ordem FIFO por report_id e criação
      if (op == null) break;
      await outbox.markInFlight(op.id);
      try {
        await _execute(op);                         // create → upload → complete → triage...
        await outbox.markDone(op.id);
      } on TransientError catch (e) {               // rede, 5xx, 429
        await outbox.reschedule(op.id, backoff(op.attempts + 1, retryAfter: e.retryAfter));
        break;                                      // preserva a ordem: não pula para o próximo
      } on PermanentError catch (e) {               // 4xx definitivos
        await outbox.markFailed(op.id, e.message);
        await localReports.setError(op.reportId, e.message);
      }
    }
  } finally { _running = false; }
}

Duration backoff(int attempt, {Duration? retryAfter}) {
  final base = min(pow(2, attempt) * 5, 900);       // 10 s, 20 s, 40 s ... teto de 15 min
  final jitter = Random().nextInt((base * 0.2).toInt() + 1);
  return retryAfter ?? Duration(seconds: base.toInt() + jitter);
}
```

Regras:

1. **Ordem por reporte:** as operações de um mesmo reporte são sequenciais (`create` antes de `photo_upload`). Reportes diferentes podem ir em paralelo (até 2).
2. **Idempotência:** `create` repetido é seguro (mesmo `id` → 200). `photo_complete` repetido também.
3. **Data/hora original (RN-11):** `client_created_at` é gravado na criação local e **nunca** alterado; o servidor guarda também `received_at`.
4. **Compressão (RT-10):** antes de enfileirar `photo_upload`, comprimir para ≤ 1 MB (`flutter_image_compress`, qualidade inicial 80, reduzindo até caber), remover EXIF e salvar o `sha256`. O envio ocorre em segundo plano.
5. **Sem perda de dados:** itens só saem da fila com `done`. Em `failed`, o reporte permanece visível com botão "Tentar de novo" (volta a `pending`).
6. **Conta expirada:** se o refresh falhar, o `SyncEngine` **pausa** (não marca `failed`) até novo login.
7. **Código provisório (D11):** `local_code = "LOCAL-" + id.substring(0, 8).toUpperCase()`. Ao receber `protocol`, a UI passa a exibi-lo.

### 6.3 Estados de UI obrigatórios (RT-12)

| Situação | Mensagem pt-BR (exemplos) |
| :-- | :-- |
| Vazio | "Você ainda não fez nenhum reporte." |
| Carregando | Indicador + "Carregando…" |
| Sem conexão | "Sem conexão. Seu reporte foi salvo e será enviado quando a internet voltar." |
| Erro | "Não foi possível concluir. Tente novamente." (+ botão) |
| Aguardando envio | Selo "Aguardando envio" com o código `LOCAL-…` |
| IA indisponível | "Não conseguimos sugerir a categoria agora. Escolha uma abaixo." |

Todos os textos vêm de `l10n/app_pt_BR.arb`.

## 7. Estrutura do front-end (Flutter)

### 7.1 Pacotes sugeridos

| Necessidade | Pacote |
| :-- | :-- |
| Estado e injeção | `flutter_riverpod` |
| Navegação | `go_router` |
| HTTP | `dio` |
| Banco local | `drift` + `sqlite3_flutter_libs` |
| Mapa (OSM) | `flutter_map`, `latlong2` |
| Localização | `geolocator` |
| Foto | `image_picker`, `flutter_image_compress`, `crypto` (sha256) |
| Voz | `speech_to_text` |
| Conectividade/segundo plano | `connectivity_plus`, `workmanager` |
| Push | `firebase_core`, `firebase_messaging` |
| Segurança | `flutter_secure_storage` |
| Login Google | `google_sign_in` |
| Discador (emergência) | `url_launcher` (`tel:190`) |
| IDs | `uuid` |
| Textos | `flutter_localizations`, `intl` |
| Testes | `flutter_test`, `mocktail`, `integration_test` |

### 7.2 Organização

```
lib/
├── core/
│   ├── api/            # api_client.dart, auth_interceptor.dart, errors.dart, dtos/ (gerados ou escritos a partir do OpenAPI)
│   ├── db/             # app_database.dart (Drift), daos
│   ├── sync/           # sync_engine.dart, outbox.dart, backoff.dart
│   ├── auth/           # token_store.dart, auth_controller.dart
│   ├── config/         # env.dart (API_BASE_URL, ENV)
│   └── theme/          # cores, tipografia (≥16 px), componentes acessíveis
└── features/
    ├── auth/           ├── home_map/    ├── new_report/   ├── triage/
    ├── protocol/       ├── my_reports/  ├── report_detail/
    ├── emergency/      └── profile/
```

Cada *feature* segue `data/` (repositório), `domain/` e `presentation/`. A UI observa **streams do banco local** (Drift) e dispara casos de uso; só o repositório conhece a API e o outbox.

### 7.3 Cliente de API a partir do contrato

Gerar os DTOs a partir de `contracts/openapi.yaml` (`openapi-generator` com `dart-dio`, ou `swagger_parser`) e **não editar** os arquivos gerados. Rodar a geração no CI e falhar o build se o resultado diferir do versionado.

## 8. Estrutura do back-end (FastAPI) — pontos de contato com o app

| Rota | Serviço | Observações de integração |
| :-- | :-- | :-- |
| `POST /v1/auth/login` | `AuthService` | OTP e Google; exige `consent` na criação da conta |
| `POST /v1/reports` | `ReportService.create` | Idempotente; devolve `upload` |
| `POST /v1/reports/{id}/photo/complete` | `ReportService.photo_complete` | Enfileira processamento de imagem e classificação |
| `GET /v1/reports/{id}` | `ReportService.get_detail` | Monta `ReportDetail` a partir da projeção + eventos + `can_*` |
| `POST /v1/reports/{id}/triage` | `ClassificationService.confirm` | Dispara roteamento |
| `…/confirm`, `…/reopen`, `…/flag`, `…/nudge` | `ReportService` | Regras de RN-13, RN-14, RN-35 |
| `GET /v1/reports/nearby` | `ReportService.nearby` | Por geohash + haversine; sem dados pessoais |
| `GET /v1/me/*`, `PUT /v1/me/devices`, `DELETE /v1/me` | `UserService` | LGPD |
| `POST /v1/agency/reports/{id}/status` | `AgencyService` | `X-API-Key`; transições válidas |
| `GET /v1/public/metrics` | `AnalyticsService` | Só camada analítica |

CORS: liberar somente as origens dos painéis web (`CORS_ORIGINS`). O app nativo não depende de CORS.

## 9. Ambiente de desenvolvimento

`infra/docker-compose.yml` deve subir:

| Serviço | Porta | Uso |
| :-- | :-- | :-- |
| `backend` | 8000 | API (hot reload) |
| `dynamodb-local` | 8001 | Banco |
| `mailhog` | 1025 (SMTP), 8025 (UI) | E-mails de OTP e e-mails aos órgãos |

`.env.example` (backend):

```
ENV=dev
APP_NAME=Reporta
JWT_SECRET=troque-isto
REPO=dynamo
DYNAMO_ENDPOINT=http://dynamodb-local:8000
STORAGE=local
STORAGE_DIR=./data/uploads
CLASSIFIER=anthropic        # ou null para rodar sem IA
ANTHROPIC_API_KEY=
AI_MODEL_SMALL=claude-haiku-5-5
AI_MODEL_LARGE=claude-sonnet-5-5
MAILER=smtp
SMTP_HOST=mailhog
SMTP_PORT=1025
PUSH=log
QUEUE=memory
ANALYTICS=duckdb
ANALYTICS_DIR=./data/analytics
CORS_ORIGINS=http://localhost:8000
```

Comandos esperados no `Makefile`: `make up`, `make seed-demo`, `make test`, `make lint`, `make contract-test`, `make e2e`.

## 10. Passo a passo para o Claude implementar

Cada passo tem **entrega** e **verificação**. Não avance sem a verificação verde.

### Back-end

| Passo | Entrega | Verificação |
| :-- | :-- | :-- |
| B1 | Esqueleto FastAPI, `config.py`, `/health`, formato de erro, `X-Correlation-ID`, logs JSON | `GET /health` = 200; erro 422 sai no formato padrão |
| B2 | Domínio: enums, máquina de estados, derivação de status (funções puras) | Testes unitários de todas as transições e do atributo `overdue` |
| B3 | Portas + adaptadores `memory` e `dynamo`; criação das tabelas e índices | Mesma suíte de testes de repositório passa nos dois adaptadores; teste proíbe alterar `Report`/`ReportEvent` (RT-21) |
| B4 | Auth: OTP por e-mail, Google, JWT, refresh rotativo, papéis | Fluxo completo com MailHog; refresh reutilizado = 401 |
| B5 | `POST /v1/reports` idempotente, protocolo, evento `recebido`, `NotificationLink`, upload (local e assinado) | Reenviar o mesmo UUID 5× gera 1 reporte; anônimo não grava `user_id` |
| B6 | Fotos: recodificação sem EXIF, `Redactor`, `photo/complete`, URLs assinadas de leitura | Imagem de teste com EXIF sai sem metadados |
| B7 | `Classifier` (`Null`, `Fake` e `Anthropic`), duas etapas, cache, fallback, tokens registrados | Com `CLASSIFIER=null` o fluxo conclui como "a classificar" |
| B8 | Deduplicação e grupos; confirmações (+1) | Casos limite de raio, janela e semelhança cobertos |
| B9 | Roteamento (matriz versionada), triagem, auto-confirmação, e-mail ao órgão sem dados pessoais, reenvio com recuo | E-mail no MailHog sem nome/e-mail do cidadão; falha de SMTP gera reenvios registrados |
| B10 | `GET /v1/reports/{id}`, `nearby`, `me/*`, reabrir, cobrar, sinalizar, painel do órgão (`/panel`) | Contrato validado com Schemathesis |
| B11 | Notificações push (adapter `log` e `fcm`), tarefa de atrasados | Mudança de status gera push com o payload definido |
| B12 | Exportador Parquet, DuckDB, `/v1/public/metrics`, painel `/public`, CSV | Métricas batem com dados sintéticos conhecidos; células pequenas ocultas |
| B13 | LGPD (`export`, `delete`), limite de taxa, auditoria, seeds de demonstração | Excluir conta remove vínculos; reportes ficam anonimizados |

### Front-end

| Passo | Entrega | Verificação |
| :-- | :-- | :-- |
| F1 | Projeto Flutter, tema acessível, `l10n` pt-BR, navegação, `Env` | `flutter analyze` limpo; contraste e toque ≥ 48 px conferidos |
| F2 | Banco local (Drift), DAOs, `ApiClient` + `AuthInterceptor`, DTOs gerados | Teste do interceptor: 401 → refresh único → repete |
| F3 | Onboarding, consentimento, login (OTP e Google), armazenamento seguro de tokens | Teste de widget do fluxo; tokens não aparecem em log |
| F4 | Home com mapa OSM, marcadores, filtros, cache offline, atalho de Emergência | Sem rede, mostra o último cache |
| F5 | Novo reporte (3 passos), GPS/pin, câmera/galeria, ditado, filtro de emergência, **faixa de emergência** | "Enviar" bloqueado sem foto e sem descrição |
| F6 | `SyncEngine`, outbox, compressão, backoff, código provisório | Teste de integração: criar offline → ligar rede → 1 reporte no servidor, sem duplicata |
| F7 | Confirmação da IA e do órgão (consulta com limite de 15 s, estados, IA indisponível, emergência) | Com classificador `fake` e `null` as duas telas se comportam como especificado |
| F8 | Protocolo (copiar/compartilhar) | Exibe `LOCAL-…` offline e `RPT-…` após sincronizar |
| F9 | Meus reportes, detalhe com linha do tempo, reabrir, cobrar, confirmar, sinalizar | Botões seguem `can_reopen` e `can_nudge` do servidor |
| F10 | Push (FCM), registro de dispositivo, tratamento de permissão negada | Negar permissão não quebra o app |
| F11 | Perfil: exportar, excluir conta, sair | Exclusão limpa banco local e tokens |
| F12 | Testes de widget e `integration_test` do caminho essencial (RT-64) | Fluxo Home → Novo reporte → Confirmação → Protocolo verde |

### Integração (back + front)

| Passo | Entrega | Verificação |
| :-- | :-- | :-- |
| I1 | `contracts/openapi.yaml` como fonte única; geração de DTOs no CI | CI falha se o gerado divergir |
| I2 | Ambiente compose + seed + app apontando para `API_BASE_URL` | Login, mapa com dados demo e reporte real funcionando no emulador |
| I3 | Teste e2e do RT-58: reporte → classificar (fake) → triagem → e-mail (MailHog) → órgão `in_progress` → app consulta e vê o status | Script `make e2e` verde |
| I4 | Cenários de falha: API fora do ar, 5xx intermitente, token expirado, URL de upload expirada, IA indisponível | Nenhum reporte perdido; mensagens corretas |
| I5 | Teste de carga (p95 de `POST /v1/reports` ≤ 2 s) e métricas | Relatório anexado a `docs/` |
| I6 | Roteiro e **vídeo de reserva** da demonstração (RT-64) | Vídeo gravado com dados fictícios |

## 11. Checklist final de integração

- [ ] Todo endpoint do app existe em `openapi.yaml`, e vice-versa.
- [ ] Reenvio do mesmo `id` nunca duplica; teste automatizado cobre isso.
- [ ] O app não perde reportes criados offline (teste com rede simulada).
- [ ] `client_created_at` é preservado de ponta a ponta (RN-11).
- [ ] O e-mail ao órgão e o painel público não contêm dado pessoal (RN-43, RT-42).
- [ ] A IA desligada não impede registrar nem encaminhar (RT-30).
- [ ] A faixa "Emergência? Ligue 190, 192 ou 193" aparece em todas as telas do fluxo de reporte (RN-27).
- [ ] Textos de erro e estados vazios estão em pt-BR (RT-12).
- [ ] Nenhum segredo no repositório; `.env.example` completo (RT-46).
- [ ] Pontos em aberto de RT-66 continuam registrados em `docs/DECISOES.md`.
