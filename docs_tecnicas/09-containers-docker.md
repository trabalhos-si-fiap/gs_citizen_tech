# Containers e Docker Compose

**Atualizado em:** 18/11/2026

Este documento descreve como o Reclame Já roda em containers: a topologia, as
decisões de segurança e otimização, o processo de migração do banco e como a
infraestrutura é testada. Complementa o
[`07-runbook-operacao.md`](./07-runbook-operacao.md).

## 1. Início rápido

Pré-requisitos: Docker Engine 24+ com Compose v2 e cerca de 4 GB de RAM livres
(o Oracle usa até 2 GB).

```bash
cp .env.example .env              # configuração não secreta
./scripts/init-secrets.sh         # gera ./secrets/*.txt (ignorado pelo git)
docker compose up --build --wait  # sobe tudo e espera os healthchecks
```

| Serviço | URL (somente em 127.0.0.1) |
|---|---|
| API (Swagger) | http://localhost:8000/docs |
| Painel web | http://localhost:4200 |
| Mailpit (e-mails de OTP e órgãos) | http://localhost:8025 |
| Oracle (SQL Developer, usuário `reclameja`) | `localhost:1521/FREEPDB1` |

IA local opcional: `docker compose --profile ai up --wait` e defina
`CLASSIFIER=ollama` no `.env`. Baixe o modelo uma vez com
`docker compose exec ollama ollama pull qwen2.5:3b`.

Para apagar tudo, inclusive dados: `docker compose down -v`.

## 2. Topologia: um container por função

```text
                  rede "app" (bridge)                      rede "data" (internal)
  navegador ──► web (nginx :8080)                        ┌──────────────────────┐
  navegador ──► api (uvicorn :8000) ─────────────────────┤ oracle (:1521)       │
                worker (fila Oracle) ────────────────────┤                      │
                db-migrate (execução única) ─────────────┤                      │
  api/worker ─► mailpit (SMTP :1025, UI :8025)           │ ollama (perfil "ai") │
                                                         └──────────────────────┘
```

| Container | Imagem | Função | Ciclo de vida |
|---|---|---|---|
| `oracle` | `gvenzl/oracle-free:23.6-slim-faststart` | Banco Oracle 23ai Free | contínuo |
| `db-migrate` | `reclame-ja/backend` | Aplica schema, migrations e packages PL/SQL | executa e termina |
| `api` | `reclame-ja/backend` | API HTTP FastAPI | contínuo |
| `worker` | `reclame-ja/backend` | Processa a fila: classificação, fotos, notificações | contínuo |
| `web` | `reclame-ja/web` | Painel Angular servido por nginx | contínuo |
| `mailpit` | `axllent/mailpit:v1.27` | SMTP de desenvolvimento com interface web | contínuo |
| `ollama` | `ollama/ollama:0.12.6` | LLM local (opcional, perfil `ai`) | contínuo |

`api`, `worker` e `db-migrate` usam **a mesma imagem** com comandos diferentes.
Assim o código implantado é idêntico nas três funções e só uma imagem é
construída e escaneada.

**Ordem de inicialização** (sem depender de `sleep`):
`oracle` saudável → `db-migrate` termina com sucesso → `api` e `worker` iniciam
(e esperam `mailpit` saudável). O `web` não depende do backend.

**Segregação do processamento:** com `INLINE_JOB_PROCESSING=false` a API só
enfileira jobs; quem processa é o container `worker`. Sem compose (modo
memória), o padrão `true` mantém o comportamento antigo em que a própria API
processa a fila.

## 3. Segurança

