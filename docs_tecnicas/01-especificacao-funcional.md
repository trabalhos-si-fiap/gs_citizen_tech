# Especificação Funcional — App de Reportes Cidadãos

Baseada nas Regras de Negócio (RN-xx). Itens marcados **[ASSUMIDO]** ou **[EXTENSÃO]** estão justificados em `00-LEIA-ME.md`, seção 4.

## 1. Visão

O app é um **canal único** para o cidadão registrar problemas urbanos, encaminhá-los ao órgão competente e acompanhá-los até o desfecho. Ele **não promete resolver** o problema, e sim garantir registro, rastreabilidade e transparência (RN-02). É gratuito para o cidadão (RN-05) e não substitui 190, 192, 193, o 156 nem as ouvidorias do SUS (RN-04).

Escopo de ocorrências (RN-03): transporte público, risco urbano e falhas de atendimento em saúde (UBS e UPA). Piloto em um território, com um tema em profundidade (RN-06; ver D2 e D3).

## 2. Atores e permissões

| Ação | Visitante | Cidadão | Órgão | Gestor | Moderador | Admin |
| :-- | :-: | :-: | :-: | :-: | :-: | :-: |
| Ver mapa e painel público | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Criar reporte | ✘ | ✔ | ✘ | ✘ | ✘ | ✘ |
| Confirmar (+1), sinalizar, reabrir, cobrar | ✘ | ✔ | ✘ | ✘ | ✘ | ✘ |
| Atualizar status, informar prazo, contestar com justificativa | ✘ | ✘ | ✔ (só do seu território) | ✘ | ✘ | ✘ |
| Painel de gestão | ✘ | ✘ | ✘ | ✔ | ✘ | ✔ |
| Revisar sinalizados e corrigir classificação | ✘ | ✘ | ✘ | ✘ | ✔ | ✔ |
| Editar matriz de responsabilidades | ✘ | ✘ | ✘ | ✘ | ✘ | ✔ (equipe do app) |

Regras: RN-07 (cadastro por e-mail ou Google; visitante só lê), RN-08 (nenhum ator pagante altera classificação, ranking ou painel público). ONGs parceiras (RN) não têm papel técnico no sistema.

## 3. Taxonomia de categorias **[ASSUMIDO]**

Fonte: `backend/app/seeds/taxonomy.json`. Extensível sem alterar código.

| Grupo (`category`) | Subcategorias (`subcategory`) | Destino típico (RN-18) |
| :-- | :-- | :-- |
| `risco_urbano` | `arvore_risco`, `esgoto_vazamento`, `calcada_danificada`, `iluminacao_falha`, `buraco_via`, `alagamento` | Prefeitura (zeladoria) ou saneamento |
| `transporte_publico` | `falha_trem_metro`, `onibus_atraso_lotacao`, `ponto_onibus_danificado`, `acessibilidade_estacao` | Operadora |
| `saude_atendimento` | `falta_medicamento`, `falta_medico`, `demora_atendimento`, `estrutura_unidade` | Ouvidoria da unidade ou secretaria de saúde |
| `a_classificar` | `a_classificar` | Fila de moderação → canal geral (RN-19) |

Urgência: `baixa`, `media`, `alta`.

## 4. Mapa de telas

```
Splash → [Onboarding + consentimento] → Login (e-mail OTP / Google)
                                              │
 ┌────────────────────────────────────────────▼───────────────────────────┐
 │ Home (mapa)  ──►  Novo reporte (3 passos) ──► Confirmação IA/órgão ──► Protocolo │
 │   │  ▲                                                                       │
 │   │  └─ atalho fixo "Emergência" (todas as telas) ──► Emergência (190/192/193)    │
 │   ├──► Detalhe da ocorrência (mapa) ──► Confirmar (+1) / Sinalizar              │
 │   └──► Meus reportes ──► Detalhe com linha do tempo ──► Reabrir / Cobrar novamente │
 │   Perfil e privacidade (exportar, excluir, sair)                                │
 └─────────────────────────────────────────────────────────────────────────┘
Visitante: Home (mapa, leitura) + Painel público (web)
Web: /public (painel público) e /panel (painel simples do órgão)
```

### 4.1 Requisitos transversais de interface

