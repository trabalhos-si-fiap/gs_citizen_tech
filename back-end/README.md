# Backend - Reclame Já

API em Python 3.12 com FastAPI e Pydantic v2, organizada para o MVP.
Oracle é o repositório persistente; a implementação em memória é apenas para
desenvolvimento.

## Organização

```text
app/
  api/            Rotas, autenticação, erros e middleware
  core/           Configuração
  infrastructure/ Adaptadores, Oracle, fila, arquivos, e-mail e worker
  models/         Schemas HTTP e modelos do domínio
  services/       Casos de uso
  main.py         Composição da aplicação FastAPI
  seeds/          Taxonomia
db/               Schema inicial e pacote PL/SQL
tests/unit/       Testes unitários
```

## Autenticação por e-mail

1. `POST /v1/auth/login` com `email` e `consent` (primeiro acesso) gera e envia
   um OTP de 6 dígitos por SMTP; a resposta é `202`.
2. A mesma rota com `email` e `code` valida o código e retorna access e refresh
   tokens. O OTP expira em 10 minutos e permite até cinco tentativas.
3. `POST /v1/auth/refresh` rotaciona o refresh token; o token anterior deixa
   de ser válido.

Configure `JWT_SECRET` com pelo menos 32 caracteres e ajuste `SMTP_HOST`,
`SMTP_PORT`, `SMTP_SENDER` e `SMTP_USE_TLS`. Em desenvolvimento, pode-se usar
MailHog (SMTP na porta 1025). Os dados de autenticação em memória são perdidos
ao reiniciar a aplicação. Para habilitar login Google, configure
`GOOGLE_CLIENT_ID`; o ID token é verificado com as chaves públicas do Google,
incluindo audiência, assinatura, expiração e e-mail verificado.

## Criação de reporte

1. `POST /v1/reports` valida um JWT de cidadão e o corpo da requisição.
2. `ReportService` valida `client_created_at` e coordena as integrações.
3. `OracleReportRepository` chama `PKG_REPORTES.registrar_reporte`.
4. O pacote grava o reporte, o evento inicial e o vínculo do solicitante na
   mesma transação; reportes sem foto também recebem um job de classificação.
   O protocolo retornado é idempotente pelo UUID do cliente.
5. A rota responde `201` para um reporte novo ou `200` para um reenvio.

`GET /v1/reports/{id}` retorna os dados disponíveis e a linha do tempo para
cidadãos autenticados. `GET /v1/me/reports` lista reportes associados ao
usuário (inclusive os enviados anonimamente), com paginação por cursor.

`GET /v1/reports/{id}/comments` lista comentários publicamente; `POST` na mesma
rota permite que cidadãos autenticados publiquem comentários de até 1000
caracteres. No MVP, comentários não podem ser editados ou removidos.
`POST /v1/reports/{id}/confirm` registra “Vi isso” (+1), uma vez por cidadão e
grupo; o autor do reporte não pode confirmar o próprio reporte.

## Upload e processamento de fotos

`POST /v1/reports` com `has_photo=true` devolve uma URL assinada válida por
10 minutos. O cliente envia o binário via `PUT` para essa URL (sem JWT) e chama
`POST /v1/reports/{id}/photo/complete` com o SHA-256. A conclusão valida a
propriedade do reporte, o hash e o formato JPEG/PNG/WebP; o job `process_photo`
recodifica a imagem para JPEG, aplica limite de pixels e remove metadados EXIF.
`GET /v1/reports/{id}` devolve uma URL de leitura assinada válida por 15 minutos.

Configure `PHOTO_UPLOAD_SECRET` com pelo menos 32 caracteres, `PHOTO_STORAGE_DIR`
em um volume persistente e compartilhado pela API e pelos workers, e
`PUBLIC_API_BASE_URL` com a URL pública da API. `PHOTO_MAX_BYTES` limita o upload
(1 MB por padrão). O worker usa a mesma fila Oracle durável para higienizar
fotos; a fila em memória é apenas para desenvolvimento. A proteção contra
rostos/placas ainda é um no-op; classificação de imagens, verificação de
conteúdo impróprio e detecção de imagens geradas por IA não foram implementadas
nesta etapa.

## Classificação e encaminhamento

Reportes sem foto são classificados em uma tarefa de fundo após a criação. O
adaptador `ollama` chama um modelo pequeno e, se a confiança ficar abaixo de
`AI_CONFIDENCE_THRESHOLD`, repete a classificação com o modelo maior. Se a IA
estiver desligada ou falhar, o fluxo usa a categoria informada pelo cidadão ou
`a_classificar`; a resposta nunca inventa urgência ou risco imediato.

