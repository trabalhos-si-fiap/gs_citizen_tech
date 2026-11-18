# Pendências do projeto por camada

**Atualizado em:** 18/11/2026  
**Escopo:** backend, banco de dados, Flutter mobile e painel web.

Este inventário complementa o
[`06-plano-implementacao.md`](./06-plano-implementacao.md), detalhando o que
falta para sair do estado de implementação local e chegar a uma validação
integrada/piloto. Foi conferido com as rotas do backend, o DDL e migrations,
as telas mobile e os componentes Angular.

## Resumo executivo

| Camada | Estado | Pendência principal |
|---|---|---|
| Backend | Parcialmente implementado | Completar proximidade e triagem automática; integrar provedores e validar fluxos ponta a ponta |
| Banco de dados | **Concluído** | Nenhuma pendência de modelagem/DDL; apenas eventual homologação no Oracle-alvo |
| Flutter mobile | Integração em andamento | Feed/mapa público, configuração Firebase/OAuth nativa e teste integrado em dispositivo |
| Web Angular | Protótipos, com indicadores públicos integrados | Autenticação institucional e consumo real das APIs de gestão |
| Operação | Parcial | Ambientes, segredos, observabilidade, segurança e backup/restore de produção |

### Dependências que bloqueiam mais de uma camada

1. A rota pública de ocorrências próximas bloqueia o mapa e o feed comunitário
   mobile.
2. A decisão e implementação de autenticação institucional bloqueia os painéis
   web do órgão e de moderação.
3. Credenciais e configuração nativa Firebase bloqueiam push real no Flutter.
4. Provedor visual aprovado e decisão jurídica bloqueiam análise de imagem,
   classificação visual e desfoque real de rostos/placas.

## 1. Backend

### Prioridade alta — completar o fluxo funcional

- [ ] **Publicar ocorrências por proximidade.** O contrato
  [`04-openapi.yaml`](./04-openapi.yaml) descreve `GET /v1/reports/nearby`, mas
  a rota não está registrada em `back-end/app/api/routes/`. Implementar
  latitude/longitude, raio, filtros, ordenação/paginação e resposta pública
  mínima, sem dados pessoais.
- [ ] **Conectar o agrupamento automático de duplicados.** `report_groups` e
  confirmações existem, mas reportes novos são criados sem uma busca/decisão
  completa de correspondência por distância, categoria e janela temporal.
  Definir limites configuráveis e conservar um reporte canônico.
- [ ] **Automatizar a confirmação/triagem pendente.** Executar a política após
  `TRIAGE_AUTO_CONFIRM_MINUTES`, com idempotência e encaminhamento para
  moderação quando a sugestão estiver ausente ou ambígua.
- [ ] **Fechar a consistência do contrato OpenAPI.** Comparar cada operação
  publicada com rota, autenticação, schema, status HTTP e erros reais; remover
  contratos que não serão implementados ou implementar os que ainda faltam.

### Integrações externas e segurança de conteúdo

- [ ] Exercitar envio SMTP com MailHog e depois no ambiente homologado,
  verificando retries, idempotência, conteúdo sem identificadores do cidadão e
  tratamento de falha.
- [ ] Configurar credenciais e validar FCM real em homologação. O adaptador e o
  modo `log` existem; modo FCM depende do projeto/conta de serviço do ambiente.
- [ ] Manter o gate de verificação visual fail-closed e, antes de habilitar
  qualquer classificador, aprovar e integrar verificadores de conteúdo
  impróprio e de imagem gerada por IA.
- [ ] Substituir ou formalizar `NoOpRedactor`: hoje o código não desfoca rostos
  ou placas. Não tratar a imagem como anonimizada enquanto isso não for
  implementado e testado.
- [ ] Aprovar com jurídico/produto retenção, conteúdo permitido, transferência
  a terceiros e política de revisão humana para imagens.

### Validação do serviço

- [ ] Rodar testes de integração contra o backend configurado para Oracle:
  autenticação/refresh, criação idempotente, upload, worker, comentários,
  notificações, ações, moderação, LGPD e métricas.