- Estados obrigatórios em toda lista e tela de dados: **vazio, carregando, sem conexão e erro**, com textos em pt-BR (RT-12).
- Acessibilidade: contraste WCAG AA, texto ≥ 16 px, áreas de toque ≥ 48 px, rótulos semânticos para leitores de tela (RT-13).
- **Faixa fixa** "Emergência? Ligue 190, 192 ou 193" em todas as telas do fluxo de reporte, mais um botão de atalho para a tela de Emergência (RN-27).
- Indicador discreto de conectividade e de itens pendentes de envio.
- Permissão de localização **somente em uso**; sem rastreamento em segundo plano (RN-42, RT-11).

### 4.2 Splash, onboarding e login

- Onboarding de 3 cartões: o que é o app, o que ele **não** faz (não resolve nem substitui emergência), privacidade.
- Consentimento explícito antes de criar conta: finalidade, link para política e termos; grava versão e data (RN-40).
- Login por e-mail (OTP de 6 dígitos, validade 10 min) ou Google (RN-07, D5).
- Menores de idade: exigir confirmação de idade mínima conforme `MIN_AGE_POLICY`; abaixo disso, bloquear cadastro e orientar o responsável (RN-45).
- **Critérios de aceite**
  - Dado um e-mail válido, quando solicito o código, então recebo um e-mail com 6 dígitos e a tela de verificação.
  - Dado o código correto, então entro e o token fica em armazenamento seguro.
  - Dado que não aceitei os termos, então o botão "Continuar" fica desabilitado.

### 4.3 Home (mapa)

- Mapa OpenStreetMap (RT, tabela de stack) centrado na localização do usuário (ou no centro do território, se negada).
- Marcadores de ocorrências próximas, com cor por status e ícone por categoria; filtros por categoria e status.
- Botão principal "Novo reporte"; barra inferior: Mapa, Meus reportes, Perfil.
- Visitante vê o mapa em leitura; ao tocar em "Novo reporte" é levado ao login.
- **Critérios de aceite**
  - Dado cache de mapa e sem rede, então vejo a última área carregada e o aviso "Sem conexão".
  - Dado que toco em um marcador, então vejo categoria, status, contagem de confirmações e data.

### 4.4 Novo reporte (3 passos) — RN-09, RN-11, RN-12

| Passo | Conteúdo | Regras |
| :-- | :-- | :-- |
| 1. Foto e descrição | Câmera/galeria (opcional) e descrição curta | Exigir **foto ou descrição** (RN-09). Foto comprimida no aparelho (RT-10). Filtro local de emergência (D9) |
| 2. Local | Pin no mapa com GPS e ajuste manual; endereço aproximado exibido | Sem GPS, o usuário marca o ponto (RT-11) |
| 3. Revisão e envio | Resumo, opção **"Reportar anonimamente"** (RN-12) e botão Enviar | Grava local primeiro; envia em segundo plano |

- Ao enviar, o reporte é salvo no banco local com `client_created_at` e entra na fila (RN-11). A tela vai para a **Confirmação IA/órgão** (online) ou para o **Protocolo provisório** (offline).
- **Critérios de aceite**
  - Dado que não informei foto nem descrição, então "Enviar" fica desabilitado e vejo a mensagem de campo obrigatório.
  - Dado que estou sem internet, quando envio, então o reporte aparece em "Meus reportes" como "Aguardando envio" com código `LOCAL-XXXXXXXX`.
  - Dado que a descrição contém termos de emergência, então vejo o diálogo de emergência antes de enviar, com "Ligar agora" e "Não é emergência, continuar".

### 4.5 Confirmação da IA e do órgão — RN-10, RN-16

- Mostra: categoria e subcategoria sugeridas, urgência e **órgão de destino** (vindo da matriz, não da IA).
- O cidadão **confirma** ou **corrige** a categoria; ao corrigir, o órgão é recalculado pelo servidor.
- Estados: "Analisando…" (até ~10 s, com indicador), sugestão pronta, **IA indisponível** (mostra a categoria informada ou seletor manual, RT-30), baixa confiança (pede confirmação, RT-27).
- Se o indicador de risco imediato vier verdadeiro, abrir a tela de Emergência por cima, mantendo o reporte registrado (RN-28, D9).
- **Critérios de aceite**
  - Dado que a IA respondeu, então vejo categoria, urgência e órgão; ao tocar "Confirmar", vou ao Protocolo.
  - Dado que a IA falhou, então posso escolher a categoria manualmente ou seguir como "a classificar".
  - Dado que sem confirmar passam 10 min, então o servidor encaminha automaticamente (D10).

