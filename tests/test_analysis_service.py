from __future__ import annotations

import json

from autodata_agent.core.schemas import AnalysisRequest, ResponseKind
from autodata_agent.services.analysis import AnalysisService
from autodata_agent.services.datasets import DatasetStore
from autodata_agent.services.executor import CodeExecutor
from autodata_agent.storage.session_store import SessionStore


class FakeRepairingLLM:
    def __init__(self) -> None:
        self.calls = 0

    def chat_json(self, *, system: str, user: str) -> str:
        if "routing brain" in system:
            return json.dumps({"route": "analysis", "reason": "Needs computation.", "limit": None})
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
        if "routing brain" in system:
            return json.dumps({"route": "analysis", "reason": "Needs computation.", "limit": None})
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


class FakeAlwaysMalformedGenerationLLM:
    """Routes to analysis, returns malformed JSON for code, valid JSON for narrative."""

    def chat_json(self, *, system: str, user: str) -> str:
        if "routing brain" in system:
            return json.dumps({"route": "analysis", "reason": "Needs computation.", "limit": None})
        if "business findings" in system:
            return json.dumps(
                {
                    "key_finding": "Here is a summary of the dataset.",
                    "business_meaning": "Use the rows to interpret the data.",
                    "limitations": ["Overview only."],
                    "follow_up_questions": ["Which category has the most sales?"],
                }
            )
        return "{ this is not valid json at all"


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


class FakeCodeLinesLLM:
    def chat_json(self, *, system: str, user: str) -> str:
        if "business findings" in system:
            return json.dumps(
                {
                    "key_finding": "Category A generated the most sales.",
                    "business_meaning": "Category A is the leading category in this sample.",
                    "limitations": ["Small test dataset."],
                    "follow_up_questions": ["Which region drives Category A sales?"],
                }
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
                "code_lines": [
                    'result_df = df.groupby("category", as_index=False)["sales"].sum()',
                    'result_df = result_df.sort_values("sales", ascending=False)',
                    'chart_spec = {"chart_type": "bar", "title": "Sales",',
                    '"x": "category", "y": "sales", "caption": "Sales by category."}',
                ],
            }
        )


class FakeMalformedNarrativeThenValidLLM:
    def __init__(self) -> None:
        self.narrative_calls = 0

    def chat_json(self, *, system: str, user: str) -> str:
        if "business findings" in system:
            self.narrative_calls += 1
            if self.narrative_calls == 1:
                return '{"key_finding": "Category A generated the most sales",'
            return json.dumps(
                {
                    "key_finding": "Category A generated the most sales.",
                    "business_meaning": "Category A is the leading category in this sample.",
                    "limitations": ["Small test dataset."],
                    "follow_up_questions": ["Which region drives Category A sales?"],
                }
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
                "code": "\n".join(
                    [
                        'result_df = df.groupby("category", as_index=False)["sales"].sum()',
                        'chart_spec = {"chart_type": "bar", "title": "Sales",',
                        '"x": "category", "y": "sales", "caption": "Sales by category."}',
                    ]
                ),
            }
        )


class FakeClarifyingFollowupsLLM:
    def chat_json(self, *, system: str, user: str) -> str:
        if "business findings" in system:
            return json.dumps(
                {
                    "key_finding": "Category A generated the most sales.",
                    "business_meaning": "Category A is the leading category in this sample.",
                    "limitations": ["Small test dataset."],
                    "follow_up_questions": [
                        "Can you provide context about important columns?",
                        "Show sales by category.",
                        "Would you like a cleaned dataset?",
                    ],
                }
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
                "code": "\n".join(
                    [
                        'result_df = df.groupby("category", as_index=False)["sales"].sum()',
                        'chart_spec = {"chart_type": "bar", "title": "Sales",',
                        '"x": "category", "y": "sales", "caption": "Sales by category."}',
                    ]
                ),
            }
        )


class FakeRouterLLM:
    def __init__(self, route: str, limit: int | None = None) -> None:
        self.route = route
        self.limit = limit
        self.calls: list[str] = []

    def chat_json(self, *, system: str, user: str) -> str:
        self.calls.append(system)
        if "routing brain" in system:
            return json.dumps(
                {
                    "route": self.route,
                    "reason": f"User intent is {self.route}.",
                    "limit": self.limit,
                }
            )
        raise AssertionError("Only routing should be needed for this request")


class FailingLLM:
    def chat_json(self, *, system: str, user: str) -> str:
        raise AssertionError("LLM should not be called for deterministic list query")


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


