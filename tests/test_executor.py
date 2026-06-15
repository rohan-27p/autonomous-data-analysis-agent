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
