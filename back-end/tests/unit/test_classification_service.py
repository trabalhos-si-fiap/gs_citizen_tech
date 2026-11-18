import json
from io import BytesIO
import unittest
from unittest.mock import patch

from app.infrastructure.classifiers import (
    ClassifierUnavailable,
    FakeClassifier,
    OllamaClassifier,
)
from app.models.classification import ClassificationInput, ClassificationResult
from app.models.taxonomy import ReportCategory
from app.services.classification_service import ClassificationService


class SequenceClassifier:
    def __init__(self, results: list[ClassificationResult | Exception]) -> None:
        self.results = results
        self.calls: list[str] = []

    def classify(
        self,
        payload: ClassificationInput,
        *,
        model: str,
    ) -> ClassificationResult:
        self.calls.append(model)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result.model_copy(update={"model": model})


def classification(
    confidence: float,
    *,
    category: ReportCategory = ReportCategory.URBAN_RISK,
    subcategory: str | None = "buraco_via",
) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        subcategory=subcategory,
        urgency="media",
        confidence=confidence,
        immediate_risk=False,
        model="fixture",
        source="ai",
    )


class ClassificationServiceTests(unittest.TestCase):
    def test_low_confidence_escalates_and_marks_larger_model(self) -> None:
        classifier = SequenceClassifier(
            [classification(0.4), classification(0.8)]
        )
        service = ClassificationService(
            classifier,
            model_small="small",
            model_large="large",
            confidence_threshold=0.7,
        )

        result = service.classify(
            ClassificationInput(text="Buraco na rua", user_category=None)
        )

        self.assertEqual(classifier.calls, ["small", "large"])
        self.assertEqual(result.model, "large")
        self.assertTrue(result.escalated)

    def test_model_failure_falls_back_without_inventing_risk(self) -> None:
        classifier = SequenceClassifier(
            [ClassifierUnavailable("offline")]
        )
        service = ClassificationService(classifier)

        result = service.classify(
            ClassificationInput(
                text="Problema urbano",
                user_category=ReportCategory.HEALTHCARE,
            )
        )

        self.assertEqual(result.category, ReportCategory.HEALTHCARE)
        self.assertEqual(result.source, "user")
        self.assertEqual(result.confidence, 0)
        self.assertIsNone(result.urgency)
        self.assertIsNone(result.immediate_risk)
        self.assertEqual(result.model, "none")

    def test_classification_cache_avoids_repeated_model_calls(self) -> None:
        classifier = FakeClassifier()
        service = ClassificationService(classifier)
        payload = ClassificationInput(text="Buraco na via", user_category=None)

        first = service.classify(payload)
        second = service.classify(
            ClassificationInput(text="  BURACO   na via ", user_category=None)
        )

        self.assertEqual(first, second)

    def test_ollama_adapter_validates_structured_output(self) -> None:
        response_body = json.dumps(
            {
                "message": {
                    "content": json.dumps(
                        {
                            "category": "risco_urbano",
                            "subcategory": "buraco_via",
                            "urgency": "media",
                            "confidence": 0.88,
                            "immediate_risk": False,
                        }
                    )
                }
            }
        ).encode("utf-8")
        captured_requests = []

        class FakeOpener:
            def open(self, request, *, timeout):
                captured_requests.append((request, timeout))
                return BytesIO(response_body)

        with patch(
            "app.infrastructure.classifiers.build_opener",
            return_value=FakeOpener(),
        ):
            classifier = OllamaClassifier("http://127.0.0.1:11434")
            result = classifier.classify(
                ClassificationInput(
                    text="Buraco na rua",
                    user_category=None,
                ),
                model="small",
            )

        request, timeout = captured_requests[0]
        request_body = json.loads(request.data)
        self.assertEqual(result.category, ReportCategory.URBAN_RISK)
        self.assertEqual(result.model, "small")
        self.assertEqual(timeout, 8)
        self.assertEqual(len(request_body["messages"]), 2)
        self.assertNotIn("correlation_id", request_body["messages"][1]["content"])

    def test_ollama_adapter_rejects_unknown_subcategory(self) -> None:
        response_body = json.dumps(
            {
                "message": {
                    "content": json.dumps(
                        {
                            "category": "risco_urbano",
                            "subcategory": "falta_medico",
                            "urgency": "media",
                            "confidence": 0.88,
                            "immediate_risk": False,
                        }
                    )
                }
            }
        ).encode("utf-8")

        class FakeOpener:
            def open(self, request, *, timeout):
                return BytesIO(response_body)

        with patch(
            "app.infrastructure.classifiers.build_opener",
            return_value=FakeOpener(),
        ):
            classifier = OllamaClassifier("http://127.0.0.1:11434")
            with self.assertRaises(ClassifierUnavailable):
                classifier.classify(
                    ClassificationInput(
                        text="Relato",
                        user_category=None,
                    ),
                    model="small",
                )
