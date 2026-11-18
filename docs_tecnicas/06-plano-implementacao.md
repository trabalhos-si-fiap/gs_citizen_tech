# Plano de implementação pendente

**Atualizado em:** 18/11/2026

> O detalhamento atualizado por camada está em
> [`08-pendencias-por-camada.md`](./08-pendencias-por-camada.md). O banco de
> dados está concluído em termos de modelagem e DDL; o MER/DER vigente está em
> [`05-diagramas-mer-der.md`](./05-diagramas-mer-der.md).

**Escopo:** backend, integração com o app e validação para o piloto. A ordem abaixo
respeita a sequência definida para o MVP; classificação de imagens permanece
depois das verificações de segurança.

## Concluído

1. **Worker durável:** fila Oracle com leases, recuperação de jobs expirados,
   backoff e execução em processo separado. A compilação e os testes em Oracle
   real continuam pendentes na etapa 7.
2. **Upload seguro de fotos:** URL HMAC, upload em streaming, verificação do
   hash/formato/tamanho, recodificação JPEG, remoção de EXIF, storage local e
   URLs temporárias de leitura. O processamento ocorre no worker.
3. **Organização da infraestrutura:** módulos soltos foram agrupados em
   [`back-end/app/infrastructure/`](../back-end/app/infrastructure/).

4. **LGPD e analítica em memória:** exportação, correção, exclusão, métricas
   públicas agregadas e CSV foram conectados à API. A auditoria de operações
   foi adicionada ao schema/migração. Consultas Oracle completas permanecem
   dependentes da compilação dos packages da etapa 7.
5. **Ações do reporte:** reabertura, cobrança limitada, sinalização,
   atualização pelo órgão e fila de moderação estão implementadas no
   repositório de desenvolvimento, com testes.
6. **Integração e operação:** o app foi preparado para exportação/exclusão pela
   API, o painel web consome indicadores públicos, CORS foi configurado e
   Docker Compose, Dockerfile, CI e runbook foram adicionados.

7. **Ações Oracle:** reabertura, cobrança, sinalização, atualização pelo órgão
   e fila de moderação têm implementação persistente direta por SQL com
   transação e auditoria.
8. **LGPD Oracle:** exportação, anonimização de vínculo, exclusão de dispositivos
   e confirmações, métricas agregadas e limiar mínimo de cinco registros por
   órgão têm implementação persistente direta.
9. **Gate visual:** o worker aceita uma etapa `verify_visual` que só conclui
   quando um verificador aprova a imagem; desativado ou sem provedor aprovado,
   o resultado é recusado e o reporte pode seguir para moderação.
10. **Validação automática concluída:** o backend compila e 84 testes unitários
    passam, incluindo API, autenticação, reportes, notificações, LGPD,
    analítica, ações de moderação e gate visual.
11. **Integração Flutter em andamento:** OTP, armazenamento seguro de tokens,
    refresh rotativo, criação de reportes com localização e foto, upload
    assinado, outbox, lista/detalhe, ações do reporte, LGPD e métricas públicas
    estão conectados no cliente. Faltam mapa/feed público, configuração
    Firebase por ambiente/plataforma, autenticação Google e validação ponta a
    ponta em dispositivo.

O desfoque de rostos e placas ainda é um no-op documentado. Não há classificação
de imagem, análise de conteúdo impróprio nem detector de imagem gerada por IA.

## Próximas etapas, na ordem acordada

### 4. Notificações

- **Parcialmente concluído:** encaminhamento ao órgão por e-mail via SMTP,
  disparado por job idempotente; job Oracle durável com tentativas e backoff;
  após esgotar tentativas, o reporte vai para moderação. O e-mail contém dados
  operacionais e não inclui nome, e-mail ou ID do cidadão (RN-43, RT-38).
- Implementado: registro e remoção de tokens por conta, adaptador FCM e modo
  `log`, jobs de status no encaminhamento e tarefa Oracle a cada 15 minutos
  para reportes com prazo vencido. Payload de push contém somente tipo, ID e
  status; sem token, o acompanhamento segue disponível (RT-15, RT-39).
- **Flutter conectado no cliente; integração de push real depende do ambiente:**
  o código solicita permissão após login, registra/rotaciona/remove tokens em
  `/v1/me/devices`, trata abertura e foreground consultando
  `/v1/reports/{id}` e mantém polling de até 60 segundos como fallback. Validar
  com Firebase configurado e dispositivos de cada plataforma.
