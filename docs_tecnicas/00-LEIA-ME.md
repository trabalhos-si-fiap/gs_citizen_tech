# App de Reportes Cidadãos — Pacote de especificação para implementação

> Origem: documentos "Regras de Negócio" (RN-xx) e "Regras Técnicas" (RT-xx), de 04/11/2026, Global Solution CitizenTech (FIAP).

## 1. Conteúdo do pacote

| Arquivo | Para que serve |
| :-- | :-- |
| `00-LEIA-ME.md` | Este arquivo: como trabalhar, estrutura do repositório, fases, decisões assumidas |
| `01-especificacao-funcional.md` | O que o app faz: atores, telas, fluxos, status, regras de negócio e critérios de aceite |
| `02-especificacao-tecnica.md` | Como é construído: arquitetura, dados, IA, roteamento, analítica, segurança, NFR e rastreabilidade RT |
| `03-guia-integracao-front-back.md` | Como front-end (Flutter) e back-end (FastAPI) se conectam: convenções, contratos, sincronização offline e passo a passo |
| `04-openapi.yaml` | Contrato da API v1, fonte da verdade para gerar clientes e testes |

## 2. Instruções ao implementador

1. **Leia os cinco arquivos antes de escrever código.** Ordem: 01 → 02 → 03 → 04.
2. **Códigos são âncoras.** Cada regra tem um código (RN-xx ou RT-xx). Cite o código em comentários de teste e em mensagens de commit (`feat(routing): aplica matriz vigente (RT-33, RN-16)`).
3. **Não invente regras.** Se algo não estiver especificado, use a decisão da seção 4. Se ainda for ambíguo, escolha a opção mais simples, registre em `docs/DECISOES.md` e siga em frente.
4. **Construa por fases** (seção 5). Cada fase termina com testes passando e o critério de pronto cumprido. Não avance com testes vermelhos.
5. **O contrato manda.** Se código e `04-openapi.yaml` divergirem, atualize o contrato primeiro, depois o código dos dois lados.
6. **Todo texto de interface em português do Brasil** (RT-12). Código, nomes de campo e identificadores em inglês.
7. **Dados de demonstração são fictícios** (RT-63). Nenhum dado pessoal real em seeds, testes ou capturas.
8. **Segredos nunca no repositório** (RT-46). Use `.env` (ignorado pelo git) e entregue um `.env.example`.

#

## 4. Decisões assumidas (lacunas e ambiguidades dos documentos-fonte)

| # | Lacuna | Decisão **[ASSUMIDO]** |
| :-- | :-- | :-- |
| D1 | O documento de negócio **não tem a seção 5**: os códigos **RN-22 a RN-26 não existem** (RN-24 é citado nas premissas como "pesos de prioridade"; supõe-se que a seção tratava de deduplicação e priorização). | Deduplicação segue RT-36/RT-37. Priorização do painel de gestão usa pesos configuráveis: urgência 50%, confirmações 30%, tempo em aberto 20% (`PRIORITY_WEIGHTS`). Fora do protótipo. **Pedir ao autor para confirmar o conteúdo da seção 5.** |
| D2 | Território do piloto não definido (RN-06). | Território fictício **"Município Demo"** com polígono GeoJSON em `seeds/territories/demo.geojson`. Trocar o seed troca o território, sem mudar código. |
| D3 | Tema em profundidade não escolhido. | Profundidade no grupo **risco urbano** (árvore, esgoto, calçada, iluminação); transporte e saúde entram como categorias (RN-06). |
| D4 | Nome do app em aberto. | Nome provisório **"Reporta"**, configurável em `APP_NAME` (backend) e `l10n` (app). |
| D5 | "Login por e-mail" (RT, `/v1/auth/login`) não especifica o mecanismo. | **Código de uso único (OTP) enviado por e-mail**, sem senha. Em desenvolvimento, o e-mail chega ao MailHog. Google: troca de ID token. |
| D6 | A API não lista endpoints para "cobrar novamente" (RN-14), confirmar a classificação (RN-10), exportar/excluir dados (RN-41, RT-51) e renovar token. | Adicionados como **[EXTENSÃO]**: `POST /v1/reports/{id}/nudge`, `POST /v1/reports/{id}/triage`, `GET /v1/me`, `GET /v1/me/export`, `DELETE /v1/me`, `PUT /v1/me/devices` (token de push), `POST /v1/auth/refresh`, `POST /v1/reports/{id}/photo/complete`. Ver `04-openapi.yaml`. |
| D7 | Upload de foto não especificado. | Duas etapas: `POST /v1/reports` (JSON) devolve URL de upload assinada; o app envia a foto em segundo plano e chama `photo/complete` (RT-10, RT-23). |
| D8 | Tipos de evento no RT-05 listam 6 tipos. | Mantidos os 6 e acrescentados tipos internos **[EXTENSÃO]**: `classificado`, `classificacao_confirmada`, `classificacao_corrigida`, `enviado_moderacao`, `vinculado_grupo`, `confirmacao_adicionada`, `cobrado`, `sinalizado`. O status visível ao cidadão continua sendo só os 4 do RN. |
| D9 | RN-28 pede interromper o fluxo "antes de registrar", mas a análise de foto por IA exige o servidor. | Duas camadas: (a) **filtro local por palavras-chave** no app, antes de enviar, com diálogo de emergência; (b) o indicador de risco imediato da IA, depois do registro, abre a tela de emergência e marca a urgência como alta. |
| D10 | Quando o cidadão não confirma a triagem (RN-10). | O encaminhamento ocorre após a confirmação; sem confirmação em `TRIAGE_AUTO_CONFIRM_MINUTES` (padrão 10), o sistema usa a sugestão da IA, ou a categoria informada, ou "a classificar" (RT-30, RN-19). |
| D11 | Protocolo offline (RN-01 exige protocolo único). | Offline, o app mostra um **código provisório** `LOCAL-XXXXXXXX` (8 primeiros caracteres do UUID). O protocolo oficial `RPT-AAAA-XXXXXX` é gerado no servidor ao sincronizar. |
| D12 | Reputação e moderação completas ficam fora do protótipo (RT-65). | Campos e filas existem no modelo, mas o protótipo não implementa telas de moderação nem cálculo de reputação. |
| D13 | Taxonomia de categorias não listada. | Ver `01-especificacao-funcional.md`, seção 3 (`seeds/taxonomy.json`), extensível sem mudança de código. |

