from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from autodata_agent.api import dependencies
from autodata_agent.api.app import create_app
from autodata_agent.core.schemas import (
    AnalysisOperation,
    AnalysisPlan,
    AnalysisResponse,
    ChartSpec,
    ChartType,
    ExecutionResult,
    Narrative,
)
from autodata_agent.services.datasets import DatasetStore
from autodata_agent.storage.session_store import SessionStore


@pytest.fixture
def session_store(tmp_path) -> SessionStore:
    return SessionStore(tmp_path / "sessions.sqlite3")


@pytest.fixture
def api_client(tmp_path, session_store) -> Iterator[TestClient]:
    app = create_app()
    dataset_store = DatasetStore(
        tmp_path / "uploads",
        max_upload_bytes=5_000_000,
        dataset_dir=tmp_path / "datasets",
    )
    app.dependency_overrides[dependencies.get_dataset_store] = lambda: dataset_store
    app.dependency_overrides[dependencies.get_session_store] = lambda: session_store
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _make_analysis_response(session_id: str, question: str) -> AnalysisResponse:
    return AnalysisResponse(
        session_id=session_id,
        dataset_id="dataset-1",
        question=question,
        plan=AnalysisPlan(
            operation=AnalysisOperation.AGGREGATION,
            objective="Aggregate sales by category.",
            required_columns=["category", "sales"],
            chart_type=ChartType.BAR,
        ),
        generated_code="result_df = df.groupby('category')['sales'].sum().reset_index()",
        execution=ExecutionResult(
            success=True,
            result_columns=["category", "sales"],
            result_rows=[{"category": "A", "sales": 150}],
            chart_spec=ChartSpec(
                chart_type=ChartType.BAR,
                title="Sales by Category",
                x="category",
                y="sales",
                caption="Category A leads sales.",
            ),
        ),
        narrative=Narrative(
            key_finding="Category A leads sales.",
            business_meaning="Focus inventory on Category A.",
            limitations=["Single period only."],
            follow_up_questions=["How do margins compare?"],
        ),
    )


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


def test_export_endpoint_returns_empty_session(api_client: TestClient):
    response = api_client.get("/api/v1/sessions/empty-session/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "empty-session"
    assert payload["analyses"] == []
    assert payload["exported_at"]


def test_export_endpoint_returns_records_in_chronological_order(
    api_client: TestClient, session_store: SessionStore
):
    session_id = "session-export"
    for question in ("First question?", "Second question?", "Third question?"):
        session_store.append(
            session_id,
            "dataset-1",
            question,
            _make_analysis_response(session_id, question),
        )

    response = api_client.get(f"/api/v1/sessions/{session_id}/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    questions = [analysis["question"] for analysis in payload["analyses"]]
    assert questions == ["First question?", "Second question?", "Third question?"]

    first = payload["analyses"][0]
    assert first["operation"] == "aggregation"
    assert first["generated_code"].startswith("result_df")
    assert first["result_rows"] == [{"category": "A", "sales": 150}]
    assert first["chart_spec"]["title"] == "Sales by Category"
    assert first["narrative"]["key_finding"] == "Category A leads sales."
