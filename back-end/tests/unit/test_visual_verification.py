import unittest

from app.services.visual_verification_service import VisualVerificationService


class VisualVerificationTests(unittest.TestCase):
    def test_disabled_verification_is_fail_closed(self) -> None:
        decision = VisualVerificationService(
            enabled=False,
            provider="",
        ).verify()
        self.assertFalse(decision.approved)
        self.assertEqual(decision.status, "disabled")

    def test_enabled_without_provider_is_unavailable(self) -> None:
        decision = VisualVerificationService(
            enabled=True,
            provider="",
        ).verify()
        self.assertFalse(decision.approved)
        self.assertEqual(decision.status, "unavailable")

    def test_configured_provider_requires_manual_review(self) -> None:
        decision = VisualVerificationService(
            enabled=True,
            provider="approved-provider",
        ).verify()
        self.assertFalse(decision.approved)
        self.assertEqual(decision.status, "manual_review")


if __name__ == "__main__":
    unittest.main()
