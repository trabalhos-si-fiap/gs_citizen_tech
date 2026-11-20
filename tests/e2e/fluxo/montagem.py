"""Montagem da demo curta: cartões, faixa de título, ajuste de ritmo e emenda.

Cada cena tem um tempo-alvo. Se a gravação passar dele, a cena é acelerada
por igual (até `ACELERACAO_MAXIMA`); se ficar mais curta, entra como está.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

LARGURA, ALTURA = 1920, 1080
FUNDO = "0x111827"
AMARELO = "0xEBE100"
FONTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONTE_TEXTO = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
ACELERACAO_MAXIMA = 2.0
CODEC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-an"]


def texto(conteudo: str, fonte: str, cor: str, tamanho: int, x: str, y: str) -> str:
    """Filtro drawtext lendo o texto de um arquivo (sem escapes de ':', ',', '%')."""
    descritor, caminho = tempfile.mkstemp(prefix="drawtext-", suffix=".txt")
    with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)
    return (f"drawtext=fontfile={fonte}:textfile={caminho}:expansion=none:"
            f"fontcolor={cor}:fontsize={tamanho}:x={x}:y={y}")


def duracao(arquivo: Path) -> float:
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(arquivo)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(saida)


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def cartao(destino: Path, titulo: str, linhas: list[str], segundos: float) -> Path:
    """Cartão de abertura/encerramento: título amarelo e linhas brancas centralizadas."""
    topo = f"h/2-{125 + 31 * len(linhas)}"
    filtros = [texto(titulo, FONTE, AMARELO, 76, "(w-tw)/2", topo)]
    for i, linha in enumerate(linhas):
        filtros.append(texto(linha, FONTE_TEXTO, "white@0.9", 38, "(w-tw)/2",
                             f"h/2-{15 + 31 * len(linhas)}+{i * 62}"))
    filtros.append("fade=t=in:st=0:d=0.4")
    filtros.append(f"fade=t=out:st={segundos - 0.4:.2f}:d=0.4")
    _ffmpeg("-f", "lavfi", "-i", f"color=c={FUNDO}:s={LARGURA}x{ALTURA}:r=30:d={segundos}",
            "-vf", ",".join(filtros), *CODEC, str(destino))
    return destino


def com_faixa(origem: Path, destino: Path, titulo: str) -> Path:
    """Vídeo de uma tela só (painel 1080p) com a faixa de título da demo."""
    filtro = (
        "scale=1920:988:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:92:color={FUNDO},"
        + texto(titulo, FONTE, AMARELO, 38, "40", "(92-th)/2") + ",fps=30"
    )
    _ffmpeg("-i", str(origem), "-vf", filtro, *CODEC, str(destino))
    return destino


def no_tempo(origem: Path, destino: Path, alvo_s: float) -> tuple[Path, float]:
    """Deixa a cena com exatamente `alvo_s` segundos (a narração usa essa grade).

    Mais longa: acelera por igual (até ACELERACAO_MAXIMA) e corta o que sobrar.
    Mais curta: congela o último quadro até completar o tempo.
    """
    atual = duracao(origem)
    fator = min(ACELERACAO_MAXIMA, max(1.0, atual / alvo_s))
    sobra = max(0.0, alvo_s - atual / fator)
    filtro = f"setpts=PTS/{fator:.4f},fps=30"
    if sobra > 0:
        filtro += f",tpad=stop_mode=clone:stop_duration={sobra + 0.5:.2f}"
    _ffmpeg("-i", str(origem), "-vf", filtro + ",format=yuv420p", "-t", f"{alvo_s:.3f}",
            *CODEC, str(destino))
    return destino, fator


def emendar(partes: list[Path], destino: Path) -> Path:
    lista = destino.with_suffix(".txt")
    lista.write_text("".join(f"file '{p.resolve()}'\n" for p in partes))
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy",
            "-movflags", "+faststart", str(destino))
    lista.unlink()
    return destino
