# Roteiro de teste ponta a ponta gravado (app + painel web)

Automatiza o roteiro de demonstração de
[`docs_tecnicas/07-runbook-operacao.md`](../../docs_tecnicas/07-runbook-operacao.md#roteiro-de-demonstração-ponta-a-ponta):
o cidadão cria o reporte no app, a IA classifica e encaminha, o órgão atende,
redireciona ou modera no painel web e o cidadão acompanha no app.

- **App (celular Android real):** controlado por ADB. Os elementos são achados
  pela árvore de acessibilidade, os toques aparecem na tela ("mostrar toques")
  e o texto é digitado tecla a tecla, com ritmo irregular e erros corrigidos
  com backspace. A tela é gravada com o `scrcpy`.
- **Painel web:** Playwright no Google Chrome, com cursor desenhado na página,
  movimento do mouse em curva e digitação tecla a tecla. O Chrome roda em tela
  cheia numa tela virtual 1920x1080 (Xvfb) gravada pelo ffmpeg em 1080p/30 fps
  (o gravador embutido do Playwright gera vídeo de bitrate baixo e texto
  borrado).
- **Tomada simultânea (passo 2):** o painel já está aberto quando o celular
  envia a solicitação; assim que a cidadã confirma, o servidor busca o
  protocolo e abre o reporte recém-chegado. As duas gravações são alinhadas
  pelo horário de início e montadas lado a lado num vídeo 1920x1080.
- **Verificação:** depois de cada passo o estado é conferido pela API (órgão,
  status, triagem), então o roteiro também é um teste: passo que não chega ao
  estado esperado sai como FALHOU no relatório.

## Demo curta (até 2 min 30 s)

Para a apresentação existe um roteiro enxuto, gravado por `gravar_demo.py`.
Logins, códigos OTP e preparo acontecem antes de a câmera ligar; celular e
painel aparecem lado a lado nas cenas 1 e 2.

| Cena | Tempo-alvo | O que aparece |
|---|---|---|
| Abertura | 5 s | Cartão "Reclame Já — do celular do cidadão ao órgão responsável" |
| 1. Registro e chegada | 60 s | A cidadã anexa a foto, captura o GPS, descreve e envia; a IA classifica; o painel recebe o reporte com categoria e órgão |
| 2. Atendimento | 40 s | O órgão inicia o atendimento e resolve; o app mostra "Em andamento" e "Resolvido" |
| 3. Gestão | 37 s | Visão geral (30 dias), órgãos e prazos, indicadores públicos e CSV |
| Encerramento | 8 s | Cartão com os diferenciais |

Se uma cena passar do tempo-alvo, a montagem a acelera por igual (no máximo
2x). O vídeo final é `gravacoes/demo_<data>/00-demo-2min30.mp4`; as cenas
montadas ficam em `cenas/` e as gravações brutas em `app/` e `web/`.

```bash
python3 tests/e2e/galeria.py ocultar      # se houver fotos pessoais no celular
python3 tests/e2e/gravar_demo.py
python3 tests/e2e/galeria.py restaurar
```

Ficam de fora da demo (estão no roteiro completo): login, redirecionamento
entre órgãos, confirmação do vizinho e moderação.

## Passos

| # | Onde | O que acontece | O que é verificado |
|---|---|---|---|
| 1 | App | Cidadã (`ana.cidada@example.com`) aceita os termos e entra com o código OTP lido no Mailpit | Login concluído, mapa aberto |
| 2 | App + Web | Com o painel da gestora aberto em Gestão de Ocorrências, a cidadã cria o reporte (foto da galeria, GPS, ponto de referência, descrição, categoria "Água e Esgoto"), envia e confirma; o painel busca o protocolo e abre o reporte que acabou de chegar | Protocolo `RPT-…` no Oracle e visível no painel |
| 3 | App | Acompanhar chamado: classificação da IA e órgão responsável na linha do tempo | Categoria, subcategoria, urgência, órgão |
| 4 | Web | Operador do órgão inicial busca o protocolo, lê a linha do tempo e redireciona ao outro órgão com justificativa | Órgão trocado no banco |
| 5 | App | Detalhe aberto (atualiza a cada 20 s) mostra o novo órgão e o redirecionamento | Texto "Responsável: <novo órgão>" |
| 6 | Web | Novo órgão inicia o atendimento com prazo e resolve com justificativa | Status `resolvido` |
| 7 | App | App mostra o reporte resolvido | Status "RESOLVIDO" no app |
| 8 | App | Cidadã sai; vizinho (`bruno.vizinho@example.com`) entra, abre um reporte do feed, confirma (+1) e toca em "Relatar inconsistência" | Reporte em `in_moderation` |
| 9 | Web | Moderadora abre a fila, lê o reporte e rejeita com justificativa | Triagem `rejected` |
| 10 | Web | Gestora vê a Visão Geral (7 dias, 30 dias, 12 semanas), Indicadores públicos e exporta o CSV | Indicadores respondem e CSV baixado |

O órgão inicial vem da IA. Com "Água e Esgoto" o reporte costuma ir direto ao
Saneamento Demo; o passo 4 então redireciona para a Zeladoria (e vice-versa),
com a justificativa adequada a cada sentido.

No passo 8 o botão "Relatar inconsistência" do app só mostra uma mensagem (não
chama `POST /v1/reports/{id}/flag`); por isso a sinalização é enviada pela API
com o mesmo vizinho, e o relatório registra isso.

## Pré-requisitos

1. Stack no ar: `docker compose up --build --wait` (raiz do repositório). Para
   a IA real: `docker compose --profile ai up -d ollama` com o modelo baixado.
2. Servidores demo cadastrados (uma vez):

   ```bash
   ./scripts/provision-staff.sh zeladoria.demo@prefeitura.gov.br agency prefeitura-demo-zeladoria
   ./scripts/provision-staff.sh saneamento.demo@prefeitura.gov.br agency saneamento-demo
   ./scripts/provision-staff.sh moderadora.demo@prefeitura.gov.br moderator
   ./scripts/provision-staff.sh gestora.demo@prefeitura.gov.br manager
   ```

3. Celular Android com depuração USB e o app de debug instalado
   ([`mobile/README.md`](../../mobile/README.md)). O roteiro faz o
   `adb reverse tcp:8000 tcp:8000` sozinho e **apaga os dados do app** no
   passo 1 (começa da tela de boas-vindas).
4. Ferramentas na máquina: `adb`, `scrcpy` (3.x), `ffmpeg`, `Xvfb` (e
   `Xephyr` para `--ver-navegador`), Node 20+, Google Chrome e Python 3.10+
   com Pillow (`varrer_telas.py`).
5. Dependências do Playwright (uma vez): `cd tests/e2e/web && npm install`
   (usa o Chrome instalado, não baixa navegador).

### Fotos pessoais na galeria

O seletor de fotos do Android mostra todas as imagens do aparelho. Antes de
gravar, oculte as imagens pessoais (cópia de segurança no PC; nada é apagado):

```bash
python3 tests/e2e/galeria.py ocultar     # antes de gravar
python3 tests/e2e/galeria.py restaurar   # depois de gravar
```

Se houver imagens visíveis, o roteiro pausa a gravação enquanto o seletor está
aberto. A foto usada no reporte é de domínio público (veja
[`dados/CREDITOS.md`](dados/CREDITOS.md)).

A localização do reporte é a do GPS real do celular e aparece nos vídeos.

## Executar

```bash
python3 tests/e2e/executar_fluxo.py                  # roteiro completo, navegador oculto
python3 tests/e2e/executar_fluxo.py --ver-navegador   # mostra o Chrome numa janela (Xephyr) enquanto grava
python3 tests/e2e/executar_fluxo.py --sem-video-unico # não gera o vídeo completo

# depurar: só alguns passos, reaproveitando protocolo e órgãos de uma execução anterior
python3 tests/e2e/executar_fluxo.py --somente 8,9 --dados-de tests/e2e/gravacoes/<pasta>/dados.json
```

Leva cerca de 15 minutos. Os passos dependem uns dos outros; se o 2 ou o 3
falham, a execução para.

## Saída

Cada execução cria `tests/e2e/gravacoes/AAAA-MM-DD_HHMM/` (fora do git):

```text
00-demonstracao-completa.mp4   todos os passos em 1920x1080, com o título de cada um
lado-a-lado/02-*.mp4           tomada simultânea: celular envia, painel recebe
app/NN-app-*.mp4               gravação do celular de cada passo do app
web/NN-web-*.mp4               gravação do painel (1080p) de cada passo web
prints/                        prints dos momentos-chave (e da tela em caso de falha)
relatorio.md                   resultado por passo, verificações, notas e links
dados.json                     protocolos, ids e resultado de cada passo
execucao.log                   log detalhado com horários
```

## Outras ferramentas

- `varrer_telas.py`: percorre as telas do app logado e procura o aviso
  amarelo/preto de overflow do Flutter (só aparece em build de debug).
- `fluxo/`: driver Android (`android.py`), ritmo humano (`humano.py`), API e
  Mailpit (`api.py`) e detector de overflow (`overflow.py`).
- `fluxo/lado_a_lado.py`: monta a tomada simultânea a partir das duas gravações.
- `web/fluxo-web.mjs`: cenários do painel (`operador`, `atender`, `moderar`,
  `gestao`, `painel-ao-vivo`), que podem rodar sozinhos; `web/tela.mjs` cuida da
  tela virtual e da gravação em 1080p:
  `node fluxo-web.mjs gestao --dados '{"email":"gestora.demo@prefeitura.gov.br"}' --video /tmp/g.mp4 --prints /tmp/g`.

## Problemas encontrados pelo roteiro (19/11/2026)

Corrigidos (com teste que falhava antes):

- Overflows em 360 x 800 dp: chips de filtro do Mapa e do Feed (fonte carregada
  depois do primeiro frame), cartões de Canais de Emergência, botões de
  emergência e cabeçalho "Sugestão IA" do novo reporte, linha "Responsável:" no
  detalhe. Testes em `mobile/test/phone_layout_test.dart`,
  `late_fonts_*_test.dart` e `theme_fonts_preload_test.dart`.
- Mapa borrado em tela 3x (`retinaMode` desligado) e marcador de posição pouco
  claro (agora "Você está aqui"). Testes em `mobile/test/nearby_tabs_test.dart`.
- `GET /v1/public/metrics` (JSON e CSV) respondia 500: no Oracle a diferença de
  TIMESTAMPs é INTERVAL e o código fazia `float()` nela. Teste em
  `tests/smoke/test_stack.py` (`PublicMetricsSmokeTests`).
- Endereço em vez de latitude/longitude: o app faz a geocodificação reversa no
  aparelho (pacote `geocoding`), envia `address` e mostra "Rua, número – Bairro,
  Cidade" no assistente, na confirmação, na lista e no detalhe; o painel web
  mostra e busca pelo endereço (migração `V011__report_address.sql`).
- Datas: a API devolve horários com fuso (UTC) e o app mostra no horário local
  ("19/11/2026 às 20:18").
- Assistente de novo reporte: campos sem textos de exemplo, aviso honesto sem
  foto, contador de caracteres real (limite 300), sem o microfone simulado, sem
  o banner falso "Sugestão IA 98%" e sem categoria pré-escolhida ("Deixar a IA
  classificar" é o padrão, então a IA classifica de verdade).
- Tela de confirmação mostra a classificação real da IA (com estado
  "Analisando…"), a urgência e o órgão; sem vizinhos, prazos ou impactos
  inventados.
- Lista "Meus Reportes": título com a descrição (não mais "Ocorrência urbana"),
  categoria legível, endereço e data local.
- "Relatar inconsistência" abre um diálogo de motivos e chama
  `POST /v1/reports/{id}/flag` (visitante é convidado a entrar).
- Botão flutuante "Reportar problema" não cobre mais o fim das abas Perfil,
  Região e Reportes; categoria legível no detalhe; saudação usa o nome salvo.

- "Indicadores públicos" no painel ficava com "—" até um clique: a página usava
  campos comuns e, sem zone.js, a tela não sabia que a resposta tinha chegado.
  Agora usa signals. Teste em `web/src/app/public-metrics.component.spec.ts`.

Em aberto:

- "Ver mapa detalhado" no detalhe do app ainda mostra uma imagem fixa.
- O roteiro completo (passo 8) ainda sinaliza pela API; pode passar a usar o
  diálogo do app.
