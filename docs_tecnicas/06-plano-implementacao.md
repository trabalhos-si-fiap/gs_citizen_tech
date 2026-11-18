# Plano de implementação pendente

**Atualizado em:** 17/11/2026

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
- **Integração Flutter pendente:** solicitar permissão após login; obter e
  registrar token/plataforma em `PUT /v1/me/devices`; sincronizar rotação do
  token e removê-lo em `DELETE /v1/me/devices` ao sair ou revogar a permissão;
  tratar push em primeiro plano e ao abrir, consultando `GET /v1/reports/{id}`
  para atualizar o estado local. Sem permissão, manter atualização por consulta
  ao abrir a lista e em primeiro plano, no máximo a cada 60 segundos.
- **Pendente validar:** fluxo SMTP real no MailHog; compilar e executar schema,
  pacotes e `DBMS_SCHEDULER` em Oracle compatível. A integração FCM real também
  depende de credenciais Firebase do ambiente.

### 5. Ações do reporte e moderação

- Implementar reabertura dentro da janela configurada, cobrança somente para
  reportes atrasados e com limite de repetição, e sinalização de conteúdo
  (RN-13, RN-14).
- Criar persistência transacional e eventos imutáveis para as ações, com
  autorização por papel e justificativas obrigatórias quando aplicável.
- Implementar a fila e os endpoints de moderação para reportes sem regra,
  jobs esgotados e conteúdo sinalizado; registrar ações administrativas em
  trilha de auditoria.
- Completar as transições e os endpoints do órgão para atualizar status e
  justificar resolução/contestação.
- Implementar deduplicação e agrupamento de reportes antes do encaminhamento,
  respeitando raio, janela temporal, categoria e limites configuráveis (RT-36,
  RT-37).
- **Aceite:** testes cobrem autorização, janelas, idempotência, limites e
  transições inválidas; eventos e projeções continuam consistentes.

### 6. LGPD e analítica

- Implementar exportação dos dados pessoais, exclusão/anonimização de conta e
  correção de dados; definir retenção com orientação jurídica antes de fixar
  prazos (RT-48, RT-51, RT-53).
- Aplicar auditoria a operações administrativas e limitar papéis/privilégios
  de banco (RT-47, RT-50).
- Criar geração incremental de indicadores, sem dados pessoais, com
  pseudonimização/agregação e proteção por contagem mínima (RT-41, RT-42).
- Implementar API de métricas e exportação CSV; concluir painéis público, do
  órgão, de moderação e de gestão, usando somente a API (RT-43, RT-44).
- **Aceite:** exportação e exclusão verificadas ponta a ponta; consultas
  analíticas reproduzíveis com dados sintéticos; células abaixo do limiar não
  são expostas.

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

### 7. Validação Oracle real

- Aplicar schema e migrações em Oracle compatível com o alvo; compilar todos os
  packages e resolver erros PL/SQL.
- Validar criação/transações, idempotência, reserva concorrente com
  `FOR UPDATE SKIP LOCKED`, leases, retries, terminalização e operações de
  foto/moderação.
- Executar testes de integração concorrentes e verificar consistência entre
  `schema.sql`, migrações, packages e DDL do Data Modeler.
- Validar operação com API e workers separados, pool, permissões mínimas,
  volume compartilhado de fotos, backup e restauração.
- **Aceite:** instalação limpa e upgrade de banco existente concluídos; testes
  de integração/utPLSQL e fluxo ponta a ponta passam em Oracle real.

## Lacunas transversais do projeto

- **Contrato da API:** comparar `04-openapi.yaml` com as rotas reais e
  implementar ou retirar do contrato rotas ainda ausentes, incluindo
  proximidade, ações do reporte, dispositivos, exportação/exclusão, agência e
  analítica.
- **Triagem automática:** implementar o encaminhamento após o período de
  confirmação, com a política definida para sugestão ausente ou ambígua
  (D10 / `TRIAGE_AUTO_CONFIRM_MINUTES`).
- **App Flutter:** além da integração de push detalhada na etapa 4, completar
  autenticação, upload assinado, triagem e acompanhamento; finalizar
  outbox/offline, retries e sincronização sem perda/duplicidade. As telas
  existentes não substituem os testes de integração contra a API.
- **Painéis:** o diretório `web/` ainda não constitui os painéis descritos na
  especificação; priorizar protótipo público e do órgão após a API de ações e
  indicadores.
- **Entrega e operação:** preparar CI, ambiente reproduzível (API, Oracle,
  worker e MailHog), lint/type-check, testes de contrato/e2e, rate limiting,
  métricas/logs/alertas, TLS, gestão de segredos e runbook de backup/restauração.
- **Decisões externas:** confirmar política de retenção e os pesos/premissas
  pendentes com jurídico e responsáveis de produto antes de fechar os critérios
  de produção.

## Fora do MVP atual

Reputação completa, moderação avançada e recursos de produção não especificados
continuam fora do escopo imediato; devem ser reavaliados depois do piloto
(RT-65).
