// Interação "humana" no navegador: cursor visível no vídeo, movimento em
// curva, digitação tecla a tecla com ritmo irregular e erros corrigidos.

const VIZINHOS = {
  a: 'qwsz', b: 'vghn', c: 'xdfv', d: 'serfcx', e: 'wsdr', f: 'drtgvc',
  g: 'ftyhbv', h: 'gyujnb', i: 'ujko', j: 'huikmn', k: 'jiolm', l: 'kop',
  m: 'njk', n: 'bhjm', o: 'iklp', p: 'ol', q: 'wa', r: 'edft', s: 'awedxz',
  t: 'rfgy', u: 'yhji', v: 'cfgb', w: 'qase', x: 'zsdc', y: 'tghu', z: 'asx',
};

export const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
const aleatorio = (min, max) => min + Math.random() * (max - min);
const gauss = (media, desvio) => {
  const u = 1 - Math.random();
  const v = Math.random();
  return media + desvio * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
};

// Fator global de ritmo (demo curta usa > 1: pausas e gestos mais rápidos).
let RITMO = 1;
export const definirRitmo = (fator) => { RITMO = Math.max(0.5, fator); };

export const pausa = (min = 400, max = 1100) => dormir(aleatorio(min, max) / RITMO);

// Cursor desenhado na página (o vídeo do Playwright não mostra o do sistema).
export const SCRIPT_CURSOR = `
(() => {
  if (window.__cursorInstalado) return;
  window.__cursorInstalado = true;
  const instalar = () => {
    const c = document.createElement('div');
    c.id = '__cursor_e2e';
    c.innerHTML = '<svg width="22" height="28" viewBox="0 0 22 28"><path d="M2 2 L2 22 L7.5 17 L11 25 L14.5 23.5 L11 15.8 L18 15.8 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position: 'fixed', left: '0px', top: '0px', zIndex: 2147483647,
      pointerEvents: 'none', transform: 'translate(-2px,-2px)', transition: 'none'});
    const anel = document.createElement('div');
    Object.assign(anel.style, {position: 'fixed', width: '34px', height: '34px', marginLeft: '-17px',
      marginTop: '-17px', borderRadius: '50%', border: '3px solid rgba(235,225,0,.95)',
      background: 'rgba(235,225,0,.25)', zIndex: 2147483646, pointerEvents: 'none', opacity: '0',
      transform: 'scale(.4)', transition: 'transform .35s ease-out, opacity .45s ease-out'});
    document.documentElement.append(anel, c);
    const pos = window.__cursorPos || {x: 720, y: 450};
    c.style.left = pos.x + 'px'; c.style.top = pos.y + 'px';
    document.addEventListener('mousemove', (e) => {
      c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
      window.__cursorPos = {x: e.clientX, y: e.clientY};
    }, true);
    document.addEventListener('mousedown', (e) => {
      anel.style.transition = 'none'; anel.style.left = e.clientX + 'px'; anel.style.top = e.clientY + 'px';
      anel.style.opacity = '1'; anel.style.transform = 'scale(.4)';
      requestAnimationFrame(() => { anel.style.transition = 'transform .35s ease-out, opacity .45s ease-out';
        anel.style.transform = 'scale(1.2)'; anel.style.opacity = '0'; });
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', instalar);
  else instalar();
})();
`;

export class Humano {
  constructor(page, {velocidade = 1} = {}) {
    this.page = page;
    this.x = 960;
    this.y = 540;
    this.velocidade = velocidade * RITMO;
  }

  async moverPara(x, y) {
    const dist = Math.hypot(x - this.x, y - this.y);
    const passos = Math.max(8, Math.min(45, Math.round(dist / 18 / RITMO)));
    // Curva de Bézier com ponto de controle deslocado (mão não anda em reta).
    const cx = (this.x + x) / 2 + aleatorio(-0.2, 0.2) * dist;
    const cy = (this.y + y) / 2 + aleatorio(-0.2, 0.2) * dist;
    for (let i = 1; i <= passos; i++) {
      const t = i / passos;
      const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; // acelera e freia
      const px = (1 - e) ** 2 * this.x + 2 * (1 - e) * e * cx + e ** 2 * x;
      const py = (1 - e) ** 2 * this.y + 2 * (1 - e) * e * cy + e ** 2 * y;
      await this.page.mouse.move(px, py);
      await dormir(aleatorio(6, 14));
    }
    this.x = x;
    this.y = y;
  }

  async alvo(locator) {
    await locator.waitFor({state: 'visible', timeout: 20000});
    await locator.scrollIntoViewIfNeeded();
    await dormir(250);
    const caixa = await locator.boundingBox();
    if (!caixa) throw new Error('Elemento sem área visível');
    const x = caixa.x + caixa.width * aleatorio(0.35, 0.65);
    const y = caixa.y + caixa.height * aleatorio(0.4, 0.6);
    return {x, y};
  }

  async passarMouse(locator) {
    const {x, y} = await this.alvo(locator);
    await this.moverPara(x, y);
  }

  async clicar(locator) {
    const {x, y} = await this.alvo(locator);
    await this.moverPara(x, y);
    await pausa(120, 320);
    await this.page.mouse.down();
    await dormir(aleatorio(50, 110));
    await this.page.mouse.up();
    await pausa(250, 550);
  }

  intervalo(anterior) {
    let base = Math.max(35, gauss(105, 40));
    if (anterior === ' ') base += aleatorio(40, 200);
    else if (',.;:!?'.includes(anterior)) base += aleatorio(200, 500);
    if (Math.random() < 0.02) base += aleatorio(500, 1100);
    return base / this.velocidade;
  }

  // Digita no elemento já focado.
  async digitar(texto, {chanceErro = 0} = {}) {
    let anterior = '';
    const chars = [...texto];
    for (let i = 0; i < chars.length; i++) {
      const c = chars[i];
      const minuscula = c.toLowerCase();
      const meioPalavra = i > 0 && i < chars.length - 1 && /\p{L}/u.test(chars[i - 1]);
      if (chanceErro > 0 && VIZINHOS[minuscula] && meioPalavra && Math.random() < chanceErro) {
        const errada = VIZINHOS[minuscula][Math.floor(Math.random() * VIZINHOS[minuscula].length)];
        await this.page.keyboard.type(errada);
        await dormir(this.intervalo(errada));
        await dormir(aleatorio(250, 600)); // percebe o erro
        await this.page.keyboard.press('Backspace');
        await dormir(aleatorio(90, 200));
      }
      await this.page.keyboard.type(c);
      await dormir(this.intervalo(anterior));
      anterior = c;
    }
  }

  async preencher(locator, texto, opcoes = {}) {
    await this.clicar(locator);
    const atual = await locator.inputValue().catch(() => '');
    if (atual) {
      await this.page.keyboard.press('ControlOrMeta+a');
      await dormir(aleatorio(150, 300));
      await this.page.keyboard.press('Backspace');
    }
    await this.digitar(texto, opcoes);
  }

  async rolar(totalPx, {passo = 120} = {}) {
    const direcao = Math.sign(totalPx);
    let restante = Math.abs(totalPx);
    while (restante > 0) {
      const delta = Math.min(restante, passo + aleatorio(-30, 30));
      await this.page.mouse.wheel(0, direcao * delta);
      restante -= delta;
      await dormir(aleatorio(60, 140));
    }
    await pausa(400, 800);
  }
}
