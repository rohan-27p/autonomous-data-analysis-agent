from __future__ import annotations

import pandas as pd
import pytest

from autodata_agent.core.errors import ExecutionAppError
from autodata_agent.services.executor import CodeExecutor


def test_executor_runs_valid_analysis_code():
    df = pd.DataFrame(
        [
            {"category": "A", "sales": 100},
            {"category": "A", "sales": 50},
            {"category": "B", "sales": 25},
        ]
    )
    code = """
result_df = df.groupby("category", as_index=False)["sales"].sum()
result_df = result_df.sort_values("sales", ascending=False)
chart_spec = {
    "chart_type": "bar",
    "title": "Sales by Category",
    "x": "category",
    "y": "sales",
    "caption": "Category A has the highest sales."
}
"""

    result = CodeExecutor(timeout_seconds=5).execute(df, code)

    assert result.success is True
    assert result.result_rows[0]["category"] == "A"
    assert result.chart_spec is not None
    assert result.chart_spec.chart_type == "bar"


def test_executor_blocks_unsafe_code():
    df = pd.DataFrame([{"x": 1}])
    with pytest.raises(ExecutionAppError) as exc:
        CodeExecutor(timeout_seconds=5).execute(df, "result_df = df\nopen('x.txt', 'w')")

    assert exc.value.code == "unsafe_generated_code"


def test_executor_normalizes_empty_chart_axes():
    df = pd.DataFrame([{"category": "A", "sales": 100}])
    code = """
result_df = df.head(1)
chart_spec = {
    "chart_type": "table",
    "title": "Preview",
    "x": [],
    "y": [],
    "caption": "Dataset preview."
}
"""

    result = CodeExecutor(timeout_seconds=5).execute(df, code)

    assert result.success is True
    assert result.chart_spec is not None
    assert result.chart_spec.x is None
    assert result.chart_spec.y is None


def test_executor_drops_fully_empty_result_rows():
    df = pd.DataFrame(
        [
            {"session": 1, "title": "System Design 101"},
            {"session": None, "title": ""},
            {"session": 2, "title": "Caching"},
        ]
    )
    code = """
result_df = df
chart_spec = {
    "chart_type": "table",
    "title": "Sessions",
    "x": "session",
    "y": "title",
    "caption": "Sessions."
}
"""

    result = CodeExecutor(timeout_seconds=5).execute(df, code)

    assert result.success is True
    assert result.result_rows == [
        {"session": 1.0, "title": "System Design 101"},
        {"session": 2.0, "title": "Caching"},
    ]