- **Pendente validar:** fluxo SMTP real no MailHog; compilar e executar schema,
  pacotes e `DBMS_SCHEDULER` em Oracle compatível. A integração FCM real também
  depende de credenciais Firebase do ambiente.

### 5. Ações do reporte e moderação

- [x] Reabertura dentro da janela configurada, cobrança limitada para reportes
  atrasados e sinalização de conteúdo (RN-13, RN-14).
- [x] Persistência transacional, eventos imutáveis e autorização por papel nas
  ações; justificativas são exigidas quando aplicável.
- [x] Fila/endpoints de moderação para reportes sem regra, jobs esgotados e
  conteúdo sinalizado; ações administrativas registradas em auditoria.
- [x] Transições e endpoints do órgão para atualizar status e justificar
  resolução/contestação.
- [ ] Implementar deduplicação e agrupamento de reportes antes do encaminhamento,
  respeitando raio, janela temporal, categoria e limites configuráveis (RT-36,
  RT-37).
- **Aceite:** testes cobrem autorização, janelas, idempotência, limites e
  transições inválidas; eventos e projeções continuam consistentes.
- **Estado atual:** implementação em memória concluída e coberta por testes;
  persistência Oracle de reabertura, cobrança, sinalização, status do órgão,
  auditoria e fila de moderação foi conectada aos métodos da API. Compilação e
  validação concorrente em Oracle real permanecem pendentes.

### 6. LGPD e analítica

- [x] Exportação de dados pessoais, exclusão/anonimização de conta e correção
  de dados (RT-48, RT-51, RT-53); [ ] definir retenção com orientação jurídica.
- [x] Auditoria das operações administrativas (RT-47); [ ] validar papéis e
  privilégios mínimos no banco Oracle de homologação (RT-50).
- [x] Geração de indicadores sem dados pessoais, com agregação e limiar mínimo
  (RT-41, RT-42).
- [x] API de métricas e exportação CSV; [ ] concluir painéis do órgão, de
  moderação e de gestão usando somente a API (RT-43, RT-44).
- **Aceite:** exportação e exclusão verificadas ponta a ponta; consultas
  analíticas reproduzíveis com dados sintéticos; células abaixo do limiar não
  são expostas.
- **Estado atual:** exportação, correção, exclusão, auditoria, JSON/CSV e
  agregações com limiar mínimo estão implementados no backend de memória;
  métodos Oracle equivalentes foram conectados. Falta validar pacote e migração
  em Oracle real.

### Verificações de imagem e classificação visual

Executar esta etapa **somente depois das etapas 4, 5 e 6**, conforme solicitado.

- Integrar verificações de conteúdo impróprio e detecção de imagens geradas por
  IA antes de qualquer classificação visual; definir limites, indisponibilidade,
  retenção e encaminhamento para revisão humana.
- Só então habilitar classificação visual e sua integração com classificação
  textual, triagem e matriz de roteamento. Não enviar imagens a provedores
  externos sem decisão explícita e controles aprovados.
- Substituir ou formalizar a limitação do `NoOpRedactor`; não apresentar o
  desfoque de rostos/placas como proteção existente até ser validado.
- **Aceite:** testes provam que conteúdo reprovado não chega ao classificador,
  falhas dos verificadores não geram aprovação automática e os resultados
  visuais podem ser auditados.
- **Estado atual:** gate fail-closed implementado no worker e coberto por
  testes. Nenhum provedor externo está habilitado por padrão.

### 7. Homologação operacional em Oracle

O modelo e o DDL do banco estão concluídos. Esta etapa é somente a validação de
implantação no ambiente Oracle-alvo; não é uma pendência de desenho ou de
implementação do banco.

- Aplicar schema e migrations em Oracle compatível com o alvo; confirmar a
  compilação dos packages PL/SQL e do `DBMS_SCHEDULER`.
- Validar criação/transações, idempotência, reserva concorrente com
  `FOR UPDATE SKIP LOCKED`, leases, retries, terminalização e operações de
  foto/moderação.
- Executar testes de integração concorrentes e verificar consistência entre
  `schema.sql`, migrações, packages e DDL do Data Modeler.
- Validar operação com API e workers separados, pool, permissões mínimas,
  volume compartilhado de fotos, backup e restauração.
