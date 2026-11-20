"""Ritmo humano para digitação e pausas, compartilhado pelo app e pelo web.

A ideia é que a gravação pareça uma pessoa usando o sistema: intervalos
irregulares entre teclas, pausas maiores depois de espaço e pontuação, uma
"pensada" de vez em quando e, opcionalmente, um erro de digitação corrigido
com backspace.
"""

from __future__ import annotations

import random
import time
import unicodedata

# Vizinhos no teclado QWERTY, usados para simular o erro de digitação.
_VIZINHOS = {
    "a": "qwsz", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wsdr",
    "f": "drtgvc", "g": "ftyhbv", "h": "gyujnb", "i": "ujko", "j": "huikmn",
    "k": "jiolm", "l": "kop", "m": "njk", "n": "bhjm", "o": "iklp",
    "p": "ol", "q": "wa", "r": "edft", "s": "awedxz", "t": "rfgy",
    "u": "yhji", "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu",
    "z": "asx",
}


def pausa(minimo: float = 0.4, maximo: float = 1.1) -> None:
    """Pausa curta de leitura/decisão entre ações."""
    time.sleep(random.uniform(minimo, maximo))


def intervalo_tecla(anterior: str, velocidade: float = 1.0) -> float:
    """Tempo (s) antes da próxima tecla. velocidade > 1 digita mais rápido."""
    base = max(0.035, random.gauss(0.13, 0.05))
    if anterior == " ":
        base += random.uniform(0.05, 0.25)
    elif anterior in ",.;:!?":
        base += random.uniform(0.25, 0.6)
    if random.random() < 0.02:  # "pensando" no meio da frase
        base += random.uniform(0.6, 1.3)
    return base / velocidade


def plano_digitacao(texto: str, chance_erro: float = 0.0) -> list[tuple[str, str]]:
    """Sequência de ações: ("char", c) | ("apaga", "") | ("hesita", "").

    Erros só acontecem em letras minúsculas no meio de palavras, para não
    estragar e-mails, códigos e números.
    """
    acoes: list[tuple[str, str]] = []
    for i, c in enumerate(texto):
        meio_palavra = 0 < i < len(texto) - 1 and texto[i - 1].isalpha()
        if (
            chance_erro > 0
            and c in _VIZINHOS
            and meio_palavra
            and random.random() < chance_erro
        ):
            acoes.append(("char", random.choice(_VIZINHOS[c])))
            if random.random() < 0.5:  # às vezes digita mais uma antes de notar
                prox = texto[i + 1] if i + 1 < len(texto) else ""
                if prox.isalpha():
                    acoes.append(("char", prox))
                    acoes.append(("hesita", ""))
                    acoes.append(("apaga", ""))
                else:
                    acoes.append(("hesita", ""))
            else:
                acoes.append(("hesita", ""))
            acoes.append(("apaga", ""))
        acoes.append(("char", c))
    return acoes


def sem_acentos(texto: str) -> str:
    """O `adb shell input text` não aceita caracteres fora do ASCII."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))
