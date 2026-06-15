from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from autodata_agent.core.errors import ExecutionAppError
from autodata_agent.core.schemas import ChartSpec, ExecutionResult

BANNED_TOKENS = (
    "import ",
    "__import__",
    "open(",
    "exec(",
    "eval(",
    "compile(",
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "urllib",
    "pathlib",
    "os.",
    "sys.",
    "shutil",
    "pickle",
    "globals(",
    "locals(",
    "__",
)


RUNNER_CODE = r"""
import contextlib
import io
import json
import math
import statistics
import traceback

import duckdb
import numpy as np
import pandas as pd

with open(INPUT_JSON, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

df = pd.DataFrame(payload["records"])
code = payload["code"]

allowed_builtins = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "pow": pow,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

scope = {
    "__builtins__": allowed_builtins,
    "df": df,
    "pd": pd,
    "np": np,
    "duckdb": duckdb,
    "math": math,
    "statistics": statistics,
}

stdout = io.StringIO()
try:
    with contextlib.redirect_stdout(stdout):
        exec(code, scope, scope)
    result_df = scope.get("result_df")
    chart_spec = scope.get("chart_spec")
    if result_df is None:
        raise ValueError("Generated code must define result_df.")
    if not isinstance(result_df, pd.DataFrame):
        result_df = pd.DataFrame(result_df)
    if chart_spec is None:
        raise ValueError("Generated code must define chart_spec.")
    if not isinstance(chart_spec, dict):
        raise ValueError("chart_spec must be a dictionary.")
    result_df = result_df.head(200)
    output = {
        "success": True,
        "result_columns": [str(column) for column in result_df.columns],
        "result_rows": json.loads(
            result_df.where(pd.notnull(result_df), None).to_json(orient="records")
        ),
        "chart_spec": chart_spec,
        "stdout": stdout.getvalue(),
    }
except Exception:
    output = {
        "success": False,
        "error": traceback.format_exc(limit=8),
        "stdout": stdout.getvalue(),
    }

with open(OUTPUT_JSON, "w", encoding="utf-8") as handle:
    json.dump(output, handle, ensure_ascii=True)
"""


class CodeExecutor:
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    def execute(self, df: pd.DataFrame, code: str) -> ExecutionResult:
        self._validate_code(code)
        records = json.loads(
            df.where(pd.notnull(df), None).to_json(orient="records", date_format="iso")
        )
        with tempfile.TemporaryDirectory(prefix="autodata_exec_") as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.json"
            output_path = tmp_path / "output.json"
            runner_path = tmp_path / "runner.py"
            input_path.write_text(json.dumps({"records": records, "code": code}), encoding="utf-8")
            runner_path.write_text(
                "INPUT_JSON = " + repr(str(input_path)) + "\n"
                "OUTPUT_JSON = " + repr(str(output_path)) + "\n"
                + RUNNER_CODE,
                encoding="utf-8",
            )
            try:
                subprocess.run(
                    [sys.executable, str(runner_path)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ExecutionAppError(
                    "analysis_timeout",
                    "Generated analysis code exceeded the execution timeout.",
                    details={"timeout_seconds": self.timeout_seconds},
                ) from exc

            if not output_path.exists():
                raise ExecutionAppError(
                    "analysis_runner_failed",
                    "Analysis runner did not return a result.",
                )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            if payload.get("success"):
                chart = ChartSpec.model_validate(payload["chart_spec"])
                return ExecutionResult(
                    success=True,
                    result_columns=payload.get("result_columns", []),
                    result_rows=payload.get("result_rows", []),
                    chart_spec=chart,
                    stdout=payload.get("stdout", ""),
                )
            return ExecutionResult(
                success=False,
                error=payload.get("error", "Unknown execution error."),
                stdout=payload.get("stdout", ""),
            )

    def _validate_code(self, code: str) -> None:
        lowered = code.lower()
        for token in BANNED_TOKENS:
            if token in lowered:
                raise ExecutionAppError(
                    "unsafe_generated_code",
                    "Generated code contains a blocked operation.",
                    details={"blocked_token": token.strip()},
                )
        if len(code) > 20_000:
            raise ExecutionAppError(
                "generated_code_too_large",
                "Generated code is too large to execute safely.",
            )


def compact_result_for_prompt(result: ExecutionResult) -> dict[str, Any]:
    return {
        "success": result.success,
        "columns": result.result_columns,
        "sample_rows": result.result_rows[:10],
        "chart_spec": result.chart_spec.model_dump() if result.chart_spec else None,
        "error": result.error,
    }
