"""Detecta a faixa amarela/preta de "OVERFLOWED BY N PIXELS" do Flutter (debug).

O indicador usa o rótulo vermelho-escuro 0xFF900000 e o amarelo 0xBFFFFF00 e preto 0xBF000000 com 75% de opacidade;
sobre fundos claros o amarelo fica perto de (255, 255, 40..110), cor que o
tema do app não usa. Retorna as caixas (x1, y1, x2, y2) onde a faixa aparece.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def faixas_overflow(imagem: Path | Image.Image, minimo: int = 40) -> list[tuple[int, int, int, int]]:
    img = imagem if isinstance(imagem, Image.Image) else Image.open(imagem)
    img = img.convert("RGB")
    largura, altura = img.size
    px = img.load()
    celula = 24
    marcadas = set()
    for cy in range(0, altura, celula):
        for cx in range(0, largura, celula):
            amarelos = 0
            for y in range(cy, min(cy + celula, altura), 2):
                for x in range(cx, min(cx + celula, largura), 2):
                    r, g, b = px[x, y]
                    # faixa amarela (overflow grande) ou rótulo vermelho-escuro
                    # 0xFF900000 do texto "OVERFLOWED BY" (overflow pequeno)
                    if (r >= 248 and g >= 248 and 30 <= b <= 120) or (
                        140 <= r <= 148 and g <= 4 and b <= 4
                    ):
                        amarelos += 1
            if amarelos >= 6:
                marcadas.add((cx // celula, cy // celula))
    # agrupa células vizinhas
    caixas = []
    vistas = set()
    for c in marcadas:
        if c in vistas:
            continue
        pilha, grupo = [c], []
        vistas.add(c)
        while pilha:
            atual = pilha.pop()
            grupo.append(atual)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    viz = (atual[0] + dx, atual[1] + dy)
                    if viz in marcadas and viz not in vistas:
                        vistas.add(viz)
                        pilha.append(viz)
        if len(grupo) * 6 >= minimo // 4:
            xs = [g[0] for g in grupo]
            ys = [g[1] for g in grupo]
            caixas.append((min(xs) * celula, min(ys) * celula,
                           (max(xs) + 1) * celula, (max(ys) + 1) * celula))
    return caixas


if __name__ == "__main__":
    import sys
    for arquivo in sys.argv[1:]:
        print(arquivo, faixas_overflow(Path(arquivo)))
