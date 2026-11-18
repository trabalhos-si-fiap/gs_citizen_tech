"""Testes estáticos da infraestrutura de containers.

Validam o `docker-compose.yml` já resolvido (`docker compose config`) e os
Dockerfiles contra as regras de segregação, otimização e segurança descritas
em `docs_tecnicas/09-containers-docker.md`.

Executar a partir da raiz do repositório:
    python -m unittest discover -s tests/infra -v
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

LONG_RUNNING = {"oracle", "api", "worker", "web", "mailpit"}
APP_SERVICES = {"api", "worker", "db-migrate", "web"}
SECRET_KEY_PATTERN = re.compile(r"(PASSWORD|SECRET|API_KEYS?)$")


def compose_config(*profiles: str) -> dict:
    command = ["docker", "compose", "--env-file", ".env.example"]
    for profile in profiles:
        command += ["--profile", profile]
    command += ["config", "--format", "json"]
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def dockerfile_stages(path: Path) -> list[list[str]]:
    stages: list[list[str]] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.upper().startswith("FROM "):
            stages.append([])
        if stages:
            stages[-1].append(stripped)
    return stages


def final_user(stage: list[str]) -> str | None:
    users = [line.split(None, 1)[1] for line in stage if line.upper().startswith("USER ")]
    return users[-1] if users else None


class ComposeTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = compose_config()
        cls.services = cls.config["services"]

    def test_one_container_per_function(self) -> None:
        self.assertEqual(
            set(self.services),
            {"oracle", "db-migrate", "api", "worker", "web", "mailpit"},
        )

    def test_ollama_is_opt_in_through_ai_profile(self) -> None:
        self.assertNotIn("ollama", self.services)
        self.assertIn("ollama", compose_config("ai")["services"])

    def test_long_running_services_have_healthchecks(self) -> None:
        for name in LONG_RUNNING:
            with self.subTest(service=name):
                self.assertIn("healthcheck", self.services[name])
                self.assertTrue(self.services[name]["healthcheck"].get("test"))

    def test_startup_order_waits_for_health_and_migrations(self) -> None:
        migrate_deps = self.services["db-migrate"]["depends_on"]
        self.assertEqual(migrate_deps["oracle"]["condition"], "service_healthy")
        for name in ("api", "worker"):
            with self.subTest(service=name):
                deps = self.services[name]["depends_on"]
                self.assertEqual(
                    deps["db-migrate"]["condition"],
                    "service_completed_successfully",
                )

    def test_api_delegates_job_processing_to_worker(self) -> None:
        self.assertEqual(
            str(self.services["api"]["environment"]["INLINE_JOB_PROCESSING"]).lower(),
            "false",
        )

    def test_db_migrate_is_one_shot(self) -> None:
        self.assertEqual(self.services["db-migrate"].get("restart", "no"), "no")

    def test_api_and_worker_share_photo_volume(self) -> None:
        def photo_targets(name: str) -> set[str]:
            return {
                volume["source"]
                for volume in self.services[name].get("volumes", [])
                if volume["type"] == "volume"
            }

        self.assertTrue(photo_targets("api") & photo_targets("worker"))


class ComposeSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.services = compose_config("ai")["services"]

    def test_app_containers_are_hardened(self) -> None:
        for name in APP_SERVICES:
            with self.subTest(service=name):
                service = self.services[name]
                self.assertTrue(service.get("read_only"), "rootfs somente leitura")
                self.assertIn("ALL", service.get("cap_drop", []))
                self.assertIn(
                    "no-new-privileges:true", service.get("security_opt", [])
                )

    def test_read_only_containers_have_writable_tmp(self) -> None:
        for name, service in self.services.items():
            if not service.get("read_only"):
                continue
            with self.subTest(service=name):
                tmpfs = service.get("tmpfs", [])
                self.assertTrue(
                    any(str(entry).startswith("/tmp") for entry in tmpfs)
                )

    def test_secrets_are_not_passed_as_environment_values(self) -> None:
        for name, service in self.services.items():
            for key in service.get("environment", {}) or {}:
                with self.subTest(service=name, variable=key):
                    self.assertIsNone(
                        SECRET_KEY_PATTERN.search(key),
                        "use Docker secrets (arquivo) em vez de variável",
                    )

    def test_published_ports_bind_to_loopback_only(self) -> None:
        for name, service in self.services.items():
            for port in service.get("ports", []):
                with self.subTest(service=name, port=port.get("published")):
                    self.assertEqual(port.get("host_ip"), "127.0.0.1")

    def test_oracle_and_ollama_are_not_published_to_host_by_default(self) -> None:
        self.assertFalse(self.services["ollama"].get("ports"))

    def test_third_party_images_are_pinned(self) -> None:
        for name, service in self.services.items():
            if "build" in service:
                continue
            with self.subTest(service=name):
                image = service["image"]
                self.assertRegex(image, r":[\w.\-]+$")
                self.assertFalse(image.endswith(":latest"))

    def test_services_have_memory_limits(self) -> None:
        for name, service in self.services.items():
            with self.subTest(service=name):
                limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
                self.assertTrue(limits.get("memory") or service.get("mem_limit"))


class DockerfileTests(unittest.TestCase):
    def test_backend_image_is_multi_stage_and_non_root(self) -> None:
        stages = dockerfile_stages(ROOT / "back-end" / "Dockerfile")

        self.assertGreaterEqual(len(stages), 2)
        user = final_user(stages[-1])
        self.assertIsNotNone(user)
        self.assertNotIn(user.split(":")[0], {"root", "0"})

    def test_backend_runtime_stage_has_no_package_installs(self) -> None:
        runtime = "\n".join(dockerfile_stages(ROOT / "back-end" / "Dockerfile")[-1])

        self.assertNotRegex(runtime, r"pip install|apt-get install")

    def test_web_image_is_built_then_served_unprivileged(self) -> None:
        stages = dockerfile_stages(ROOT / "web" / "Dockerfile")

        self.assertGreaterEqual(len(stages), 2)
        self.assertIn("nginx-unprivileged", stages[-1][0])

    def test_dockerignore_excludes_secrets_and_local_artifacts(self) -> None:
        for context, required in (
            ("back-end", {".env", "tests", "var", "__pycache__"}),
            ("web", {"node_modules", ".angular", "dist"}),
        ):
            with self.subTest(context=context):
                path = ROOT / context / ".dockerignore"
                self.assertTrue(path.is_file())
                entries = {
                    line.strip().strip("/").removeprefix("**/")
                    for line in path.read_text().splitlines()
                }
                self.assertTrue(required <= entries, required - entries)

    def test_secret_files_are_gitignored(self) -> None:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "secrets/jwt_secret.txt"],
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
