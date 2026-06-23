from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from autodata_agent.api.app import create_app
from autodata_agent.core.config import Settings
from autodata_agent.core.errors import AppError, ExternalServiceError
from autodata_agent.services.llm import OllamaCloudClient


def test_health_endpoint_returns_configured_model():
    client = TestClient(create_app())
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["model"] == "qwen3-coder:480b"


def test_cors_allows_configured_frontend_origin():
    client = TestClient(create_app())
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unlisted_origin():
    client = TestClient(create_app())
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://evil.example"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


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


def test_ollama_client_uses_native_cloud_chat_endpoint(monkeypatch, tmp_path):
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return httpx.Response(
            200,
            json={"message": {"content": '{"ok": true}'}, "done": True},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    settings = Settings(
        storage_dir=tmp_path / "runtime",
        upload_dir=tmp_path / "uploads",
        ollama_api_key="test-key",
    )

    content = OllamaCloudClient(settings).chat_json(system="Return JSON.", user="{}")

    assert content == '{"ok": true}'
    assert captured["url"] == "https://ollama.com/api/chat"
    assert captured["json"]["model"] == "qwen3-coder:480b"
    assert captured["json"]["format"] == "json"
    assert captured["json"]["options"]["num_predict"] == 2048
    assert captured["json"]["stream"] is False
    assert "think" not in captured["json"]
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_ollama_client_reports_http_status_details(monkeypatch, tmp_path):
    def fake_post(url, *, json, headers, timeout):
        return httpx.Response(
            404,
            text='{"error":"model not found"}',
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    settings = Settings(
        storage_dir=tmp_path / "runtime",
        upload_dir=tmp_path / "uploads",
        ollama_api_key="test-key",
    )

    with pytest.raises(ExternalServiceError) as exc:
        OllamaCloudClient(settings).chat_json(system="Return JSON.", user="{}")

    assert exc.value.code == "ollama_request_failed"
    assert exc.value.message == "model not found"
    assert exc.value.details["status_code"] == 404
    assert exc.value.details["url"] == "https://ollama.com/api/chat"
    assert "model not found" in exc.value.details["response_body"]
