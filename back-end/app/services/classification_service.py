"""Orquestra classificação em duas etapas, fallback e cache TTL."""

import hashlib
import re
import threading
import time
from collections import OrderedDict

from app.infrastructure.classifiers import Classifier, ClassifierUnavailable
from app.core.config import settings
from app.models.classification import (
    ClassificationInput,
    ClassificationResult,
)
from app.models.reports import ReportCategory

CACHE_TTL_SECONDS = 24 * 60 * 60


class ClassificationService:
    def __init__(
        self,
        classifier: Classifier,
        *,
        model_small: str | None = None,
        model_large: str | None = None,
        confidence_threshold: float | None = None,
        cache_size: int | None = None,
        clock=time.monotonic,
    ) -> None:
        self._classifier = classifier
        self._model_small = model_small or settings.ai_model_small
        self._model_large = model_large or settings.ai_model_large
        self._confidence_threshold = (
            settings.ai_confidence_threshold
            if confidence_threshold is None
            else confidence_threshold
        )
        self._cache_size = (
            settings.ai_cache_size if cache_size is None else cache_size
        )
        if not 0 <= self._confidence_threshold <= 1:
            raise ValueError("AI_CONFIDENCE_THRESHOLD deve estar entre 0 e 1.")
        if self._cache_size < 1:
            raise ValueError("AI_CACHE_SIZE deve ser maior que zero.")
        self._clock = clock
        self._cache: OrderedDict[str, tuple[float, ClassificationResult]] = (
            OrderedDict()
        )
        self._lock = threading.Lock()

    def classify(self, payload: ClassificationInput) -> ClassificationResult:
        cache_key = self._cache_key(payload)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            result = self._classifier.classify(
                payload,
                model=self._model_small,
            )
            if result.confidence < self._confidence_threshold:
                result = self._classifier.classify(
                    payload,
                    model=self._model_large,
                ).model_copy(update={"escalated": True})
        except ClassifierUnavailable:
            result = self._fallback(payload)

        self._set_cached(cache_key, result)
        return result

    @staticmethod
    def _cache_key(payload: ClassificationInput) -> str:
        normalized_text = re.sub(r"\s+", " ", (payload.text or "").casefold()).strip()
        material = f"{normalized_text}\0{payload.user_category or ''}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _get_cached(self, key: str) -> ClassificationResult | None:
        with self._lock:
            cached = self._cache.get(key)
            if cached is None:
                return None
            expires_at, result = cached
            if expires_at <= self._clock():
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return result

    def _set_cached(self, key: str, result: ClassificationResult) -> None:
        with self._lock:
            self._cache[key] = (self._clock() + CACHE_TTL_SECONDS, result)
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

    @staticmethod
    def _fallback(payload: ClassificationInput) -> ClassificationResult:
        category = payload.user_category or ReportCategory.TO_CLASSIFY
        return ClassificationResult(
            category=category,
            subcategory=(
                "a_classificar"
                if category == ReportCategory.TO_CLASSIFY
                else None
            ),
            urgency=None,
            confidence=0,
            immediate_risk=None,
            model="none",
            source="user" if payload.user_category else "none",
        )