| Medida | Onde |
|---|---|
| Processo sem root (`api`/`worker`/`db-migrate`: UID 10001; `web`: UID 101) | Dockerfiles |
| Código da aplicação pertence ao root: o processo só lê | `back-end/Dockerfile` |
| Rootfs somente leitura; só `/tmp` (tmpfs) e o volume de fotos são graváveis | `read_only`, `tmpfs` |
| Todas as capabilities removidas e `no-new-privileges` | `cap_drop: [ALL]`, `security_opt` |
| Segredos como Docker secrets (arquivos em `/run/secrets`), nunca em variáveis de ambiente | `secrets:` + `SECRETS_DIR` |
| Portas publicadas somente em `127.0.0.1` | `ports` |
| Oracle e Ollama em rede `internal` (sem saída para a internet) | `networks.data` |
| Limites de memória em todos os serviços | `deploy.resources.limits` |
| Rotação de logs (10 MB × 3) | `x-logging` |
| Imagens de terceiros com tag fixa (sem `latest`) | `image:` |
| Patches de SO aplicados na construção (`apt-get upgrade`, `apk upgrade`) | Dockerfiles |
| `curl` removido da imagem web; healthchecks sem ferramentas extras (Python e wget do busybox) | Dockerfiles |
| nginx com `server_tokens off` e cabeçalhos `nosniff`, `X-Frame-Options`, `Referrer-Policy` e `Permissions-Policy` | `web/nginx.conf` |
| uvicorn sem cabeçalho `Server` | `--no-server-header` |
| `.dockerignore` impede `.env`, testes e artefatos locais no contexto de build | `*/.dockerignore` |
| Varredura Trivy: o CI falha com vulnerabilidade HIGH/CRITICAL que já tenha correção | `.github/workflows/ci.yml` |

**Segredos.** `scripts/init-secrets.sh` gera senhas aleatórias em `secrets/`
(pasta 700, ignorada pelo git) sem sobrescrever arquivos existentes. Os arquivos
ficam com modo 644 porque o Compose (fora do Swarm) monta o arquivo com as
permissões do host e os processos dos containers não são root. A proteção no
host vem da pasta 700. O `pydantic-settings` lê cada arquivo de
`SECRETS_DIR=/run/secrets` no campo de mesmo nome (`jwt_secret`, `db_password`,
`photo_upload_secret`, `agency_api_keys`). Variáveis de ambiente continuam tendo
precedência, o que mantém o uso fora de containers.

| Arquivo | Uso |
|---|---|
| `oracle_password` | SYS/SYSTEM do Oracle (só o container `oracle` recebe) |
| `db_password` | usuário da aplicação `reclameja` |
| `jwt_secret` | assinatura dos tokens de acesso |
| `photo_upload_secret` | HMAC das URLs de upload |
| `agency_api_keys` | chaves dos órgãos |

## 4. Otimização das imagens

| Imagem | Tamanho | Estratégia |
|---|---|---|
| `reclame-ja/backend` | ~200 MB | Multi-stage: dependências instaladas num virtualenv no estágio `builder`. O runtime copia só o virtualenv e o código, sem pip, setuptools, ensurepip, cache ou `__pycache__` |
| `reclame-ja/web` | ~75 MB | Multi-stage: `npm ci` e `ng build` em `node:alpine`. O runtime `nginx-unprivileged:alpine` contém só os arquivos estáticos (~0,4 MB) |

A ordem das camadas favorece o cache: `requirements.txt` e
`package-lock.json` são copiados antes do código, então alterar código não
reinstala dependências.

## 5. Banco de dados e migrations

O container `db-migrate` executa `python -m app.infrastructure.migrations`
(`back-end/app/infrastructure/migrations.py`), que aplica os scripts de
`back-end/db` direto pelo driver `oracledb`, sem SQL*Plus:

1. **Versionados**, uma vez cada, registrados na tabela `schema_migrations`:
   `schema.sql` (versão 001) e `migrations/V<NNN>__*.sql`. O `schema.sql` é
   consolidado e o cabeçalho `-- baseline-version: 004` informa que ele já
   contém V002 a V004. Em banco vazio essas migrations são só registradas. Em
   banco que já tenha histórico, rodam normalmente.
2. **Repetíveis**, a cada execução, por serem idempotentes: `seed_routing.sql`
   (MERGE), `pkg_*.sql` (`CREATE OR REPLACE`) e `jobs_scheduler.sql`.
3. **Recompilação** dos objetos inválidos (`DBMS_UTILITY.COMPILE_SCHEMA`) e
   falha se algum continuar inválido. Os packages são aplicados em ordem
   alfabética, e `pkg_atendimento` depende de `pkg_jobs`. Essa falha só
   apareceu no Oracle real.

O privilégio `CREATE JOB`, usado pelo `DBMS_SCHEDULER`, é concedido na
primeira inicialização do Oracle por `infra/oracle/initdb/01-grants.sql`. Esse
script supõe o usuário padrão `reclameja`. Se `ORACLE_APP_USER` mudar, ajuste o
script.

