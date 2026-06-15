from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from autodata_agent.api import dependencies
from autodata_agent.api.app import create_app
from autodata_agent.services.datasets import DatasetStore
from autodata_agent.storage.session_store import SessionStore


@pytest.fixture
def api_client(tmp_path) -> Iterator[TestClient]:
    app = create_app()
    dataset_store = DatasetStore(
        tmp_path / "uploads",
        max_upload_bytes=5_000_000,
        dataset_dir=tmp_path / "datasets",
    )
    session_store = SessionStore(tmp_path / "sessions.sqlite3")
    app.dependency_overrides[dependencies.get_dataset_store] = lambda: dataset_store
    app.dependency_overrides[dependencies.get_session_store] = lambda: session_store
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_upload_dataset_endpoint_returns_profile(api_client: TestClient):
    response = api_client.post(
        "/api/v1/datasets/upload",
        files={"file": ("orders.csv", b"category,sales\nA,100\nB,50\n", "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["row_count"] == 2
    assert payload["profile"]["columns"][0]["name"] == "category"


def test_upload_dataset_endpoint_rejects_unsupported_files(api_client: TestClient):
    response = api_client.post(
        "/api/v1/datasets/upload",
        files={"file": ("orders.txt", b"category,sales\nA,100\n", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_profile_endpoint_returns_structured_missing_dataset_error(api_client: TestClient):
    response = api_client.get("/api/v1/datasets/not-real/profile")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "dataset_not_found"


def test_sql_endpoint_rejects_non_select_queries(api_client: TestClient):
    response = api_client.post(
        "/api/v1/datasets/sql",
        json={
            "connection_uri": "sqlite:///example.sqlite3",
            "query": "DROP TABLE orders",
            "source_name": "bad_sql",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsafe_sql_query"


def test_analysis_endpoint_returns_structured_request_validation_error(
    api_client: TestClient,
):
    response = api_client.post("/api/v1/analysis", json={"question": "Missing dataset id"})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "request_validation_failed"
    assert any("dataset_id" in str(item["loc"]) for item in payload["error"]["details"])

