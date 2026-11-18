import os
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "reclame-ja-api"
    environment: str = "development"
    debug: bool = False
    db_user: str = ""
    db_password: SecretStr = SecretStr("")
    db_dsn: str = ""
    db_pool_min: int = 1
    db_pool_max: int = 5
    report_repository: Literal["memory", "oracle"] = "memory"
    photo_max_bytes: int = Field(default=1_000_000, gt=0, le=5_000_000)
    photo_upload_secret: SecretStr = SecretStr("")
    photo_storage_dir: Path = Path("./var/photos")
    public_api_base_url: str = "http://localhost:8000"
    jwt_secret: SecretStr = SecretStr("")
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_sender: str = "no-reply@reclameja.local"
    smtp_use_tls: bool = False
    smtp_timeout_seconds: int = 10
    push_provider: Literal["log", "fcm"] = "log"
    fcm_project_id: str = ""
    fcm_service_account_file: Path | None = None
    push_timeout_seconds: int = Field(default=10, gt=0)
    google_client_id: str = ""
    classifier: Literal["null", "fake", "ollama"] = "null"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ai_model_small: str = "qwen2.5:3b"
    ai_model_large: str = "qwen2.5:7b"
    ai_confidence_threshold: float = Field(default=0.7, ge=0, le=1)
    ai_timeout_seconds: float = Field(default=8.0, gt=0)
    ai_cache_size: int = Field(default=512, gt=0)
    report_job_poll_seconds: float = Field(default=1.0, gt=0)
    report_job_lease_seconds: int = Field(default=90, gt=0)
    report_job_max_attempts: int = Field(default=6, gt=0)
    # D10: sem confirmação do cidadão nesse prazo, a sugestão é aplicada.
    triage_auto_confirm_minutes: int = Field(default=10, gt=0)
    triage_sweep_interval_seconds: float = Field(default=60, gt=0)
    # true: a API também executa jobs (modo memória/dev sem worker).
    # false: a API só enfileira; o container worker processa a fila.
    inline_job_processing: bool = True
    agency_api_keys: str = ""
    visual_verification_enabled: bool = False
    visual_verification_provider: str = ""
    cors_allow_origins: str = (
        "http://localhost:4200,http://127.0.0.1:4200,http://localhost:8000"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
        # Docker secrets: cada arquivo em SECRETS_DIR (ex.: /run/secrets/jwt_secret)
        # preenche o campo de mesmo nome. Variáveis de ambiente têm precedência.
        secrets_dir=os.environ.get("SECRETS_DIR") or None,
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