**Nova migration:** crie `back-end/db/migrations/V006__descricao.sql`. Se
também atualizar o `schema.sql` consolidado, altere o cabeçalho para
`-- baseline-version: 006`.

## 6. Como a infraestrutura é testada (TDD)

Cada mudança foi escrita a partir de um teste que falhou primeiro. Há três
camadas:

| Camada | Comando | O que garante |
|---|---|---|
| Unitária (backend) | `cd back-end && python -m unittest discover -s tests/unit` | Separação de scripts SQL/PL-SQL, ordem e baseline das migrations, recompilação, leitura de Docker secrets, CORS por ambiente, healthchecks, heartbeat do worker e desligamento do processamento inline |
| Estática (infra) | `python -m unittest discover -s tests/infra` | Topologia do compose (um serviço por função, perfil `ai`, ordem por saúde), endurecimento (`read_only`, `cap_drop`, `no-new-privileges`, tmpfs), segredos fora do ambiente, portas em loopback, imagens fixadas, limites de memória, Dockerfiles multi-stage sem root, `.dockerignore` e `secrets/` no `.gitignore` |
| Fumaça (stack real) | `python -m unittest discover -s tests/smoke` | Com o stack no ar: `/health`, cabeçalhos do nginx, login OTP com o código lido no Mailpit, criação idempotente de reporte no Oracle, classificação feita pelo container `worker`, processos sem root e rootfs somente leitura |

O teste de fumaça foi validado também em sentido negativo: com o `worker`
parado, ele falha ("worker não classificou o reporte").

O CI (`.github/workflows/ci.yml`) roda as três camadas. O job `containers`
constrói as imagens, roda o Trivy, sobe o stack completo, executa os testes de
fumaça e imprime os logs se algo falhar.

## 7. Decisões e limitações conhecidas

- **Imagem do Oracle.** `gvenzl/oracle-free` é mantida por Gerald Venzl
  (Oracle) e é a mesma usada pelo Testcontainers. É bem menor e sobe mais
  rápido (variante `faststart`) que a oficial
  `container-registry.oracle.com/database/free`. O
  [`08-pendencias-por-camada.md`](./08-pendencias-por-camada.md) pede imagens
  oficiais, então a imagem é configurável por `ORACLE_IMAGE` no `.env`. Em
  homologação e produção, o Oracle continua sendo um serviço externo aprovado:
  basta apontar `DB_DSN` para ele e não subir o serviço `oracle`.
- **Ollama roda como root** (limitação da imagem oficial). Por isso fica num
  perfil opcional e sem portas publicadas.
- **Mailpit** substitui o MailHog, que não recebe manutenção. A porta SMTP não
  é publicada no host, só a interface web.
- **Painel web e URL da API:** o Angular usa `http://localhost:8000` por
  padrão (`window.RECLAME_JA_API_URL`). Para outros ambientes é preciso injetar
  essa configuração; ficou para a integração do painel com a API.
- **Volume de fotos** compartilhado entre `api` e `worker`. Para várias
  réplicas em hosts diferentes é preciso storage compartilhado (pendência de
  operação).
- O CD (publicação de imagens versionadas e implantação em homologação) ainda
  não existe. As imagens já aceitam `REGISTRY_PREFIX` e `IMAGE_TAG`.

## 8. Solução de problemas

| Sintoma | Causa provável / ação |
|---|---|
| `db-migrate` termina com `exit 1` | `docker compose logs db-migrate`. A mensagem mostra o script e o número do comando. Corrija o SQL e rode `docker compose up -d` de novo; versões já registradas não são reaplicadas |
| `secret ... no such file` | Rode `./scripts/init-secrets.sh` |
| Oracle demora ou fica `unhealthy` | Precisa de cerca de 2 GB de RAM. Veja `docker compose logs oracle` |
| `permission denied` lendo `/run/secrets/*` | Arquivo de segredo criado à mão com modo 600. Use `chmod 644 secrets/*.txt` |
| Senha do banco trocada depois da primeira subida | O Oracle só lê as senhas na primeira inicialização. Use `docker compose down -v` (apaga os dados) ou altere a senha no banco |