### 4.6 Protocolo — RN-01

- Exibe o protocolo `RPT-AAAA-XXXXXX` (ou o provisório `LOCAL-…`), status "Recebido", órgão previsto, botão copiar/compartilhar e atalho para o acompanhamento.
- Texto explícito: "O app registra e encaminha; a resolução depende do órgão" (RN-02).
- **Critério de aceite:** todo reporte sincronizado tem protocolo único, mesmo que o órgão nunca responda (RN-01).

### 4.7 Meus reportes e detalhe — RN-13, RN-14, RN-15, RN-38

- Lista paginada dos reportes do usuário (inclusive anônimos, via vínculo de notificação, RN-12), com status e selo **"Atrasado"** quando vencido o prazo de referência (RT-39).
- Detalhe: foto, categoria, órgão, mapa, **linha do tempo** com data, hora e responsável de cada mudança (RN-15); justificativas do órgão ficam visíveis (RN-38).
- Ações:
  - **Reabrir** (só em `resolvido`, dentro de `REOPEN_WINDOW_DAYS`, RN-13);
  - **Cobrar novamente** (só se atrasado, RN-14);
  - **Confirmar (+1)** em reportes de terceiros, uma vez por usuário;
  - **Sinalizar abuso** (RN-35).
- **Critérios de aceite**
  - Dado um reporte resolvido há 3 dias, então "Reabrir" aparece; há 8 dias, não aparece.
  - Dado um reporte atrasado, quando toco "Cobrar novamente", então surge um evento `cobrado` na linha do tempo e o órgão é notificado.

### 4.8 Emergência — RN-27, RN-28, RN-32, RT-07

- Tela local (sem chamadas à API) com três botões grandes que abrem o discador: 190 (Polícia), 192 (SAMU), 193 (Bombeiros).
- Texto: o app não é botão de pânico nem canal de denúncia de crimes (RN-32). Segurança se limita a prevenção (iluminação, pontos de risco, acessibilidade).

### 4.9 Perfil e privacidade — RN-40, RN-41

- Exibir dados da conta, versão do consentimento, **exportar meus dados** (arquivo JSON), **excluir conta** (com confirmação), sair.
- Ao excluir: dados pessoais apagados; reportes já encaminhados permanecem **anonimizados** (RN-41).

### 4.10 Painel público (web, `/public`) — RN-46 a RN-50, RT-42 a RT-44

- Cards: tempo médio de resposta, taxa de resolução e total de reportes (ocorrências agrupadas).
- Mapa de calor por bairro, ranking de órgãos, linha do tempo mensal, filtros por período, categoria e órgão.
- Link para a **metodologia** (definição de "resolvido", prazos, exclusões, RN-48) e botão **Exportar CSV** (RN-49).
- Células com contagem menor que `PUBLIC_MIN_CELL_COUNT` são ocultadas.
- Sem login. Nenhum dado pessoal.

### 4.11 Painel simples do órgão (web, `/panel`) — RN-21, RT-64

- Acesso por chave de API do órgão (escopo de território).
- Lista de reportes encaminhados ao órgão, filtro por status, detalhe com foto e mapa.
- Ações: **Em andamento** (com prazo), **Resolvido** (com descrição), **Contestar** (com justificativa obrigatória, RN-38).
- O órgão vê o reporte **sem dados pessoais** (RN-43).

## 5. Ciclo de vida e status — RN-15, RT-05

Status visíveis ao cidadão e quem os altera:

| Status | Evento que o define | Quem altera |
| :-- | :-- | :-- |
| Recebido | `recebido` | Sistema |
| Encaminhado | `encaminhado` | Sistema |
| Em andamento | `em_andamento` (com prazo) | Órgão |
| Resolvido | `resolvido` | Órgão |

```
recebido ─► (classificado ─► classificacao_confirmada|corrigida) ─► encaminhado ─► em_andamento ─► resolvido
   │                │                                                  │                              │
   │                └─► enviado_moderacao ─► (canal geral, RN-19) ─────┘                              └─► reaberto ─► encaminhado
   └─ vinculado_grupo (duplicado)             contestado (órgão, com justificativa; status não regride)
```

