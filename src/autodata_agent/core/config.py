from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://localhost:8501",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8501",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTODATA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "development"
    storage_dir: Path = Path("data/runtime")
    upload_dir: Path = Path("data/uploads")

    ollama_base_url: str = "https://ollama.com"
    ollama_api_key: SecretStr | None = None
    ollama_model: str = "qwen3-coder:480b"
    ollama_think: str = "false"
    ollama_num_predict: int = 2048

    llm_timeout_seconds: float = 90
    execution_timeout_seconds: float = 12
    max_repair_attempts: int = Field(default=2, ge=0, le=5)
    max_upload_bytes: int = 50 * 1024 * 1024
    max_preview_rows: int = 50
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS)
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value  # type: ignore[return-value]

    def ensure_dirs(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