def test_analysis_service_falls_back_to_overview_when_execution_fails(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file("orders.csv", b"category,sales\nA,100\nB,10\n")
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FakeAlwaysMissingColumnLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=1,
    )

    # The model only ever produces code that references a missing column. Instead of
    # raising, the service must degrade to a guaranteed data overview.
    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="Rank categories by revenue")
    )

    assert response.execution.success is True
    assert response.plan.operation == "overview"
    assert response.generated_code.startswith("result_df = df.head(50)")
    assert response.execution.result_rows[0]["category"] == "A"


def test_analysis_service_falls_back_when_generation_json_malformed(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file("orders.csv", b"category,sales\nA,100\nB,10\n")
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FakeAlwaysMalformedGenerationLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    # Reproduces the viva failure: the model returns malformed JSON for the analysis
    # code. The user must still get a valid answer, never an error.
    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="Which category has the most revenue?")
    )

    assert response.execution.success is True
    assert response.generated_code.startswith("result_df = df.head(50)")
    # Generation fell back, but the narrative step still succeeded normally.
    assert response.narrative.key_finding == "Here is a summary of the dataset."


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
        AnalysisRequest(dataset_id=info.dataset_id, question="Create a compact table of the data")
    )

    assert response.plan.operation == "overview"
    assert response.execution.success is True
    assert response.execution.chart_spec is not None
    assert response.execution.chart_spec.chart_type == "table"
    assert response.execution.result_rows[0]["category"] == "A"
    assert response.narrative.limitations == ["Only a preview was requested."]
    assert response.narrative.follow_up_questions == ["Which category has the highest sales?"]


def test_analysis_service_uses_llm_router_for_profile_questions(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file("orders.csv", b"order_id,category,sales\n1,A,100\n2,B,10\n")
    llm = FakeRouterLLM("profile")
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=llm,
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="what is this csv about and list columns")
    )

    assert any("routing brain" in system for system in llm.calls)
    assert response.response_kind == ResponseKind.ANSWER
    assert response.generated_code == ""
    assert [row["Column"] for row in response.execution.result_rows] == [
        "order_id",
        "category",
        "sales",
    ]
    assert response.plan.assumptions == ["LLM router selected this path: User intent is profile."]


def test_analysis_service_uses_llm_router_for_preview_questions(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file(
        "orders.csv",
        b"order_id,category,sales\n1,A,100\n2,B,10\n3,C,40\n",
    )
    llm = FakeRouterLLM("preview", limit=2)
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=llm,
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="show some rows to me, I want to check data in it")
    )

    assert any("routing brain" in system for system in llm.calls)
    assert response.response_kind == ResponseKind.ANSWER
    assert response.generated_code == ""
    assert len(response.execution.result_rows) == 2
    assert response.execution.result_columns == ["order_id", "category", "sales"]
    assert response.execution.result_rows[0]["order_id"] == 1


def test_analysis_service_answers_dataset_profile_questions_without_llm(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file(
        "orders.csv",
        b"order_id,category,sales\n1,A,100\n2,B,10\n",
    )
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FailingLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="what is this csv about, and list all columns")
    )

    assert response.response_kind == ResponseKind.ANSWER
    assert response.generated_code == ""
    assert response.execution.result_columns == [
        "Column",
        "Type",
        "Non-null",
        "Null %",
        "Unique",
        "Examples",
    ]
    assert [row["Column"] for row in response.execution.result_rows] == [
        "order_id",
        "category",
        "sales",
    ]
    assert "2 rows and 3 columns" in response.narrative.key_finding


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


def test_analysis_service_accepts_generated_code_lines(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file("orders.csv", b"category,sales\nA,100\nB,10\n")
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FakeCodeLinesLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="Rank categories by sales")
    )

    assert response.execution.success is True
    assert response.generated_code.startswith("result_df")
    assert response.execution.result_rows[0]["category"] == "A"


def test_analysis_service_retries_malformed_narrative_json(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file("orders.csv", b"category,sales\nA,100\nB,10\n")
    llm = FakeMalformedNarrativeThenValidLLM()
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

    assert llm.narrative_calls == 2
    assert response.execution.success is True
    assert response.narrative.key_finding.startswith("Category A")


def test_analysis_service_filters_clarifying_followups(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file("orders.csv", b"category,sales\nA,100\nB,10\n")
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FakeClarifyingFollowupsLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="Rank categories by sales")
    )

    assert response.narrative.follow_up_questions == ["Show sales by category."]