## 5. Fases de implementação

| Fase | Escopo | Critério de pronto |
| :-- | :-- | :-- |
| **0. Fundação** | Monorepo, CI, docker-compose, `.env.example`, `contracts/openapi.yaml`, lint | `docker compose up` sobe backend + DynamoDB local + MailHog; CI verde |
| **1. Backend núcleo** | Auth, modelo de dados, `POST /v1/reports` idempotente, eventos imutáveis, upload, `GET` de reporte e timeline | Testes de contrato e unitários passam; reenvio do mesmo UUID não duplica |
| **2. IA e roteamento** | Classificador em duas etapas com fallback, matriz, motor de roteamento, e-mail ao órgão, triagem | Fluxo ponta a ponta no back: reporte → classificação → triagem → e-mail no MailHog |
| **3. App — caminho essencial (RT-64)** | Login, Home com mapa, Novo reporte, Confirmação IA/órgão, Protocolo, tela de Emergência | Cidadão de teste cria um reporte e vê o protocolo, ligado ao backend real |
| **4. Offline e sincronização** | Banco local, fila, backoff, compressão de foto, estados de UI | Teste: reportes criados sem rede sincronizam ao voltar, sem perda ou duplicidade |
| **5. Acompanhamento** | Meus reportes, detalhe com timeline, push, confirmar (+1), reabrir, sinalizar, cobrar | Órgão (painel simples) muda status e o app mostra a mudança + push |
| **6. Painéis e analítica** | Exportação de eventos, DuckDB, painel público, painel simples do órgão | Métricas de RT-41..44 reproduzíveis com dados sintéticos |
| **7. Endurecimento** | Segurança, LGPD (exportar/excluir), limite de taxa, observabilidade, backups, vídeo de reserva | Checklist de RT-45..56 cumprido; teste e2e do RT-58 verde |

Fases 0 a 3 correspondem ao **protótipo** da Global Solution (RT-64). As demais compõem o piloto. Itens de RT-65 ficam só documentados.

## 6. Parâmetros calibráveis (todos em configuração, nunca no código)

| Variável | Padrão inicial | Origem |
| :-- | :-- | :-- |
| `AI_CONFIDENCE_THRESHOLD` | 0.70 | RT-27 (a calibrar) |
| `DEDUP_RADIUS_METERS` | 50 | RT-36 (a calibrar) |
| `DEDUP_WINDOW_DAYS` | 14 | RT-36 (assumido) |
| `DEDUP_TEXT_SIMILARITY` | 0.80 | RT-36 (assumido) |
| `PHOTO_MAX_BYTES` | 1_000_000 | RT-10 (a calibrar) |
| `REOPEN_WINDOW_DAYS` | 7 | RN-13 (a validar) |
| `TRIAGE_AUTO_CONFIRM_MINUTES` | 10 | D10 |
| `PHOTO_WAIT_SECONDS` | 60 | tempo máximo para esperar a foto antes de classificar só com texto |
| `ACCESS_TOKEN_TTL_MIN` / `REFRESH_TOKEN_TTL_DAYS` | 15 / 30 | RT-16 |
| `PUBLIC_MIN_CELL_COUNT` | 5 | RT-42 (k-anonimato mínimo) |
| `RATE_LIMIT_USER_PER_MIN` / `RATE_LIMIT_IP_PER_MIN` | 60 / 120 | RT-18 |
| `MIN_AGE_POLICY` | 18 | RN-45 (confirmar com o jurídico) |

## 7. Definição de pronto global

- Todos os testes (unitários, contrato, e2e) passam no CI.
- O fluxo **Home → Novo reporte → Confirmação IA/órgão → Protocolo** funciona no aparelho/emulador contra o backend real.
- O app funciona com a IA desligada (`CLASSIFIER=null`) e sem rede (RT-03, RT-30).
- O aviso "Emergência? Ligue 190, 192 ou 193" aparece em todas as telas do fluxo de reporte (RN-27).
- Nenhum dado pessoal em logs, e-mails a órgãos ou painel público (RN-43, RT-42, RT-48).
