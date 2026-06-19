from __future__ import annotations

import json

import pytest

from autodata_agent.core.errors import ExecutionAppError
from autodata_agent.core.schemas import AnalysisRequest
from autodata_agent.services.analysis import AnalysisService
from autodata_agent.services.datasets import DatasetStore
from autodata_agent.services.executor import CodeExecutor
from autodata_agent.storage.session_store import SessionStore


class FakeRepairingLLM:
    def __init__(self) -> None:
        self.calls = 0

    def chat_json(self, *, system: str, user: str) -> str:
        self.calls += 1
        if "business findings" in system:
            return json.dumps(
                {
                    "key_finding": "Category A generated the most sales.",
                    "business_meaning": "The business should inspect why A leads demand.",
                    "limitations": ["Only two rows were tested."],
                    "follow_up_questions": ["Which region drives Category A sales?"],
                }
            )
        if self.calls == 1:
            return json.dumps(
                {
                    "plan": {
                        "operation": "aggregation",
                        "objective": "Rank categories by sales.",
                        "required_columns": ["category", "revenue"],
                        "assumptions": ["Revenue means sales."],
                        "chart_type": "bar",
                    },
                    "code": "\n".join(
                        [
                            'result_df = df.groupby("category", as_index=False)["revenue"].sum()',
                            "chart_spec = {",
                            '    "chart_type": "bar",',
                            '    "title": "Revenue by Category",',
                            '    "x": "category",',
                            '    "y": "revenue",',
                            '    "caption": "Revenue by category."',
                            "}",
                        ]
                    ),
                }
            )
        return json.dumps(
            {
                "plan": {
                    "operation": "aggregation",
                    "objective": "Rank categories by sales.",
                    "required_columns": ["category", "sales"],
                    "assumptions": ["Revenue is represented by the sales column."],
                    "chart_type": "bar",
                },
                "code": "\n".join(
                    [
                        'result_df = df.groupby("category", as_index=False)["sales"].sum()',
                        'result_df = result_df.sort_values("sales", ascending=False)',
                        "chart_spec = {",
                        '    "chart_type": "bar",',
                        '    "title": "Sales by Category",',
                        '    "x": "category",',
                        '    "y": "sales",',
                        '    "caption": "Sales by category."',
                        "}",
                    ]
                ),
            }
        )


class FakeUnsafeThenRepairLLM:
    def __init__(self) -> None:
        self.calls = 0

    def chat_json(self, *, system: str, user: str) -> str:
        self.calls += 1
        if "business findings" in system:
            return json.dumps(
                {
                    "key_finding": "Category A generated the most sales.",
                    "business_meaning": "Category A is the strongest category in this sample.",
                    "limitations": ["Small test dataset."],
                    "follow_up_questions": ["How does Category A perform by region?"],
                }
            )
        if self.calls == 1:
            code = "\n".join(
                [
                    'open("should_not_be_created.txt", "w")',
                    'result_df = df.groupby("category", as_index=False)["sales"].sum()',
                    'chart_spec = {"chart_type": "bar", "title": "Sales",',
                    '"x": "category", "y": "sales", "caption": "Sales by category."}',
                ]
            )
        else:
            code = "\n".join(
                [
                    'result_df = df.groupby("category", as_index=False)["sales"].sum()',
                    "chart_spec = {",
                    '    "chart_type": "bar",',
                    '    "title": "Sales",',
                    '    "x": "category",',
                    '    "y": "sales",',
                    '    "caption": "Sales by category."',
                    "}",
                ]
            )
        return json.dumps(
            {
                "plan": {
                    "operation": "aggregation",
                    "objective": "Rank categories by sales.",
                    "required_columns": ["category", "sales"],
                    "assumptions": [],
                    "chart_type": "bar",
                },
                "code": code,
            }
        )


class FakeAlwaysMissingColumnLLM:
    def chat_json(self, *, system: str, user: str) -> str:
        return json.dumps(
            {
                "plan": {
                    "operation": "aggregation",
                    "objective": "Rank categories by revenue.",
                    "required_columns": ["category", "revenue"],
                    "assumptions": [],
                    "chart_type": "bar",
                },
                "code": "\n".join(
                    [
                        'result_df = df.groupby("category", as_index=False)["revenue"].sum()',
                        'chart_spec = {"chart_type": "bar", "title": "Revenue",',
                        '"x": "category", "y": "revenue", "caption": "Revenue."}',
                    ]
                ),
            }
        )


