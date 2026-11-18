import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.core.config import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class SecretsDirTests(unittest.TestCase):
    def test_secrets_dir_env_var_loads_secrets_from_files(self) -> None:
        with tempfile.TemporaryDirectory() as secrets_dir:
            Path(secrets_dir, "jwt_secret").write_text("segredo-do-arquivo\n")
            env = {
                key: value
                for key, value in os.environ.items()
                if key != "JWT_SECRET"
            }
            env["SECRETS_DIR"] = secrets_dir

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from app.core.config import settings;"
                    "print(settings.jwt_secret.get_secret_value())",
                ],
                cwd=BACKEND_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

        self.assertEqual(result.stdout.strip(), "segredo-do-arquivo")


class CorsOriginsTests(unittest.TestCase):
    def test_default_origins_cover_local_web_panel(self) -> None:
        self.assertIn("http://localhost:4200", Settings().cors_origins)

    def test_origins_are_parsed_from_comma_separated_value(self) -> None:
        settings = Settings(
            cors_allow_origins=" https://painel.exemplo.gov.br , https://a.b ,"
        )

        self.assertEqual(
            settings.cors_origins,
            ["https://painel.exemplo.gov.br", "https://a.b"],
        )


if __name__ == "__main__":
    unittest.main()
