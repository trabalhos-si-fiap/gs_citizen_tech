#!/usr/bin/env python3
"""Junta a narração gravada à demo.

Uso: python3 tests/e2e/narrar.py gravacoes/<pasta-da-demo>

Lê `falas/posicoes.json` da pasta: uma lista de trechos
{"arquivo": "1.ogg", "de": 0.0, "ate": 3.78, "em": 5.4}, em que `de`/`ate`
recortam o arquivo de fala e `em` é o segundo do vídeo onde o trecho entra.
Gera `00-demo-2min30-com-narracao.mp4` a partir de
`00-demo-2min30-sem-narracao.mp4`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fluxo.montagem import duracao  # noqa: E402
from fluxo.narracao import Trecho, mixar  # noqa: E402


def main() -> None:
    pasta = Path(sys.argv[1]).resolve()
    falas = pasta / "falas"
    video = pasta / "00-demo-2min30-sem-narracao.mp4"
    trechos = [Trecho(falas / t["arquivo"], t["de"], t["ate"], t["em"])
               for t in json.loads((falas / "posicoes.json").read_text())]
    total = duracao(video)
    for anterior, atual in zip(trechos, trechos[1:]):
        fim = anterior.em + anterior.fim - anterior.inicio
        if fim > atual.em + 0.6:
            raise SystemExit(f"{atual.arquivo.name}@{atual.em}s sobrepõe o trecho anterior (fim {fim:.1f}s)")
    ultimo = trechos[-1]
    if ultimo.em + ultimo.fim - ultimo.inicio > total:
        raise SystemExit("a narração passa do fim do vídeo")
    destino = mixar(video, trechos, pasta / "00-demo-2min30-com-narracao.mp4")
    print(f"{destino} ({duracao(destino):.1f}s)")


if __name__ == "__main__":
    main()