- [ ] Testar concorrência, retries, leases expirados, reprocessamento e
  terminação de jobs em condições reais de falha.
- [ ] Definir política operacional de rate limiting, limites de payload, CORS
  por ambiente, gestão/rotação de segredos, TLS, logs sem dados pessoais,
  métricas, alertas e resposta a incidentes.

## 2. Banco de dados

### Implementação — concluída

- [x] Schema consolidado, constraints, índices, tabelas de apoio e migrations
  V002–V005.
- [x] Packages PL/SQL, scheduler e DDL de modelagem existentes no repositório.
- [x] MER/DER corrigidos para refletir o estado final pós-migrações em
  [`05-diagramas-mer-der.md`](./05-diagramas-mer-der.md).
- [x] DDL consolidado para importar no Oracle SQL Developer Data Modeler em
  [`back-end/db/oracle_data_modeler_ddl.sql`](../back-end/db/oracle_data_modeler_ddl.sql).

**Não há pendência de desenvolvimento do modelo ou do DDL do banco.** Para
importar no Data Modeler, usar o DDL consolidado indicado acima; para instalar
ou atualizar uma instância, usar `schema.sql` e a sequência de migrations,
conforme o runbook.

### Homologação de ambiente — atividade operacional, não pendência de modelo

- [ ] Se ainda não registrada no ambiente-alvo, executar instalação limpa e
  upgrade das migrations; confirmar compilação dos packages e execução do
  `DBMS_SCHEDULER`.
- [ ] Confirmar pool, privilégios mínimos, conexões da API/worker, backup e
  restauração no Oracle de homologação/produção.

Esses itens são critérios de implantação e validação operacional. Não alteram
o estado de conclusão do modelo lógico nem do DDL.

## 3. Flutter mobile

### Fluxos com integração iniciada

- Login por e-mail/OTP, persistência segura de tokens e refresh rotativo.
- Criação de reporte, captura de localização, seleção de imagem, upload
  assinado e fila local para envio posterior.
- Consulta de reportes próprios, detalhe, comentários, confirmações, correção
  de triagem, reabertura e cobrança.
- Exportação/exclusão LGPD e consulta de métricas públicas.
- Polling de acompanhamento e estrutura de push. Push está desligado por
  padrão e exige configuração Firebase do aplicativo/ambiente.

### Pendências antes de considerar a integração concluída

- [ ] **Mapa e feed público:** substituir o mapa ilustrativo e as fontes locais
  por dados da rota `/v1/reports/nearby`; hoje esses componentes ainda não
  apresentam ocorrências públicas reais.
- [ ] **Push em dispositivo:** configurar Firebase para cada plataforma,
  habilitar `ENABLE_FIREBASE_PUSH`, validar permissão, registro/rotação/remoção
  do token, push em foreground e abertura por push. Sem essa configuração, o
  polling permanece como fallback.
- [ ] **Android:** o projeto Flutter versionado contém scaffolding iOS e macOS,
  mas não possui diretório Android. Criar e configurar o target Android
  (permissões de localização/câmera, Firebase e build) se Android fizer parte
  do piloto.
- [ ] **Login Google:** não está integrado no app; a opção deve permanecer
  identificada como indisponível até configurar OAuth e validar o fluxo com o
  backend. Login por OTP é o fluxo disponível.
- [ ] Validar em aparelho/simulador os fluxos de permissão de localização,
  câmera/galeria, upload, retomada da outbox, sessão expirada, logout e
  notificações.
- [ ] Adicionar testes de integração da API e dos fluxos offline/erro; a análise
  estática e o smoke test não substituem teste ponta a ponta.
- [ ] Configurar `API_BASE_URL` por ambiente. `localhost` é apenas um default
  de desenvolvimento e não deve ser usado para um aparelho físico ou
  implantação.

## 4. Web Angular

### Já conectado

- [x] A página `/indicadores` consome `GET /v1/public/metrics` e oferece
  exportação CSV.

### Pendências funcionais

