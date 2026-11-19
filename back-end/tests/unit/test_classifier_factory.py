import unittest

from app.core.config import Settings
from app.infrastructure.classifiers import (
    ClassifierUnavailable,
    FakeClassifier,
    FallbackClassifier,
    NullClassifier,
    OllamaClassifier,
    build_classifier,
)
from app.models.classification import ClassificationInput
from app.models.taxonomy import ReportCategory

PAYLOAD = ClassificationInput(text="Buraco enorme na rua", user_category=None)


def config(**values) -> Settings:
    return Settings(_env_file=None, environment="development", **values)


class BuildClassifierTests(unittest.TestCase):
    def test_ollama_service_on_compose_network_is_allowed(self) -> None:
        classifier = build_classifier(
            config(classifier="ollama", ollama_base_url="http://ollama:11434")
        )

        self.assertIsInstance(classifier, OllamaClassifier)

    def test_ollama_on_external_host_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            build_classifier(
                config(
                    classifier="ollama",
                    ollama_base_url="http://api.example.com:11434",
                )
            )

    def test_ollama_with_fake_fallback_wraps_both(self) -> None:
        classifier = build_classifier(
            config(
                classifier="ollama",
                ollama_base_url="http://ollama:11434",
                ai_fallback="fake",
            )
        )

        self.assertIsInstance(classifier, FallbackClassifier)

    def test_fake_fallback_is_development_only(self) -> None:
        with self.assertRaises(RuntimeError):
            build_classifier(
                Settings(
                    _env_file=None,
                    environment="production",
                    classifier="ollama",
                    ollama_base_url="http://ollama:11434",
                    ai_fallback="fake",
                )
            )


class FallbackClassifierTests(unittest.TestCase):
    def test_uses_secondary_when_primary_is_unavailable(self) -> None:
        classifier = FallbackClassifier(NullClassifier(), FakeClassifier())

        result = classifier.classify(PAYLOAD, model="small")

        self.assertEqual(result.category, ReportCategory.URBAN_RISK)

    def test_keeps_primary_result_when_available(self) -> None:
        class Primary:
            def classify(self, payload, *, model):
                return FakeClassifier().classify(payload, model=model).model_copy(
                    update={"model": "primary"}
                )

        result = FallbackClassifier(Primary(), NullClassifier()).classify(
            PAYLOAD, model="small"
        )

        self.assertEqual(result.model, "primary")

    def test_propagates_when_both_are_unavailable(self) -> None:
        with self.assertRaises(ClassifierUnavailable):
            FallbackClassifier(NullClassifier(), NullClassifier()).classify(
                PAYLOAD, model="small"
            )


if __name__ == "__main__":
    unittest.main()
