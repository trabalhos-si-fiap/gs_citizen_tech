#!/usr/bin/env python3
"""Percorre as telas do app e procura o aviso de overflow do Flutter.

    python3 tests/e2e/varrer_telas.py            # app já logado como cidadão
    python3 tests/e2e/varrer_telas.py --saida DIR

Para cada tela (e cada posição de rolagem) tira um print e roda o detector de
`fluxo/overflow.py`. Prints com overflow ficam marcados com "_OVERFLOW" no nome.
Exige build de debug (o aviso amarelo/preto só aparece em debug).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fluxo.android import Android, ElementoNaoEncontrado  # noqa: E402
from fluxo.overflow import faixas_overflow  # noqa: E402

PACOTE = "br.fiap.reclameja.reclame_ja_mobile"


class Varredura:
    def __init__(self, a: Android, saida: Path) -> None:
        self.a = a
        self.saida = saida
        self.n = 0
        self.achados: list[tuple[str, list]] = []

    def capturar(self, nome: str) -> None:
        self.n += 1
        time.sleep(0.8)
        arquivo = self.saida / f"{self.n:03d}_{nome}.png"
        self.a.print_tela(arquivo)
        faixas = faixas_overflow(arquivo)
        if faixas:
            novo = arquivo.with_name(arquivo.stem + "_OVERFLOW.png")
            arquivo.rename(novo)
            self.achados.append((novo.name, faixas))
            print(f"  OVERFLOW em {novo.name}: {faixas}")
        else:
            print(f"  ok {arquivo.name}")

    def tela_rolando(self, nome: str, rolagens: int = 6) -> None:
        anterior = None
        for i in range(rolagens):
            textos = self.a.texto_tela()
            if textos == anterior:
                break
            anterior = textos
            self.capturar(f"{nome}_{i}")
            self.a.rolar(True, 0.6)
        for _ in range(rolagens):
            self.a.rolar(False, 0.8)

    def tentar(self, descricao: str, acao) -> None:
        try:
            acao()
        except (ElementoNaoEncontrado, TimeoutError) as erro:
            print(f"  pulado ({descricao}): {erro}")


def aba(a: Android, nome: str) -> None:
    a.tocar_texto(contem=f"{nome}\nTab", timeout=6)
    time.sleep(1.5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--saida", type=Path,
                        default=Path(__file__).parent / "gravacoes" / "varredura"
                        / datetime.now().strftime("%Y-%m-%d_%H%M"))
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    a = Android()
    v = Varredura(a, args.saida)
    a.abrir_app(PACOTE)
    time.sleep(2)
    if a.existe(texto="Entrar com e-mail", timeout=3):
        v.tela_rolando("boas_vindas")
        sys.exit("Faça login no app antes da varredura das telas internas.")

    for nome in ("Mapa", "Reportes", "Feed", "Região", "Perfil"):
        v.tentar(nome, lambda nome=nome: (aba(a, nome), v.tela_rolando(f"aba_{nome}")))

    def detalhe() -> None:
        aba(a, "Feed")
        cartoes = [n for n in a.nos() if n.clicavel and len(n.texto) > 30
                   and "Tab" not in n.texto]
        if not cartoes:
            raise ElementoNaoEncontrado("nenhum cartão no feed")
        a.tocar(cartoes[0])
        time.sleep(2)
        v.tela_rolando("detalhe_feed", 10)
        a.tecla(4)
        time.sleep(1)

    v.tentar("detalhe do feed", detalhe)

    def meus() -> None:
        aba(a, "Reportes")
        cartoes = [n for n in a.nos() if n.clicavel and "RPT-" in n.texto]
        if not cartoes:
            raise ElementoNaoEncontrado("nenhum reporte próprio")
        a.tocar(cartoes[0])
        time.sleep(2)
        v.tela_rolando("detalhe_meu", 10)
        a.tecla(4)
        time.sleep(1)

    v.tentar("detalhe de reporte próprio", meus)

    def emergencia() -> None:
        aba(a, "Mapa")
        a.tocar_texto("Canais de Emergência")
        time.sleep(1.5)
        v.tela_rolando("emergencia")
        a.tecla(4)
        time.sleep(1)

    v.tentar("emergência", emergencia)

    def assistente() -> None:
        aba(a, "Mapa")
        a.tocar_texto("Reportar problema")
        time.sleep(1.5)
        for passo in range(1, 5):
            v.tela_rolando(f"novo_reporte_passo{passo}")
            if passo < 4:
                a.tocar_texto("Continuar")
                time.sleep(1.2)
        for _ in range(4):
            a.tecla(4)
            time.sleep(0.8)

    v.tentar("novo reporte", assistente)

    print()
    if v.achados:
        print(f"{len(v.achados)} print(s) com overflow em {args.saida}:")
        for nome, faixas in v.achados:
            print(f"  {nome}: {faixas}")
        sys.exit(1)
    print(f"Nenhum overflow encontrado ({v.n} prints em {args.saida}).")


if __name__ == "__main__":
    main()
