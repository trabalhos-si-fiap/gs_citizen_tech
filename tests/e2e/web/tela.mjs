// Tela virtual 1920x1080 para o Chrome e gravação dela em 1080p/30 fps.
//
// O gravador embutido do Playwright gera VP8 de bitrate baixo (texto borrado).
// Aqui o Chrome abre num X virtual (Xvfb, invisível; ou Xephyr, numa janela
// para acompanhar) e o ffmpeg grava esse display com x264 de alta qualidade.

import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';

import {dormir} from './humano.mjs';

export const LARGURA = 1920;
export const ALTURA = 1080;

function displayLivre() {
  for (let n = 90; n < 140; n++) {
    if (!existsSync(`/tmp/.X11-unix/X${n}`) && !existsSync(`/tmp/.X${n}-lock`)) return n;
  }
  throw new Error('Nenhum display X livre entre :90 e :139');
}

export async function abrirTela({visivel = false} = {}) {
  const numero = displayLivre();
  const display = `:${numero}`;
  const servidor = visivel
    ? spawn('Xephyr', [display, '-screen', `${LARGURA}x${ALTURA}`, '-ac', '-br', '-resizeable',
      '-title', 'Reclame Já — gravação do painel'], {stdio: 'ignore'})
    : spawn('Xvfb', [display, '-screen', '0', `${LARGURA}x${ALTURA}x24`, '-ac', '-nolisten', 'tcp'],
      {stdio: 'ignore'});
  const limite = Date.now() + 10000;
  while (!existsSync(`/tmp/.X11-unix/X${numero}`)) {
    if (Date.now() > limite || servidor.exitCode !== null) throw new Error(`Display ${display} não subiu`);
    await dormir(100);
  }
  await dormir(300);
  return {
    display,
    fechar: () => servidor.kill('SIGTERM'),
  };
}

// Argumentos do Chrome (sem aviso de automação nem oferta de tradução).
export const ARGS_CHROME = [
  `--window-size=${LARGURA},${ALTURA}`,
  '--window-position=0,0',
  '--lang=pt-BR',
  '--accept-lang=pt-BR,pt',
  '--no-first-run',
  '--no-default-browser-check',
  '--disable-session-crashed-bubble',
  '--hide-crash-restore-bubble',
  '--disable-features=Translate,TranslateUI',
  '--password-store=basic',
  // Sem GPU no X virtual: WebGL por software (o mapa do detalhe usa WebGL).
  '--use-gl=angle',
  '--use-angle=swiftshader',
  '--enable-unsafe-swiftshader',
  '--ignore-gpu-blocklist',
];

// Ambiente do Chrome: interface em português (senão ele oferece traduzir a página).
export function ambienteChrome(display) {
  return {...process.env, DISPLAY: display, LANG: 'pt_BR.UTF-8', LANGUAGE: 'pt_BR:pt'};
}

// Tela cheia de verdade (como F11): some a barra de abas e de endereço.
export async function telaCheia(page) {
  const cdp = await page.context().newCDPSession(page);
  const {windowId} = await cdp.send('Browser.getWindowForTarget');
  await cdp.send('Browser.setWindowBounds', {windowId, bounds: {windowState: 'fullscreen'}});
  await dormir(800);
  await cdp.detach();
}

export async function gravarTela(display, arquivo) {
  const ffmpeg = spawn('ffmpeg', [
    '-y', '-loglevel', 'error',
    '-f', 'x11grab', '-draw_mouse', '0', '-framerate', '30',
    '-video_size', `${LARGURA}x${ALTURA}`, '-i', `${display}.0+0,0`,
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart', arquivo,
  ], {stdio: ['pipe', 'ignore', 'pipe']});
  let erro = '';
  ffmpeg.stderr.on('data', (d) => { erro += d; });
  const inicioMs = Date.now();
  await dormir(500);
  if (ffmpeg.exitCode !== null) throw new Error(`ffmpeg não iniciou: ${erro}`);
  return {
    inicioMs,
    parar: () => new Promise((resolve) => {
      ffmpeg.once('exit', () => resolve());
      ffmpeg.stdin.write('q');
      ffmpeg.stdin.end();
      setTimeout(() => ffmpeg.kill('SIGINT'), 8000);
    }),
  };
}