Para usar os modelos locais, inicie o Ollama e baixe os modelos configurados:

```bash
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
```

Configure `CLASSIFIER=ollama`. O endereço Ollama deve apontar para loopback; o
backend não envia descrições de reportes a provedores externos. `CLASSIFIER=null`
é o padrão e mantém o MVP operável sem IA. `CLASSIFIER=fake` habilita somente
um classificador determinístico de desenvolvimento/teste.

Com `REPORT_REPOSITORY=oracle`, os jobs de classificação e higienização de foto
ficam persistidos e um processo separado os reserva com lease. Se um worker parar, outro pode retomar o job depois do
vencimento do lease. Erros transitórios usam backoff de 1, 5, 15 e 60 minutos;
após seis tentativas, o job de classificação é encaminhado à moderação.
`REPORT_REPOSITORY=memory` usa uma fila volátil apenas para desenvolvimento.

Após a sugestão, o solicitante pode confirmar ou corrigir a categoria em
`POST /v1/reports/{id}/triage`. O backend escolhe a regra vigente mais
específica na matriz versionada (`app/seeds/routing_matrix.json`), devolve o
órgão e o prazo de referência e registra os eventos. Sem regra, o reporte vai
para moderação. No piloto, todos os reportes são associados ao território
fictício `municipio_demo`. Após o encaminhamento, o worker envia e-mail ao
contato do órgão por SMTP, com retentativas da fila durável; auto-confirmação
após inatividade ainda não está implementada.

## Notificações push

O cidadão registra e remove tokens em `PUT`/`DELETE /v1/me/devices`, enviando
`push_token` e `platform` (`android` ou `ios`). Tokens são associados ao usuário,
não ao conteúdo do reporte. `PUSH_PROVIDER=log` é o padrão de desenvolvimento;
para envio real, configure `PUSH_PROVIDER=fcm`, `FCM_PROJECT_ID` e
`FCM_SERVICE_ACCOUNT_FILE` com credenciais de uma conta de serviço Firebase.
Os pushes incluem somente tipo, ID do reporte e status; a aplicação consulta a
API para obter os detalhes. Sem token registrado, o job conclui sem bloquear o
acompanhamento.

O Oracle enfileira a notificação de status na mesma transação do encaminhamento.
`PKG_ATENDIMENTO.MARCAR_ATRASADOS`, agendado a cada 15 minutos, enfileira um
único aviso por reporte cujo prazo venceu e cujo status continua aberto. Atraso
é derivado do prazo e status atual, não um evento mutável no histórico.

## Oracle

Execute os scripts como proprietário do schema:

```sql
@db/schema.sql
@db/seed_routing.sql
@db/pkg_reportes.sql
@db/pkg_auth.sql
@db/pkg_jobs.sql
@db/pkg_roteamento.sql
@db/pkg_atendimento.sql
@db/jobs_scheduler.sql
```

Para instalações existentes, aplique também
`@db/migrations/V003__citizen_push_notifications.sql` após a migração V002.
Recompile `pkg_jobs.sql`, `pkg_roteamento.sql` e `pkg_atendimento.sql` nessa
ordem e então execute `@db/jobs_scheduler.sql`. A conta precisa das permissões
de `DBMS_SCHEDULER` para criar `JOB_ATRASADOS`.

Para gerar o MER/DER no Oracle SQL Developer Data Modeler, importe
[`db/oracle_data_modeler_ddl.sql`](./db/oracle_data_modeler_ddl.sql) como arquivo
DDL. Esse arquivo contém tabelas, chaves, restrições e índices, sem seeds,
packages ou triggers.

Configure `DB_USER`, `DB_PASSWORD`, `DB_DSN`, `JWT_SECRET`, os parâmetros SMTP
e `REPORT_REPOSITORY=oracle` no `.env`. A API abre o pool ao iniciar e falha
explicitamente se o banco ou a configuração estiver indisponível.

`REPORT_REPOSITORY=memory` é restrito ao ambiente `development` e perde os
dados ao reiniciar o processo.

## Executar

```bash
cd back-end
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Em outro processo, com o mesmo `.env`, execute o worker Oracle:

```bash
cd back-end
python -m app.infrastructure.worker
```

O worker separado exige `REPORT_REPOSITORY=oracle`; a API pode dar início
oportunista a um job, mas o worker separado é responsável pela recuperação e
pela drenagem contínua da fila.

Documentação interativa: `http://localhost:8000/docs`.

Testes:

```bash
python -m unittest discover -s tests/unit -v
```
