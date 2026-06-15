from __future__ import annotations

from functools import lru_cache

from autodata_agent.core.config import Settings, get_settings
from autodata_agent.services.analysis import AnalysisService
from autodata_agent.services.datasets import DatasetStore
from autodata_agent.services.executor import CodeExecutor
from autodata_agent.services.llm import OllamaCloudClient
from autodata_agent.storage.session_store import SessionStore


@lru_cache
def get_dataset_store() -> DatasetStore:
    settings = get_settings()
    return DatasetStore(settings.upload_dir, settings.max_upload_bytes)


@lru_cache
def get_session_store() -> SessionStore:
    settings = get_settings()
    return SessionStore(settings.storage_dir / "sessions.sqlite3")


def get_analysis_service() -> AnalysisService:
    settings = get_settings()
    return AnalysisService(
        datasets=get_dataset_store(),
        sessions=get_session_store(),
        llm=OllamaCloudClient(settings),
        executor=CodeExecutor(settings.execution_timeout_seconds),
        max_repair_attempts=settings.max_repair_attempts,
    )


def settings_dependency() -> Settings:
    return get_settings()

