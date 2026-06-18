from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
sys.path.insert(0, str(FRONTEND_DIR))

from api_client import ApiError, AutodataApiClient  # noqa: E402


def test_health_returns_backend_payload(monkeypatch):
    captured: dict[str, str] = {}

    def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        return httpx.Response(
            200,
            json={"status": "ok", "environment": "test", "model": "demo-model"},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx, "request", fake_request)

    payload = AutodataApiClient("http://127.0.0.1:8000").health()

    assert captured["method"] == "GET"
    assert captured["url"] == "http://127.0.0.1:8000/api/v1/health"
    assert payload["model"] == "demo-model"


def test_api_error_is_raised_for_structured_backend_failure(monkeypatch):
    def fake_request(method, url, **kwargs):
        return httpx.Response(
            400,
            json={"error": {"code": "empty_upload", "message": "Uploaded file is empty."}},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx, "request", fake_request)

    with pytest.raises(ApiError) as exc:
        AutodataApiClient("http://127.0.0.1:8000").upload_dataset("orders.csv", b"")

    assert exc.value.code == "empty_upload"
    assert exc.value.status_code == 400
