import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import SecretStr

from app.models.auth import ConsentRequest
from app.infrastructure.repositories import ConsentRequired, InMemoryAuthRepository
from app.services.auth_service import (
    AuthService,
    GoogleVerificationUnavailable,
    InvalidGoogleToken,
    InvalidOtp,
)
from app.infrastructure.tokens import decode_access_token


class FakeOtpMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_otp(self, email: str, code: str) -> None:
        self.sent.append((email, code))


class AuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryAuthRepository()
        self.mailer = FakeOtpMailer()
        self.service = AuthService(self.repository, self.mailer)
        self.secret = "a-test-secret-long-enough-for-hs256"
        self.settings_patch = patch(
            "app.services.auth_service.settings",
            SimpleNamespace(
                jwt_secret=SecretStr(self.secret),
                google_client_id="test-google-client.apps.googleusercontent.com",
            ),
        )
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    def test_new_account_requires_consent_before_sending_otp(self) -> None:
        with self.assertRaises(ConsentRequired):
            self.service.request_otp("person@example.com", None)

        self.assertEqual(self.mailer.sent, [])

    def test_otp_login_and_refresh_rotation(self) -> None:
        self.service.request_otp(
            "person@example.com",
            ConsentRequest(version="2026-01", accepted_age=True),
        )
        email, code = self.mailer.sent[-1]

        tokens = self.service.verify_otp(email, code)
        claims = decode_access_token(tokens.access_token, self.secret)
        self.assertIsNotNone(claims)
        self.assertEqual(claims["role"], "citizen")
        self.assertEqual(tokens.user.email, email)
        self.assertEqual(tokens.user.consent_version, "2026-01")

        rotated = self.service.refresh(tokens.refresh_token)
        self.assertNotEqual(rotated.refresh_token, tokens.refresh_token)
        with self.assertRaises(InvalidOtp):
            self.service.refresh(tokens.refresh_token)

    def test_invalid_otp_attempt_limit_and_single_use(self) -> None:
        self.service.request_otp(
            "person@example.com",
            ConsentRequest(version="2026-01", accepted_age=True),
        )
        email, code = self.mailer.sent[-1]

        for _ in range(5):
            with self.assertRaises(InvalidOtp):
                wrong_code = "000000" if code != "000000" else "000001"
                self.service.verify_otp(email, wrong_code)
        with self.assertRaises(InvalidOtp):
            self.service.verify_otp(email, code)

        self.service.request_otp(
            email,
            ConsentRequest(version="2026-01", accepted_age=True),
        )
        email, code = self.mailer.sent[-1]
        self.service.verify_otp(email, code)
        with self.assertRaises(InvalidOtp):
            self.service.verify_otp(email, code)

    def test_google_login_requires_verified_email_and_persists_identity(self) -> None:
        claims = {
            "sub": "google-user-123",
            "email": "Person@Example.com",
            "email_verified": True,
        }
        with patch.object(
            self.service,
            "_verify_google_token",
            return_value=claims,
        ):
            with self.assertRaises(ConsentRequired):
                self.service.login_google("valid-id-token", None)

            tokens = self.service.login_google(
                "valid-id-token",
                ConsentRequest(version="2026-01", accepted_age=True),
            )
            again = self.service.login_google("valid-id-token", None)

        self.assertEqual(tokens.user.id, again.user.id)
        self.assertEqual(tokens.user.email, "person@example.com")
        self.assertNotEqual(tokens.refresh_token, again.refresh_token)

    def test_google_login_rejects_unverified_email(self) -> None:
        with patch.object(
            self.service,
            "_verify_google_token",
            return_value={
                "sub": "google-user-123",
                "email": "person@example.com",
                "email_verified": False,
            },
        ):
            with self.assertRaises(InvalidGoogleToken):
                self.service.login_google(
                    "valid-id-token",
                    ConsentRequest(version="2026-01", accepted_age=True),
                )

    def test_google_token_verifier_checks_audience_and_translates_failures(self) -> None:
        with patch(
            "google.oauth2.id_token.verify_oauth2_token",
            return_value={"sub": "google-user-123"},
        ) as verify:
            claims = self.service._verify_google_token(
                "signed-id-token",
                "expected-client-id",
            )

        self.assertEqual(claims["sub"], "google-user-123")
        self.assertEqual(verify.call_args.kwargs["audience"], "expected-client-id")

        with patch(
            "google.oauth2.id_token.verify_oauth2_token",
            side_effect=ValueError("invalid token"),
        ):
            with self.assertRaises(InvalidGoogleToken):
                self.service._verify_google_token(
                    "invalid-token",
                    "expected-client-id",
                )

        from google.auth.exceptions import TransportError

        with patch(
            "google.oauth2.id_token.verify_oauth2_token",
            side_effect=TransportError("key server unavailable"),
        ):
            with self.assertRaises(GoogleVerificationUnavailable):
                self.service._verify_google_token(
                    "signed-id-token",
                    "expected-client-id",
                )


if __name__ == "__main__":
    unittest.main()
