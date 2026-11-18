"""Agrupamento automático de reportes duplicados (RT-36, RT-37)."""

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from app.core.config import settings
from app.core.geo import bounding_box, haversine_m
from app.infrastructure.repositories import ReportRepository, TriageConflict
from app.models.reports import DedupCandidate, TriageState


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_accents).split())


def _trigrams(text: str) -> set[str]:
    padded = f"  {text} "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def text_similarity(first: str | None, second: str | None) -> float:
    """Semelhança de Jaccard entre trigramas de caracteres (0 a 1).

    Ignora maiúsculas, acentos e pontuação. Texto vazio não tem semelhança.
    """
    a, b = _normalize(first or ""), _normalize(second or "")
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    grams_a, grams_b = _trigrams(a), _trigrams(b)
    return len(grams_a & grams_b) / len(grams_a | grams_b)


class DeduplicationService:
    """Vincula um reporte recém-classificado ao grupo de um reporte equivalente.

    Candidato: mesma categoria (e subcategoria, quando ambos têm), distância
    menor que o raio, criado na janela, grupo não resolvido nem em moderação.
    Com texto nos dois, exige semelhança mínima; sem texto em um deles (ainda
    não há comparação de imagem), exige distância menor que metade do raio.
    """

    def __init__(
        self,
        repository: ReportRepository,
        *,
        radius_m: float | None = None,
        window_days: int | None = None,
        text_threshold: float | None = None,
        max_candidates: int | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._radius_m = radius_m or settings.dedup_radius_meters
        self._window = timedelta(days=window_days or settings.dedup_window_days)
        self._threshold = (
            settings.dedup_text_similarity if text_threshold is None else text_threshold
        )
        self._max_candidates = max_candidates or settings.dedup_max_candidates
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def link_if_duplicate(self, report_id: UUID) -> bool:
        detail = self._repository.get_detail(report_id)
        if detail.triage_state != TriageState.AWAITING_USER:
            return False
        summary = detail.summary
        subcategory = detail.classification.subcategory if detail.classification else None

        best: tuple[float, float, DedupCandidate] | None = None
        for candidate in self._repository.list_dedup_candidates(
            report_id,
            bounding_box(summary.latitude, summary.longitude, self._radius_m),
            self._clock() - self._window,
            self._max_candidates,
        ):
            if candidate.category != summary.category:
                continue
            if subcategory and candidate.subcategory and subcategory != candidate.subcategory:
                continue
            distance = haversine_m(
                summary.latitude, summary.longitude, candidate.latitude, candidate.longitude
            )
            if distance >= self._radius_m:
                continue
            if _normalize(detail.description or "") and _normalize(candidate.description or ""):
                similarity = text_similarity(detail.description, candidate.description)
                if similarity < self._threshold:
                    continue
            else:
                similarity = 0.0
                if distance >= self._radius_m / 2:
                    continue
            if best is None or (-similarity, distance) < (-best[0], best[1]):
                best = (similarity, distance, candidate)

        if best is None:
            return False
        similarity, distance, candidate = best
        try:
            self._repository.link_to_group(
                report_id, candidate.group_id, similarity=similarity, distance_m=distance
            )
        except TriageConflict:
            return False
        return True
