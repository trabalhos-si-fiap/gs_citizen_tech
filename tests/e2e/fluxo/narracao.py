"""Mistura a narração gravada (trechos de áudio) no vídeo da demo.

Cada trecho é um pedaço de um arquivo de fala (`inicio`..`fim` dentro dele)
posicionado em `em` segundos do vídeo. O vídeo é copiado sem reencode.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .montagem import duracao


@dataclass
class Trecho:
    arquivo: Path
    inicio: float  # dentro do arquivo de fala
    fim: float
    em: float  # posição no vídeo


def mixar(video: Path, trechos: list[Trecho], destino: Path) -> Path:
    total = duracao(video)
    entradas: list[str] = ["-i", str(video)]
    filtros: list[str] = []
    for i, t in enumerate(trechos, start=1):
        entradas += ["-i", str(t.arquivo)]
        filtros.append(
            f"[{i}:a]atrim={t.inicio:.3f}:{t.fim:.3f},asetpts=PTS-STARTPTS,"
            f"aresample=48000,afade=t=in:d=0.04,afade=t=out:st={max(0.0, t.fim - t.inicio - 0.08):.3f}:d=0.08,"
            f"adelay={int(t.em * 1000)}:all=1[f{i}]"
        )
    rotulos = "".join(f"[f{i}]" for i in range(1, len(trechos) + 1))
    filtros.append(
        f"{rotulos}amix=inputs={len(trechos)}:normalize=0,"
        "highpass=f=80,volume=2dB,alimiter=limit=0.89:level=false,"
        f"apad,atrim=0:{total:.3f}[voz]"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *entradas,
         "-filter_complex", ";".join(filtros), "-map", "0:v", "-map", "[voz]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
         "-movflags", "+faststart", str(destino)],
        check=True,
    )
    return destino
