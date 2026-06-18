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


def test_preview_endpoint_returns_rows_with_limit(api_client: TestClient):
    upload_response = api_client.post(
        "/api/v1/datasets/upload",
        files={"file": ("orders.csv", b"category,sales\nA,100\nB,50\nC,75\n", "text/csv")},
    )
    dataset_id = upload_response.json()["dataset_id"]

    response = api_client.get(f"/api/v1/datasets/{dataset_id}/preview?limit=2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"] == dataset_id
    assert payload["columns"] == ["category", "sales"]
    assert len(payload["rows"]) == 2
    assert payload["rows"][0]["category"] == "A"
    assert payload["rows"][1]["sales"] == 50


def test_render_chart_endpoint_returns_plotly_figure(api_client: TestClient):
    response = api_client.post(
        "/api/v1/charts/render",
        json={
            "chart_spec": {
                "chart_type": "bar",
                "title": "Sales by Category",
                "x": "category",
                "y": "sales",
                "caption": "Category A leads sales.",
            },
            "result_rows": [
                {"category": "A", "sales": 150},
                {"category": "B", "sales": 75},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["caption"] == "Category A leads sales."
    assert payload["figure"]["layout"]["title"]["text"] == "Sales by Category"
    assert payload["figure"]["data"][0]["type"] == "bar"


def test_render_chart_endpoint_returns_structured_validation_error(api_client: TestClient):
    response = api_client.post(
        "/api/v1/charts/render",
        json={
            "chart_spec": {
                "chart_type": "bar",
                "title": "Sales by Category",
                "x": "category",
                "y": "sales",
                "caption": "No rows.",
            },
            "result_rows": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_chart_data"

