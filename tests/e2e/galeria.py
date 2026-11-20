#!/usr/bin/env python3
"""Oculta as imagens pessoais da galeria do celular durante a gravação.

    python3 tests/e2e/galeria.py ocultar     # backup no PC + move para pasta oculta
    python3 tests/e2e/galeria.py restaurar   # devolve cada imagem ao lugar original
    python3 tests/e2e/galeria.py status

Nada é apagado: cada imagem é copiada para ~/.reclameja_e2e_galeria/backup e
movida, no próprio celular, para /sdcard/.e2e_galeria_oculta (com .nomedia),
o que a tira do seletor de fotos. O manifesto guarda o caminho original.
Imagens enviadas pelo próprio teste (Pictures/ReclameJaTeste) ficam visíveis.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PASTA_OCULTA = "/sdcard/.e2e_galeria_oculta"
PASTA_TESTE = "/storage/emulated/0/Pictures/ReclameJaTeste"
LOCAL = Path.home() / ".reclameja_e2e_galeria"
MANIFESTO = LOCAL / "manifesto.json"


def adb(*args: str, check: bool = True) -> str:
    return subprocess.run(["adb", *args], capture_output=True, text=True, check=check).stdout


def sh(comando: str) -> str:
    return adb("shell", comando)


def imagens_visiveis() -> list[str]:
    saida = sh("content query --uri content://media/external/images/media --projection _data")
    caminhos = []
    for linha in saida.splitlines():
        if "_data=" in linha:
            caminho = linha.split("_data=", 1)[1].strip()
            if not caminho.startswith(PASTA_TESTE):
                caminhos.append(caminho)
    return caminhos


def tamanho(caminho: str) -> str:
    return sh(f"stat -c %s '{caminho}' 2>/dev/null").strip()


def ocultar() -> None:
    manifesto = json.loads(MANIFESTO.read_text()) if MANIFESTO.exists() else []
    ja_ocultas = {item["original"] for item in manifesto}
    (LOCAL / "backup").mkdir(parents=True, exist_ok=True)
    sh(f"mkdir -p {PASTA_OCULTA} && touch {PASTA_OCULTA}/.nomedia")
    for original in imagens_visiveis():
        if original in ja_ocultas:
            continue
        nome_oculto = original.replace("/storage/emulated/0/", "").replace("/", "__")
        destino = f"{PASTA_OCULTA}/{nome_oculto}"
        copia = LOCAL / "backup" / nome_oculto
        adb("pull", original, str(copia))
        if not copia.exists() or str(copia.stat().st_size) != tamanho(original):
            sys.exit(f"Backup não confere para {original}; nada foi movido.")
        sh(f"mv '{original}' '{destino}'")
        if tamanho(destino) != str(copia.stat().st_size):
            sys.exit(f"Falha ao mover {original}; verifique {destino}.")
        manifesto.append({"original": original, "oculto": destino, "backup": str(copia)})
        MANIFESTO.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False))
        print(f"oculta: {original}")
    print(f"{len(manifesto)} imagem(ns) oculta(s). Backup em {LOCAL / 'backup'}")


def restaurar() -> None:
    if not MANIFESTO.exists():
        print("Nada a restaurar.")
        return
    manifesto = json.loads(MANIFESTO.read_text())
    pendentes = []
    for item in manifesto:
        pasta = item["original"].rsplit("/", 1)[0]
        if tamanho(item["oculto"]):
            sh(f"mkdir -p '{pasta}' && mv '{item['oculto']}' '{item['original']}'")
        elif not tamanho(item["original"]):
            # Não está no celular em nenhum dos dois lugares: devolve o backup.
            adb("push", item["backup"], item["original"])
        if tamanho(item["original"]):
            sh("am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE "
               f"-d 'file://{item['original']}' >/dev/null")
            print(f"restaurada: {item['original']}")
        else:
            pendentes.append(item)
    if pendentes:
        MANIFESTO.write_text(json.dumps(pendentes, indent=2, ensure_ascii=False))
        sys.exit(f"{len(pendentes)} imagem(ns) não restaurada(s); veja {MANIFESTO}")
    MANIFESTO.unlink()
    print("Galeria restaurada. O backup continua em", LOCAL / "backup")


def status() -> None:
    print("Visíveis (fora da pasta de teste):", len(imagens_visiveis()))
    if MANIFESTO.exists():
        print("Ocultas pelo teste:", len(json.loads(MANIFESTO.read_text())))


if __name__ == "__main__":
    acoes = {"ocultar": ocultar, "restaurar": restaurar, "status": status}
    if len(sys.argv) != 2 or sys.argv[1] not in acoes:
        sys.exit(__doc__)
    acoes[sys.argv[1]]()