- **Aceite:** instalação limpa e upgrade de banco existente concluídos; testes
  de integração/utPLSQL e fluxo ponta a ponta passam em Oracle real.

### 8. Infraestrutura com Docker, Docker Compose e CI/CD

Há uma base de infraestrutura versionada: Dockerfile do backend, Compose para
API/MailHog/volume de fotos e CI com testes unitários do backend. A etapa
adicional é completar e validar o fluxo reproduzível de desenvolvimento até
homologação/produção.

- [x] Dockerfile para a API, `docker-compose.yml` inicial e workflow de CI
  executando os testes unitários do backend.
- [x] Incluir o worker no Compose e configurar API/worker para compartilharem
  configuração, conexão Oracle e volume de fotos; definir healthchecks e ordem
  de inicialização sem depender apenas de `depends_on`. Ver
  [`09-containers-docker.md`](./09-containers-docker.md).
- [x] Validar o stack com Oracle 23ai Free em container: schema, migrations,
  packages e `DBMS_SCHEDULER` aplicados e verificados pelo `db-migrate`.
  [ ] Confirmar a imagem de banco aprovada pela equipe.
- [ ] Expandir CI para lint/type-check e testes do backend, análise/testes/build
  Flutter e lint/test/build Angular; validar também a construção das imagens e
  executar smoke/contrato quando as dependências estiverem disponíveis.
- [ ] Implementar CD para publicar imagens versionadas e implantar em
  homologação com smoke test, gestão de secrets e aprovação explícita antes de
  produção; documentar rollback.
- [x] Adicionar verificação de vulnerabilidades de dependências/imagens e
  garantir que credenciais e arquivos `.env` reais nunca sejam incluídos nos
  artefatos ou logs.
- **Aceite:** configuração Compose válida, stack validado com serviços
  disponíveis, CI verde para as plataformas incluídas no piloto e implantação
  em homologação rastreável e reversível.

## Lacunas transversais do projeto

### Pendências externas, não cobertas por implementação local

- Compilar e executar schema, migrações V004/V005, packages e `DBMS_SCHEDULER`
  em Oracle real.
- Validar SMTP real no MailHog/ambiente homologado e credenciais FCM Firebase.
- Habilitar verificadores visuais somente após decisão jurídica/produtiva e
  integração de um provedor aprovado.
- Concluir autenticação institucional do painel web, que permanece fora desta
  fase de backend.

- **Contrato da API:** comparar `04-openapi.yaml` com as rotas reais e
  implementar ou retirar do contrato rotas ainda ausentes. A rota de
  proximidade continua pendente; ações do reporte, dispositivos,
  exportação/exclusão, agência, moderação e analítica já têm rotas no backend.
- **Triagem automática:** implementar o encaminhamento após o período de
  confirmação, com a política definida para sugestão ausente ou ambígua
  (D10 / `TRIAGE_AUTO_CONFIRM_MINUTES`).
- **App Flutter:** completar mapa/feed contra uma rota pública de proximidade,
  habilitar push com a configuração Firebase do ambiente, decidir/integrar
  autenticação Google e executar testes ponta a ponta da outbox e dos fluxos
  reportados em dispositivo.
- **Estado atual:** login OTP, upload assinado, triagem, acompanhamento,
  ações do reporte, LGPD e métricas públicas estão ligados ao cliente. Push
  tem código condicionado à configuração Firebase; o app não substitui testes
  integrados contra o backend/Oracle.
- **Painéis:** o diretório `web/` ainda não constitui os painéis descritos na
  especificação; priorizar protótipo público e do órgão após a API de ações e
  indicadores.
- **Entrega e operação:** concluir a etapa 8 de Docker/Compose/CI/CD e preparar
  ambientes, testes de contrato/e2e, rate limiting, métricas/logs/alertas, TLS,
  gestão de segredos e runbook de backup/restauração.
- **Decisões externas:** confirmar política de retenção e os pesos/premissas
  pendentes com jurídico e responsáveis de produto antes de fechar os critérios
  de produção.
- **Inventário completo:** consultar
  [`08-pendencias-por-camada.md`](./08-pendencias-por-camada.md) para os itens
  detalhados de backend, banco, mobile, web e operação.

## Fora do MVP atual

Reputação completa, moderação avançada e recursos de produção não especificados
continuam fora do escopo imediato; devem ser reavaliados depois do piloto
(RT-65).
