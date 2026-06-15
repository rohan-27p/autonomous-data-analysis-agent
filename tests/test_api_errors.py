from __future__ import annotations

from fastapi.testclient import TestClient

from autodata_agent.api.app import create_app
from autodata_agent.core.config import Settings
from autodata_agent.core.errors import AppError
from autodata_agent.services.llm import OllamaCloudClient


def test_health_endpoint_returns_configured_model():
    client = TestClient(create_app())
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["model"] == "kimi-k2.7-code:cloud"


def test_ollama_client_fails_gracefully_without_key(tmp_path):
    settings = Settings(
        storage_dir=tmp_path / "runtime",
        upload_dir=tmp_path / "uploads",
        ollama_api_key=None,
    )
    client = OllamaCloudClient(settings)

    try:
        client.chat_json(system="Return JSON.", user="{}")
    except AppError as exc:
        assert exc.code == "ollama_api_key_missing"
    else:
        raise AssertionError("Expected Ollama client to fail without API key.")
