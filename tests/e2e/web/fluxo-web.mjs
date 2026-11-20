// Passos do painel web do roteiro, com gravação de vídeo e interação humana.
//
//   node fluxo-web.mjs <cenario> --dados '<json>' --video saida.mp4 \
//        --prints DIR [--headed] [--web http://127.0.0.1:4200]
//
// Cenários: operador | atender | moderar | gestao | painel-ao-vivo
//           demo-chegada | demo-atender | demo-gestao (demo curta: login fora da gravação)
// --ritmo N acelera pausas e digitação (padrão 1).
// O vídeo é 1920x1080/30 fps (tela virtual gravada pelo ffmpeg; veja tela.mjs).
// Com --headed a tela virtual abre numa janela (Xephyr) para acompanhar.
// No stderr, "PRONTO <epoch ms>" avisa quando o painel-ao-vivo está esperando.
// Última linha do stdout: JSON com { ok, video, inicioVideoMs, prints, notas, erro? }.

import {existsSync, mkdirSync, readFileSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {chromium} from 'playwright';

import {Humano, SCRIPT_CURSOR, definirRitmo, dormir, pausa} from './humano.mjs';
import {ARGS_CHROME, abrirTela, ambienteChrome, gravarTela, telaCheia} from './tela.mjs';

const MAILPIT = process.env.MAILPIT_URL ?? 'http://127.0.0.1:8025';

function argumentos() {
  const [cenario, ...resto] = process.argv.slice(2);
  const opcoes = {cenario, headed: false, web: 'http://127.0.0.1:4200'};
  for (let i = 0; i < resto.length; i++) {
    const chave = resto[i].replace(/^--/, '');
    if (chave === 'headed') opcoes.headed = true;
    else opcoes[chave] = resto[++i];
  }
  opcoes.dados = JSON.parse(opcoes.dados ?? '{}');
  return opcoes;
}

async function codigoOtp(email, depoisDe) {
  const limite = Date.now() + 30000;
  while (Date.now() < limite) {
    const url = `${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:"${email}"`)}&limit=5`;
    const resposta = await fetch(url).then((r) => r.json());
    for (const msg of resposta.messages ?? []) {
      const codigo = /\b(\d{6})\b/.exec(msg.Snippet ?? '');
      if (new Date(msg.Created) >= depoisDe && codigo) return codigo[1];
    }
    await dormir(1000);
  }
  throw new Error(`Código OTP não chegou para ${email}`);
}

class Sessao {
  constructor(page, h, opcoes) {
    this.page = page;
    this.h = h;
    this.opcoes = opcoes;
    this.prints = [];
    this.notas = [];
  }

  async print(nome) {
    const arquivo = join(this.opcoes.prints, `${nome}.png`);
    await this.page.screenshot({path: arquivo});
    this.prints.push(arquivo);
  }

  nota(texto) {
    this.notas.push(texto);
    console.error(`  ${texto}`);
  }

  async entrar(email) {
    const {page, h} = this;
    await page.goto(`${this.opcoes.web}/login`);
    await page.waitForSelector('#identity');
    await pausa(800, 1400);
    await h.preencher(page.locator('#identity'), email);
    const pedido = new Date(Date.now() - 2000);
    await h.clicar(page.locator('button.primary-login-button'));
    await page.locator('#code').waitFor({state: 'visible', timeout: 15000});
    const codigo = await codigoOtp(email, pedido);
    this.nota(`código OTP de ${email} lido no Mailpit`);
    await pausa(900, 1600); // "olhando o e-mail"
    await h.preencher(page.locator('#code'), codigo);
    await h.clicar(page.locator('button.primary-login-button'));
    await page.waitForURL(/\/dashboard/, {timeout: 20000});
    await page.waitForLoadState('networkidle');
    await pausa(1000, 1600);
  }

  async menu(titulo) {
    await this.h.clicar(this.page.locator(`nav a[title="${titulo}"], a[title="${titulo}"]`).first());
    await this.page.waitForLoadState('networkidle');
    await pausa(800, 1300);
  }

  async abrirOcorrencia(protocolo) {
    const {page, h} = this;
    await this.menu('Gestão de Ocorrências');
    const busca = page.getByRole('searchbox', {name: 'Buscar ocorrências'});
    await h.preencher(busca, protocolo);
    await pausa(300, 600);
    await page.keyboard.press('Enter');
    const link = page.locator('a.protocol-link', {hasText: protocolo});
    await link.waitFor({state: 'visible', timeout: 20000});
    await pausa(700, 1200);
    await h.clicar(link);
    await page.locator('section.incident-hero').waitFor({timeout: 20000});
    await page.waitForLoadState('networkidle');
    await pausa(1200, 1800);
  }

  async lerTimeline() {
    const {page, h} = this;
    await h.passarMouse(page.locator('section.timeline-card h2'));
    await h.rolar(500);
    await pausa(1200, 2000);
    await h.rolar(-500);
  }

  async aguardarRetorno() {
    const ok = this.page.locator('.action-feedback[role="status"]');
    const erro = this.page.locator('.action-feedback.error-feedback');
    await Promise.race([
      ok.waitFor({state: 'visible', timeout: 20000}),
      erro.waitFor({state: 'visible', timeout: 20000}),
    ]);
    if (await erro.isVisible()) throw new Error(`Painel recusou a ação: ${await erro.innerText()}`);
    this.nota(`painel: ${(await ok.innerText()).trim()}`);
    await pausa(1200, 1800);
  }
}

async function esperarSinal(s, h, etapa = null) {
  const arquivo = s.opcoes.sinal;
  if (!arquivo) throw new Error('Este cenário precisa de --sinal ARQUIVO');
  const limite = Date.now() + 15 * 60000;
  let proximoGesto = Date.now() + 4000;
  while (Date.now() < limite) {
    if (existsSync(arquivo)) {
      const texto = readFileSync(arquivo, 'utf8').trim();
      const sinal = texto ? JSON.parse(texto) : null;
      if (sinal && (etapa === null || sinal.etapa === etapa)) return sinal.protocolo;
    }
    if (Date.now() > proximoGesto) { // mexe o mouse de vez em quando, como quem espera
      await h.moverPara(400 + Math.random() * 1100, 250 + Math.random() * 600);
      proximoGesto = Date.now() + 3000 + Math.random() * 5000;
    }
    await dormir(250);
  }
  throw new Error('O celular não enviou o protocolo a tempo');
}

// ----------------------------------------------------------------- cenários
const cenarios = {
  // Operador do órgão encontra o reporte e (opcionalmente) redireciona.
  async operador(s, {email, protocolo, redirecionarPara, justificativa}) {
    await s.entrar(email);
    await s.print('01-painel');
    await s.abrirOcorrencia(protocolo);
    await s.print('02-detalhe');
    await s.lerTimeline();
    if (!redirecionarPara) return;
    const {page, h} = s;
    const painel = page.locator('.redirect-panel');
    await h.passarMouse(painel.locator('h3'));
    await pausa(600, 1000);
    const select = painel.locator('select');
    await h.clicar(select);
    await page.keyboard.press('Escape');
    await select.selectOption({label: redirecionarPara});
    s.nota(`destino escolhido: ${redirecionarPara}`);
    await pausa(500, 900);
    await h.preencher(painel.locator('textarea'), justificativa, {chanceErro: 0.03});
    await h.clicar(painel.getByRole('button', {name: /Redirecionar/}));
    await s.aguardarRetorno();
    await s.print('03-redirecionado');
    await s.lerTimeline();
  },

  // Novo órgão inicia o atendimento com prazo e depois resolve.
  async atender(s, {email, protocolo, prazoDias = 2, justificativa}) {
    const {page, h} = s;
    await s.entrar(email);
    await s.abrirOcorrencia(protocolo);
    await s.print('01-detalhe-novo-orgao');
    const acoes = page.locator('.action-card');
    await h.clicar(acoes.locator('label', {hasText: 'Iniciar atendimento'}));
    const prazo = new Date(Date.now() + prazoDias * 86400000);
    prazo.setHours(17, 0, 0, 0);
    const pad = (n) => String(n).padStart(2, '0');
    const valor = `${prazo.getFullYear()}-${pad(prazo.getMonth() + 1)}-${pad(prazo.getDate())}T17:00`;
    const campoPrazo = acoes.locator('input[type="datetime-local"]');
    await h.clicar(campoPrazo);
    await campoPrazo.fill(valor); // seletor nativo de data não aceita digitação livre
    s.nota(`prazo definido: ${valor}`);
    await pausa(600, 1000);
    await h.clicar(acoes.getByRole('button', {name: /Confirmar/}));
    await s.aguardarRetorno();
    await s.print('02-em-andamento');
    await h.clicar(acoes.locator('label', {hasText: 'Resolvido'}));
    await h.preencher(acoes.locator('textarea').first(), justificativa, {chanceErro: 0.03});
    await h.clicar(acoes.getByRole('button', {name: /Confirmar/}));
    await s.aguardarRetorno();
    await s.print('03-resolvido');
    await s.lerTimeline();
  },

  // Moderadora decide um reporte sinalizado.
  async moderar(s, {email, protocolo, decisao = 'Rejeitar', justificativa}) {
    const {page, h} = s;
    await s.entrar(email);
    await s.menu('Fila de moderação');
    await s.print('01-fila');
    const link = page.locator('a.protocol-link', {hasText: protocolo});
    await link.waitFor({state: 'visible', timeout: 20000});
    await pausa(800, 1300);
    await h.clicar(link);
    await page.locator('section.incident-hero').waitFor({timeout: 20000});
    await pausa(1200, 1800);
    const painel = page.locator('.action-panel', {has: page.locator('h3', {hasText: 'Moderação'})});
    await h.passarMouse(painel.locator('h3'));
    await h.preencher(painel.locator('textarea'), justificativa, {chanceErro: 0.03});
    await h.clicar(painel.getByRole('button', {name: decisao, exact: true}));
    await s.aguardarRetorno();
    await s.print('02-decidido');
    await s.lerTimeline();
  },

  // Painel aberto enquanto o cidadão envia pelo celular: quando o
  // orquestrador grava o protocolo no arquivo --sinal, o servidor busca o
  // reporte recém-chegado e abre o detalhe (classificação e órgão).
  async 'painel-ao-vivo'(s, {email}) {
    const {page, h} = s;
    await s.entrar(email);
    await s.menu('Gestão de Ocorrências');
    await s.print('01-painel-aguardando');
    console.error(`PRONTO ${Date.now()}`);
    const protocolo = await esperarSinal(s, h);
    s.nota(`protocolo recebido do celular: ${protocolo}`);
    await pausa(700, 1200);
    const busca = page.getByRole('searchbox', {name: 'Buscar ocorrências'});
    await h.preencher(busca, protocolo);
    await pausa(300, 600);
    await page.keyboard.press('Enter');
    const link = page.locator('a.protocol-link', {hasText: protocolo});
    await link.waitFor({state: 'visible', timeout: 30000});
    await h.passarMouse(page.locator('tr', {has: link}));
    await pausa(1500, 2200); // linha nova na tabela
    await s.print('02-reporte-chegou');
    await h.clicar(link);
    await page.locator('section.incident-hero').waitFor({timeout: 20000});
    await page.waitForLoadState('networkidle');
    await pausa(1500, 2200);
    await s.print('03-detalhe');
    await h.passarMouse(page.locator('.incident-tags'));
    await pausa(1200, 1800);
    await s.lerTimeline();
  },

  // ----- Demo curta: cada cenário tem `preparo` (fora da gravação) e `gravar`.

  // Gestora com a lista aberta; quando o celular envia, busca e abre o reporte.
  'demo-chegada': {
    async preparo(s, {email}) {
      await s.entrar(email);
      await s.menu('Gestão de Ocorrências');
    },
    async gravar(s) {
      const {page, h} = s;
      console.error(`PRONTO ${Date.now()}`);
      const protocolo = await esperarSinal(s, h);
      s.nota(`protocolo recebido do celular: ${protocolo}`);
      const busca = page.getByRole('searchbox', {name: 'Buscar ocorrências'});
      await h.preencher(busca, protocolo);
      await page.keyboard.press('Enter');
      const link = page.locator('a.protocol-link', {hasText: protocolo});
      await link.waitFor({state: 'visible', timeout: 30000});
      await h.passarMouse(page.locator('tr', {has: link}));
      await pausa(1200, 1600);
      await h.clicar(link);
      await page.locator('section.incident-hero').waitFor({timeout: 20000});
      await page.waitForLoadState('networkidle');
      await h.passarMouse(page.locator('.incident-tags'));
      await pausa(1800, 2200);
      await s.print('01-chegou');
      await h.passarMouse(page.locator('.detail-side-column').first());
      await pausa(1500, 1800);
    },
  },

  // Operador do órgão: abre o reporte, inicia o atendimento e resolve. Avisa
  // no stderr (STATUS ...) para o celular atualizar na hora.
  'demo-atender': {
    async preparo(s, {email}) {
      await s.entrar(email);
      await s.menu('Gestão de Ocorrências');
    },
    async gravar(s, {protocolo, justificativa}) {
      const {page, h} = s;
      console.error(`PRONTO ${Date.now()}`);
      const busca = page.getByRole('searchbox', {name: 'Buscar ocorrências'});
      await h.preencher(busca, protocolo);
      await page.keyboard.press('Enter');
      const link = page.locator('a.protocol-link', {hasText: protocolo});
      await link.waitFor({state: 'visible', timeout: 20000});
      await h.clicar(link);
      await page.locator('section.incident-hero').waitFor({timeout: 20000});
      await pausa(900, 1200);
      const acoes = page.locator('.action-card');
      await h.clicar(acoes.locator('label', {hasText: 'Iniciar atendimento'}));
      const prazo = new Date(Date.now() + 2 * 86400000);
      const pad = (n) => String(n).padStart(2, '0');
      await acoes.locator('input[type="datetime-local"]').fill(
        `${prazo.getFullYear()}-${pad(prazo.getMonth() + 1)}-${pad(prazo.getDate())}T17:00`);
      await h.clicar(acoes.getByRole('button', {name: /Confirmar/}));
      await s.aguardarRetorno();
      console.error(`STATUS em_andamento ${Date.now()}`);
      await esperarSinal(s, h, 'em_andamento');
      await h.clicar(acoes.locator('label', {hasText: 'Resolvido'}));
      await h.preencher(acoes.locator('textarea').first(), justificativa);
      await h.clicar(acoes.getByRole('button', {name: /Confirmar/}));
      await s.aguardarRetorno();
      console.error(`STATUS resolvido ${Date.now()}`);
      await s.print('01-resolvido');
      await esperarSinal(s, h, 'resolvido');
    },
  },

  // Gestora: visão geral, órgãos e indicadores públicos (sem login na gravação).
  'demo-gestao': {
    async preparo(s, {email}) {
      await s.entrar(email);
    },
    async gravar(s) {
      const {page, h} = s;
      // Só passa o mouse: se um texto mudar no painel, a cena segue.
      const apontar = async (texto, min = 900, max = 1200) => {
        const alvo = page.getByText(texto, {exact: true}).first();
        if (await alvo.isVisible().catch(() => false)) await h.passarMouse(alvo);
        await pausa(min, max);
      };
      await pausa(800, 1000);
      await h.clicar(page.getByRole('button', {name: 'Últimos 30 dias'}));
      await page.waitForLoadState('networkidle');
      await pausa(1200, 1500);
      await apontar('REPORTES NO PERÍODO');
      await apontar('EM ABERTO');
      await apontar('PRAZO VENCIDO');
      await apontar('TAXA DE RESOLUÇÃO');
      await h.rolar(650);
      await pausa(1500, 1800);
      await apontar('Órgãos', 1500, 1800);
      await s.print('01-orgaos');
      await h.rolar(-650);
      await s.menu('Indicadores Públicos');
      await page.getByText('Prefeitura Demo', {exact: false}).first().waitFor({timeout: 15000});
      await pausa(1000, 1300);
      await apontar('Resposta média (h)');
      await apontar('Taxa de resolução');
      await s.print('02-indicadores');
      const [download] = await Promise.all([
        page.waitForEvent('download', {timeout: 15000}),
        h.clicar(page.getByRole('button', {name: 'Exportar CSV'})),
      ]);
      await download.saveAs(join(s.opcoes.prints, 'indicadores.csv'));
      await pausa(1800, 2200);
    },
  },

  // Gestora vê o painel em três períodos, os indicadores e exporta CSV.
  async gestao(s) {
    const {page, h} = s;
    await s.entrar(s.dados.email);
    await page.locator('.period-switch, [class*="period"]').first().waitFor({timeout: 15000}).catch(() => {});
    await s.print('01-visao-geral');
    for (const periodo of ['Últimos 30 dias', 'Últimas 12 semanas', 'Últimos 7 dias']) {
      await h.clicar(page.getByRole('button', {name: periodo}));
      await page.waitForLoadState('networkidle');
      await pausa(1200, 1800);
    }
    await h.rolar(700);
    await s.print('02-categorias-orgaos');
    await h.rolar(700);
    await pausa(1000, 1600);
    await h.rolar(-1400);
    await s.menu('Indicadores Públicos');
    await s.print('03-indicadores');
    const [download] = await Promise.all([
      page.waitForEvent('download', {timeout: 15000}),
      h.clicar(page.getByRole('button', {name: 'Exportar CSV'})),
    ]);
    const csv = join(s.opcoes.prints, `indicadores-${Date.now()}.csv`);
    await download.saveAs(csv);
    s.nota(`CSV exportado: ${csv}`);
    await pausa(1000, 1500);
  },
};

// ------------------------------------------------------------------ execução
async function main() {
  const opcoes = argumentos();
  definirRitmo(Number(opcoes.ritmo ?? 1));
  const cenario = cenarios[opcoes.cenario];
  if (!cenario) throw new Error(`Cenário desconhecido: ${opcoes.cenario}`);
  mkdirSync(opcoes.prints, {recursive: true});
  mkdirSync(dirname(opcoes.video), {recursive: true});
  const tela = await abrirTela({visivel: opcoes.headed});
  const navegador = await chromium.launch({
    channel: 'chrome',
    headless: false,
    env: ambienteChrome(tela.display),
    args: ARGS_CHROME,
    ignoreDefaultArgs: ['--enable-automation'],
  });
  const contexto = await navegador.newContext({
    viewport: null,
    locale: 'pt-BR',
    timezoneId: 'America/Sao_Paulo',
    acceptDownloads: true,
  });
  await contexto.addInitScript(SCRIPT_CURSOR);
  const page = contexto.pages()[0] ?? await contexto.newPage();
  await page.goto('about:blank');
  await telaCheia(page);
  const h = new Humano(page);
  const sessao = new Sessao(page, h, opcoes);
  sessao.dados = opcoes.dados;
  let gravacao = null;
  let erro = null;
  try {
    if (cenario.preparo) await cenario.preparo(sessao, opcoes.dados); // fora da gravação
    gravacao = await gravarTela(tela.display, opcoes.video);
    await (cenario.gravar ?? cenario)(sessao, opcoes.dados);
    await pausa(1500, 2000); // respiro no fim do vídeo
  } catch (e) {
    erro = e;
    await sessao.print('erro').catch(() => {});
  } finally {
    if (gravacao) await gravacao.parar();
    await contexto.close().catch(() => {});
    await navegador.close().catch(() => {});
    tela.fechar();
  }

  const resultado = {ok: !erro, video: existsSync(opcoes.video) ? opcoes.video : null,
    inicioVideoMs: gravacao?.inicioMs ?? null, prints: sessao.prints, notas: sessao.notas,
    erro: erro ? String(erro.message ?? erro) : undefined};
  console.log(JSON.stringify(resultado));
  process.exitCode = erro ? 1 : 0;
}

main().catch((e) => {
  console.log(JSON.stringify({ok: false, erro: String(e.message ?? e)}));
  process.exitCode = 1;
});