class FakeCompactOllamaShapeLLM:
    def chat_json(self, *, system: str, user: str) -> str:
        if "business findings" in system:
            return json.dumps(
                {
                    "key_finding": "The dataset contains business order records.",
                    "business_meaning": "It can be used for revenue and profit analysis.",
                    "limitations": "Only a preview was requested.",
                    "follow_up_questions": "Which category has the highest sales?",
                }
            )
        return json.dumps(
            {
                "result_df": "df.head(10)",
                "chart_spec": {
                    "chart_type": "table",
                    "title": "Dataset Overview",
                    "x": "category",
                    "y": "sales",
                    "caption": "Preview of the uploaded dataset.",
                },
            }
        )


class FakeMalformedThenValidLLM:
    def __init__(self) -> None:
        self.calls = 0

    def chat_json(self, *, system: str, user: str) -> str:
        self.calls += 1
        if "business findings" in system:
            return json.dumps(
                {
                    "key_finding": "Category A generated the most sales.",
                    "business_meaning": "Category A should be inspected further.",
                    "limitations": ["Small test dataset."],
                    "follow_up_questions": ["Which region drives Category A sales?"],
                }
            )
        if self.calls == 1:
            return '{"plan": {"operation": "aggregation",'
        return json.dumps(
            {
                "plan": {
                    "operation": "aggregation",
                    "objective": "Rank categories by sales.",
                    "required_columns": ["category", "sales"],
                    "assumptions": [],
                    "chart_type": "bar",
                },
                "code": "\n".join(
                    [
                        'result_df = df.groupby("category", as_index=False)["sales"].sum()',
                        'chart_spec = {"chart_type": "bar", "title": "Sales",',
                        '"x": "category", "y": "sales", "caption": "Sales by category."}',
                    ]
                ),
            }
        )


def test_analysis_service_repairs_failed_generated_code(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file(
        "orders.csv",
        b"category,sales\nA,100\nB,10\nA,50\n",
    )
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FakeRepairingLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="Which category has the most revenue?")
    )

    assert response.execution.success is True
    assert response.execution.attempts == 2
    assert response.execution.result_rows[0]["category"] == "A"
    assert response.narrative.key_finding.startswith("Category A")


def test_analysis_service_repairs_unsafe_generated_code(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file("orders.csv", b"category,sales\nA,100\nB,10\n")
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FakeUnsafeThenRepairLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="Rank categories by sales")
    )

    assert response.execution.success is True
    assert response.execution.attempts == 2
    assert not (tmp_path / "should_not_be_created.txt").exists()


def test_analysis_service_fails_gracefully_after_plan_validation_retries(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file("orders.csv", b"category,sales\nA,100\nB,10\n")
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FakeAlwaysMissingColumnLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=1,
    )

    with pytest.raises(ExecutionAppError) as exc:
        service.analyze(
            AnalysisRequest(dataset_id=info.dataset_id, question="Rank categories by revenue")
        )

    assert exc.value.code == "analysis_execution_failed"
    assert "revenue" in exc.value.details["error"]


def test_analysis_service_normalizes_compact_ollama_shape(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file("orders.csv", b"category,sales\nA,100\nB,10\n")
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FakeCompactOllamaShapeLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="What is this CSV about?")
    )

    assert response.plan.operation == "overview"
    assert response.execution.success is True
    assert response.execution.chart_spec is not None
    assert response.execution.chart_spec.chart_type == "table"
    assert response.execution.result_rows[0]["category"] == "A"
    assert response.narrative.limitations == ["Only a preview was requested."]
    assert response.narrative.follow_up_questions == ["Which category has the highest sales?"]


def test_analysis_service_retries_malformed_generation_json(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file("orders.csv", b"category,sales\nA,100\nB,10\n")
    llm = FakeMalformedThenValidLLM()
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=llm,
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="Rank categories by sales")
    )

    assert llm.calls == 3
    assert response.execution.success is True
    assert response.execution.result_rows[0]["category"] == "A"