Regras de derivação **[ASSUMIDO]**:

- O status atual é o do **último evento de status** (`recebido`, `encaminhado`, `em_andamento`, `resolvido`). `reaberto` volta o status para `encaminhado` e incrementa `reopened_count`.
- `contestado` (órgão) **não muda** o status; exibe a justificativa na linha do tempo (RN-38).
- `atrasado` é um **atributo derivado**, não um evento: `now > prazo_referência` e status ≠ `resolvido` (RT-39).
- Todo evento guarda `ator`, data/hora e, quando aplicável, justificativa e prazo (RN-15). Eventos são imutáveis (RT-21).

## 6. Regras de negócio — onde cada uma é implementada

| Regra | Resumo | Implementação |
| :-- | :-- | :-- |
| RN-01 | Protocolo único sempre | Serviço de reportes gera `protocol` ao criar; app mostra provisório offline (D11) |
| RN-02, RN-04 | Promessa limitada; não substitui emergência | Textos do Protocolo, onboarding e Emergência |
| RN-03, RN-06 | Três grupos; piloto de um território | Taxonomia e seed do território |
| RN-05 | Gratuito | Sem fluxo de pagamento no app |
| RN-07, RN-08 | Cadastro e neutralidade | Auth e papéis; painel público sem edição por contrato |
| RN-09 | Campos mínimos | Validação no app e no servidor (foto **ou** descrição + localização) |
| RN-10 | Confirmar categoria e órgão | Tela de triagem + `POST /v1/reports/{id}/triage` |
| RN-11 | Offline preservando data/hora | `client_created_at` enviado e gravado; fila local |
| RN-12 | Anonimato | `Report.user_id` nulo; vínculo em `NotificationLink` |
| RN-13 | Reabertura em 7 dias | Validação em `POST …/reopen` com `REOPEN_WINDOW_DAYS` |
| RN-14 | Cobrar novamente | `POST …/nudge` → evento `cobrado` + notificação ao órgão |
| RN-15 | Histórico de status | Event log e linha do tempo |
| RN-16 a RN-21 | Roteamento por matriz | Motor de roteamento; seed da matriz; e-mail/painel no piloto |
| RN-27, RN-28 | Aviso e interrupção por risco | Faixa fixa, filtro local, indicador de risco da IA |
| RN-29 a RN-31 | Saúde como ouvidoria | Sem campos clínicos; agregação por unidade e período |
| RN-32 | Sem pânico nem denúncia de crime | Textos de ajuda; categorias de segurança só preventivas |
| RN-33 a RN-38 | Reputação, moderação, sinalização, contestação | Modelo preparado; protótipo implementa só `flag` e contestação do órgão (D12) |
| RN-39 a RN-45 | Privacidade e LGPD | Coleta mínima, consentimento, exportar/excluir, localização só em uso, órgão sem dados pessoais, política etária |
| RN-46 a RN-51 | Transparência e painéis | Painel público e de gestão sobre a camada analítica |
| RN-52 a RN-54 | Contratação, conflito de interesse, custo por reporte | Fora do código, exceto a métrica de custo (observabilidade) |
| RN-55, RN-56 | Metas e ODS | Documentação; indicadores nos painéis |

## 7. Seeds de demonstração (RT-63)

- Território "Município Demo", 3 órgãos fictícios (Prefeitura Demo — Zeladoria, Saneamento Demo, Operadora Demo) e 1 ouvidoria de saúde fictícia.
- Matriz com uma regra por (categoria × território), prazos de referência fictícios (por exemplo, 72 h, 120 h, 240 h).
- 30 a 50 reportes fictícios espalhados, com eventos variados, para alimentar mapa e painéis.

## 8. Fora do escopo do protótipo (RT-65)

Reputação, moderação completa, painel de gestão B2G (filas priorizadas, alertas), integrações por API com 156 e canais oficiais, multi-município e administração da matriz por interface permanecem no roadmap, **sem implementação**. Como extensão do MVP, comentários públicos são permitidos a usuários autenticados, sem edição ou remoção; a confirmação “Vi isso” segue a regra +1 por grupo e por usuário.