- [ ] Definir e implementar autenticação institucional e autorização por
  perfil. Não colocar `AGENCY_API_KEYS` ou credenciais privilegiadas no
  navegador; o mecanismo de acesso do órgão precisa ser aprovado e protegido.
- [ ] Substituir dados demonstrativos do dashboard por indicadores da API e
  implementar período, filtros, alertas, gráficos e exportação efetiva.
- [ ] Substituir a lista ilustrativa de ocorrências por consulta paginada à API;
  ligar busca, categoria, status, prioridade e prazo a filtros de servidor.
- [ ] Carregar o detalhe por identificador real e preencher linha do tempo,
  localização, categoria, prazo e anexos com a resposta da API.
- [ ] Persistir as ações da tela de detalhe: atualização de status com
  justificativa, redirecionamento, envio de atualização ao cidadão e consulta
  de órgãos. A UI atual altera estado local ou mostra mensagens demonstrativas.
- [ ] Integrar fila de moderação às rotas existentes, com autorização,
  justificativas, trilha de auditoria e tratamento de erros.
- [ ] Adicionar testes unitários, de contrato/API e e2e; validar acessibilidade,
  layout responsivo e comportamento de falha/sem dados.

O README do web identifica explicitamente as telas administrativas como
ilustrativas; elas não devem ser usadas para operação municipal até essas
integrações serem concluídas.

## 5. Entrega e operação

### Infraestrutura com Docker, Docker Compose e CI/CD

**Base já existente:** [`back-end/Dockerfile`](../back-end/Dockerfile),
[`docker-compose.yml`](../docker-compose.yml) com API, MailHog e volume de
fotos, e workflow
[`ci.yml`](../.github/workflows/ci.yml) com testes unitários do backend. A
configuração atual ainda não sobe o worker nem o Oracle e o CI não valida mobile,
web, build das imagens ou implantação contínua.

- [ ] Completar o Compose com worker, configuração compartilhada, conexão ao
  Oracle-alvo e healthchecks; validar volume compartilhado de fotos entre API e
  worker.
- [ ] Manter o Oracle como serviço externo/aprovado e documentar como apontar
  o ambiente local e o Compose para ele; não usar imagens de banco não oficiais
  ou desconhecidas.
- [ ] Separar configuração por ambiente e usar secrets fora do repositório;
  não incluir `.env` real, credenciais ou segredos nas imagens, artefatos e
  logs.
- [ ] Expandir CI para lint/type-check e testes do backend, análise/testes/build
  Flutter e lint/test/build Angular; construir e verificar as imagens Docker e
  adicionar testes de contrato/smoke conforme os serviços estiverem disponíveis.
- [ ] Criar CD para publicar imagens versionadas e implantar em homologação,
  executar smoke tests e exigir aprovação antes de produção; definir rollback.
- [ ] Adicionar varredura de vulnerabilidades de dependências e imagens ao
  pipeline.

### Operação dos ambientes

- [ ] Preparar ambientes separados de desenvolvimento, homologação e produção,
  com configuração de API, Oracle, worker, SMTP, Firebase e storage de fotos.
- [ ] Configurar TLS, CORS por ambiente, secrets manager, rotação de chaves,
  observabilidade, alertas e política de incidentes.
- [ ] Validar backup e restauração conjunta do Oracle e das fotos; documentar
  RPO/RTO e executar ensaio de restore.
- [ ] Confirmar retenção LGPD e critérios de produção com responsáveis jurídicos
  e de produto.

**Critério de conclusão:** stack reproduzível e validado no ambiente aprovado,
CI verde para as plataformas do piloto e implantação em homologação rastreável,
com smoke test e rollback documentados.

## Critério de encerramento

O projeto pode ser considerado pronto para piloto quando: as rotas usadas pelos
clientes estiverem implementadas e documentadas; mapa/feed mobile e painéis
administrativos usarem dados reais; nenhuma ação aparentar sucesso sem ser
persistida; OTP, upload, worker, notificações, ações, moderação e LGPD passarem
em testes ponta a ponta; e o runbook tiver sido executado no ambiente-alvo.