def test_analysis_service_handles_greeting_without_analysis_shell(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file("orders.csv", b"category,sales\nA,100\nB,10\n")
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FailingLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="hi")
    )

    assert response.execution.success is True
    assert response.response_kind == ResponseKind.CONVERSATION
    assert response.execution.result_rows == []
    assert response.generated_code == ""


def test_analysis_service_marks_table_lookup_as_answer(tmp_path):
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
        AnalysisRequest(dataset_id=info.dataset_id, question="list the rows")
    )

    assert response.response_kind == ResponseKind.ANSWER


class FakeLookupLLM:
    """Routes a lookup question to LLM-generated pandas that filters the file."""

    def chat_json(self, *, system: str, user: str) -> str:
        if "routing brain" in system:
            return json.dumps({"route": "lookup", "reason": "List matching rows.", "limit": None})
        if "business findings" in system:
            return json.dumps(
                {
                    "key_finding": "There are 2 orders in the West region.",
                    "business_meaning": "West contributes two of the recorded orders.",
                    "limitations": ["Based on the uploaded rows only."],
                    "follow_up_questions": ["Which region has the most orders?"],
                }
            )
        return json.dumps(
            {
                "plan": {
                    "operation": "filtering",
                    "objective": "List all orders in the West region.",
                    "required_columns": ["region"],
                    "assumptions": [],
                    "chart_type": "table",
                },
                "code": "\n".join(
                    [
                        'result_df = df[df["region"] == "West"].copy()',
                        'chart_spec = {"chart_type": "table", "title": "West orders",',
                        '"x": "order_id", "y": "region", "caption": "Orders in the West region."}',
                    ]
                ),
            }
        )


class FakeDerivedColumnLLM:
    """Declares a derived/output column in required_columns that is not in the file."""

    def chat_json(self, *, system: str, user: str) -> str:
        if "routing brain" in system:
            return json.dumps({"route": "analysis", "reason": "Needs computation.", "limit": None})
        if "business findings" in system:
            return json.dumps(
                {
                    "key_finding": "West has the highest revenue per unit.",
                    "business_meaning": "West sells higher-value units on average.",
                    "limitations": ["Small sample."],
                    "follow_up_questions": ["Which region sells the most units?"],
                }
            )
        return json.dumps(
            {
                "plan": {
                    "operation": "aggregation",
                    "objective": "Average revenue per unit by region.",
                    # 'avg_revenue_per_unit' is a derived output column, not in the file.
                    "required_columns": ["region", "avg_revenue_per_unit"],
                    "assumptions": [],
                    "chart_type": "bar",
                },
                "code": "\n".join(
                    [
                        'g = df.groupby("region", as_index=False).agg(',
                        '    total_rev=("revenue", "sum"), total_units=("units", "sum"))',
                        'g["avg_revenue_per_unit"] = g["total_rev"] / g["total_units"]',
                        'result_df = g[["region", "avg_revenue_per_unit"]]',
                        'chart_spec = {"chart_type": "bar", "title": "Avg revenue per unit",',
                        '"x": "region", "y": "avg_revenue_per_unit",',
                        '"caption": "Avg revenue per unit."}',
                    ]
                ),
            }
        )


def test_analysis_service_routes_lookup_to_llm_generated_pandas(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file(
        "orders.csv",
        b"order_id,region\n1,West\n2,East\n3,West\n",
    )
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FakeLookupLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="list all orders in the West region")
    )

    # The model controls the lookup: it generated real pandas, not a hardcoded heuristic.
    assert response.generated_code.startswith("result_df")
    assert response.response_kind == ResponseKind.ANSWER
    assert [row["region"] for row in response.execution.result_rows] == ["West", "West"]


def test_analysis_service_accepts_derived_output_columns_in_plan(tmp_path):
    datasets = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = datasets.put_file(
        "orders.csv",
        b"region,units,revenue\nWest,10,100\nEast,5,50\nWest,2,80\n",
    )
    service = AnalysisService(
        datasets=datasets,
        sessions=SessionStore(tmp_path / "sessions.sqlite3"),
        llm=FakeDerivedColumnLLM(),
        executor=CodeExecutor(timeout_seconds=5),
        max_repair_attempts=2,
    )

    # Previously this 422'd because 'avg_revenue_per_unit' is not a source column.
    response = service.analyze(
        AnalysisRequest(dataset_id=info.dataset_id, question="average revenue per unit by region")
    )

    assert response.execution.success is True
    assert response.execution.attempts == 1
    assert "avg_revenue_per_unit" in response.execution.result_columns
