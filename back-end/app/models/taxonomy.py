"""Taxonomia compartilhada pelas rotas e pelo classificador."""

import json
from functools import lru_cache
from pathlib import Path
from enum import StrEnum


class ReportCategory(StrEnum):
    URBAN_RISK = "risco_urbano"
    PUBLIC_TRANSPORT = "transporte_publico"
    HEALTHCARE = "saude_atendimento"
    TO_CLASSIFY = "a_classificar"


@lru_cache(maxsize=1)
def load_taxonomy() -> dict[str, list[str]]:
    taxonomy_path = Path(__file__).resolve().parents[1] / "seeds" / "taxonomy.json"
    with taxonomy_path.open(encoding="utf-8") as taxonomy_file:
        taxonomy = json.load(taxonomy_file)
    if not isinstance(taxonomy, dict) or not all(
        isinstance(category, str)
        and isinstance(subcategories, list)
        and all(isinstance(item, str) for item in subcategories)
        for category, subcategories in taxonomy.items()
    ):
        raise RuntimeError("A taxonomia de classificação está inválida.")
    return taxonomy


def validate_taxonomy(
    category: ReportCategory,
    subcategory: str | None,
) -> None:
    subcategories = load_taxonomy().get(category.value)
    if subcategories is None:
        raise ValueError("Categoria não encontrada na taxonomia.")
    if subcategory is not None and subcategory not in subcategories:
        raise ValueError("Subcategoria não pertence à categoria informada.")
    if category == ReportCategory.TO_CLASSIFY and subcategory != "a_classificar":
        raise ValueError("A categoria a_classificar exige a subcategoria correspondente.")
