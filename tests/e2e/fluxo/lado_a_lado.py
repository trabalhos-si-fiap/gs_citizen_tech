"""Monta a tomada simultânea: celular à esquerda e painel web à direita.

As duas gravações começam em horários diferentes; o alinhamento usa o horário
de início (epoch, ms) de cada uma. Se a gravação do celular foi pausada (por
exemplo, com a galeria aberta), o intervalo aparece como um quadro escuro com
o aviso "galeria oculta".
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .montagem import texto

LARGURA, ALTURA = 1920, 1080
FUNDO = "0x111827"
AMARELO = "0xEBE100"
FONTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONTE_TEXTO = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Layout (px): faixa de título em cima, celular à esquerda, painel à direita.
TOPO = 92
CEL_W, CEL_H = 414, 920  # 9:20, como o S20 FE
CEL_X, CEL_Y = 32, TOPO + 8
WEB_X = CEL_X + CEL_W + 32
WEB_W = LARGURA - WEB_X - 32
WEB_H = WEB_W * 9 // 16
WEB_Y = CEL_Y + (CEL_H - WEB_H) // 2


def _duracao(arquivo: Path) -> float:
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(arquivo)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(saida)


def montar(
    video_celular: Path,
    trechos_ms: list[tuple[float, float]],
    video_web: Path,
    inicio_web_ms: float,
    destino: Path,
    titulo: str,
) -> Path:
    """`trechos_ms`: (início em epoch ms, duração em s) de cada trecho gravado
    do celular, na ordem em que estão emendados em `video_celular`."""
    if not trechos_ms:
        raise ValueError("Sem gravação do celular")
    deslocamentos, acumulado = [], 0.0
    for _, duracao in trechos_ms:
        deslocamentos.append(acumulado)
        acumulado += duracao
    trechos_celular = [(video_celular, inicio) for inicio, _ in trechos_ms]
    t0 = trechos_celular[0][1]  # o vídeo começa quando o celular começa a gravar
    duracoes = [duracao for _, duracao in trechos_ms]
    fim_celular = trechos_celular[-1][1] / 1000 + duracoes[-1]
    corte_web = max(0.0, (t0 - inicio_web_ms) / 1000)
    atraso_web = max(0.0, (inicio_web_ms - t0) / 1000)
    fim_web = inicio_web_ms / 1000 + _duracao(video_web)
    total = max(fim_celular, fim_web) - t0 / 1000

    entradas: list[str] = ["-f", "lavfi", "-i", f"color=c={FUNDO}:s={LARGURA}x{ALTURA}:r=30:d={total:.3f}"]
    filtros: list[str] = []
    partes = []
    for i, (arquivo, inicio_ms) in enumerate(trechos_celular):
        entradas += ["-ss", f"{deslocamentos[i]:.3f}", "-t", f"{duracoes[i]:.3f}", "-i", str(arquivo)]
        idx = i + 1
        filtros.append(
            f"[{idx}:v]fps=30,scale={CEL_W}:{CEL_H}:force_original_aspect_ratio=decrease,"
            f"pad={CEL_W}:{CEL_H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p[c{i}]"
        )
        partes.append(f"[c{i}]")
        if i + 1 < len(trechos_celular):
            fim = inicio_ms / 1000 + duracoes[i]
            lacuna = max(0.0, trechos_celular[i + 1][1] / 1000 - fim)
            if lacuna > 0.05:
                filtros.append(
                    f"color=c=0x1F2937:s={CEL_W}x{CEL_H}:r=30:d={lacuna:.3f},"
                    f"drawtext=fontfile={FONTE_TEXTO}:text='galeria oculta':fontcolor=white@0.8:"
                    f"fontsize=28:x=(w-tw)/2:y=(h-th)/2,format=yuv420p,setsar=1[g{i}]"
                )
                partes.append(f"[g{i}]")
    filtros.append(f"{''.join(partes)}concat=n={len(partes)}:v=1:a=0[cel]")

    idx_web = len(trechos_celular) + 1
    entradas += ["-ss", f"{corte_web:.3f}", "-i", str(video_web)]
    web = (
        f"[{idx_web}:v]fps=30,scale={WEB_W}:{WEB_H},setsar=1,format=yuv420p"
    )
    if atraso_web > 0.05:
        web += f",tpad=start_duration={atraso_web:.3f}:color={FUNDO}"
    filtros.append(web + "[web]")

    rotulos = ",".join([
        texto(titulo, FONTE, AMARELO, 38, "40", f"(({TOPO}-th)/2)"),
        texto("Celular do cidadão (app)", FONTE_TEXTO, "white@0.85", 22,
              f"{CEL_X}+({CEL_W}-tw)/2", f"{CEL_Y + CEL_H + 12}"),
        texto("Painel web da prefeitura", FONTE_TEXTO, "white@0.85", 22,
              f"{WEB_X}+({WEB_W}-tw)/2", f"{WEB_Y + WEB_H + 14}"),
    ])
    filtros.append(f"[0:v][cel]overlay={CEL_X}:{CEL_Y}:eof_action=repeat[a]")
    filtros.append(f"[a][web]overlay={WEB_X}:{WEB_Y}:eof_action=repeat,{rotulos},format=yuv420p[saida]")

    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *entradas,
         "-filter_complex", ";".join(filtros), "-map", "[saida]",
         "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-movflags", "+faststart", str(destino)],
        check=True,
    )
    return destino
