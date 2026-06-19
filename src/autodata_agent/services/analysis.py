from __future__ import annotations

import json

from autodata_agent.core.errors import ExecutionAppError, ValidationAppError
from autodata_agent.core.json_utils import extract_json_object
from autodata_agent.core.schemas import (
    AnalysisOperation,
    AnalysisPlan,
    AnalysisRequest,
    AnalysisResponse,
    ChartType,
    ExecutionResult,
    GeneratedAnalysisCode,
    Narrative,
)
from autodata_agent.services.datasets import DatasetStore
from autodata_agent.services.executor import CodeExecutor, compact_result_for_prompt
from autodata_agent.services.llm import LLMClient
from autodata_agent.storage.session_store import SessionStore

GENERATION_SYSTEM_PROMPT = """You are the code-generation brain for a data analysis backend.
Return only valid JSON matching this exact schema:
{
  "plan": {
    "operation": "one allowed operation value",
    "objective": "short objective",
    "required_columns": ["only columns that exist in the dataset"],
    "assumptions": ["short assumptions"],
    "chart_type": "bar|line|scatter|heatmap|distribution|table"
  },
  "code": "Python code as one string. It must define result_df and chart_spec."
}
Allowed operation values: overview, aggregation, filtering, grouping, trend_analysis,
correlation, segmentation, distribution, anomaly_detection.
Do not return top-level result_df. Do not return top-level chart_spec. Do not include markdown.
Generate Python/pandas code against an existing DataFrame named df.
The code must define:
1. result_df: a pandas DataFrame containing the final answer.
2. chart_spec: a dict with chart_type, title, x, y, optional color, and caption.
Do not import modules. Use only pd, np, duckdb, math, statistics, and df.
Do not read files, call networks, access environment variables, or mutate external state.
Choose chart_type from: bar, line, scatter, heatmap, distribution, table.
"""


REPAIR_SYSTEM_PROMPT = """You repair failed pandas analysis code.
Return only valid JSON with the same schema as the original generation.
Do not include markdown. Do not import modules. Keep the output contract unchanged.
"""


NARRATIVE_SYSTEM_PROMPT = """You write concise business findings for data analysis results.
Return only valid JSON with key_finding, business_meaning, limitations, follow_up_questions.
State uncertainty and limitations clearly. Do not invent facts not supported by result rows.
"""


class AnalysisService:
    def __init__(
        self,
        *,
        datasets: DatasetStore,
        sessions: SessionStore,
        llm: LLMClient,
        executor: CodeExecutor,
        max_repair_attempts: int,
    ) -> None:
        self.datasets = datasets
        self.sessions = sessions
        self.llm = llm
        self.executor = executor
        self.max_repair_attempts = max_repair_attempts

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        stored = self.datasets.get(request.dataset_id)
        session_id = request.session_id or self.sessions.create_session_id()
        history = self.sessions.history(session_id, limit=5)
        generated = self._generate_code(
            question=request.question,
            profile=stored.profile.model_dump(mode="json"),
            history=[self._history_summary(record.response) for record in history],
        )

        profile = stored.profile.model_dump(mode="json")
        execution = self._execute_generated(stored.dataframe, generated, profile)
        attempts = 1
        while not execution.success and attempts <= self.max_repair_attempts:
            generated = self._repair_code(
                question=request.question,
                profile=profile,
                failed_code=generated.code,
                error=execution.error or "Unknown execution error.",
            )
            attempts += 1
            execution = self._execute_generated(stored.dataframe, generated, profile)
        execution.attempts = attempts

        if not execution.success:
            raise ExecutionAppError(
                "analysis_execution_failed",
                "Generated analysis code failed after repair attempts.",
                status_code=422,
                details={"attempts": attempts, "error": execution.error},
            )

        narrative = self._generate_narrative(
            question=request.question,
            profile=stored.profile.model_dump(mode="json"),
            execution=compact_result_for_prompt(execution),
        )
        response = AnalysisResponse(
            session_id=session_id,
            dataset_id=request.dataset_id,
            question=request.question,
            plan=generated.plan,
            generated_code=generated.code,
            execution=execution,
            narrative=narrative,
        )
        self.sessions.append(session_id, request.dataset_id, request.question, response)
        return response

    def _execute_generated(
        self,
        df,
        generated: GeneratedAnalysisCode,
        profile: dict,
    ) -> ExecutionResult:
        plan_error = self._validate_generated_plan(generated, profile)
        if plan_error is not None:
            return plan_error
        try:
            return self.executor.execute(df, generated.code)
        except ExecutionAppError as exc:
            return ExecutionResult(
                success=False,
                error=f"{exc.code}: {exc.message}",
            )

    def _validate_generated_plan(
        self,
        generated: GeneratedAnalysisCode,
        profile: dict,
    ) -> ExecutionResult | None:
        available_columns = {str(column["name"]) for column in profile.get("columns", [])}
        missing = [
            column
            for column in generated.plan.required_columns
            if column not in available_columns
        ]
        if missing:
            return ExecutionResult(
                success=False,
                error=(
                    "Generated plan referenced columns that do not exist in the dataset: "
                    f"{missing}. Available columns: {sorted(available_columns)}"
                ),
            )
        return None

    def _generate_code(
        self,
        *,
        question: str,
        profile: dict,
        history: list[dict],
    ) -> GeneratedAnalysisCode:
        user = json.dumps(
            {"question": question, "dataset_profile": profile, "session_history": history},
            ensure_ascii=True,
        )
        last_error: ValidationAppError | None = None
        for attempt in range(2):
            raw = self.llm.chat_json(system=GENERATION_SYSTEM_PROMPT, user=user)
            try:
                return self._parse_generated(raw)
            except ValidationAppError as exc:
                last_error = exc
                user = self._json_retry_prompt(
                    original_user=user,
                    bad_response=raw,
                    error=exc,
                    attempt=attempt + 1,
                )
        if last_error is not None:
            raise last_error
        raise ValidationAppError("invalid_generated_analysis", "The model returned invalid output.")

    def _repair_code(
        self,
        *,
        question: str,
        profile: dict,
        failed_code: str,
        error: str,
    ) -> GeneratedAnalysisCode:
        user = json.dumps(
            {
                "question": question,
                "dataset_profile": profile,
                "failed_code": failed_code,
                "execution_error": error,
            },
            ensure_ascii=True,
        )
        raw = self.llm.chat_json(system=REPAIR_SYSTEM_PROMPT, user=user)
        return self._parse_generated(raw)

    def _generate_narrative(self, *, question: str, profile: dict, execution: dict) -> Narrative:
        user = json.dumps(
            {"question": question, "dataset_profile": profile, "execution_result": execution},
            ensure_ascii=True,
        )
        raw = self.llm.chat_json(system=NARRATIVE_SYSTEM_PROMPT, user=user)
        try:
            return Narrative.model_validate(
                self._normalize_narrative_payload(extract_json_object(raw))
            )
        except ValidationAppError:
            raise
        except Exception as exc:
            raise ValidationAppError(
                "invalid_narrative",
                "The model returned a narrative that did not match the required schema.",
                details={"reason": str(exc)},
            ) from exc

    def _normalize_narrative_payload(self, data: dict) -> dict:
        normalized = dict(data)
        for key in ("limitations", "follow_up_questions"):
            value = normalized.get(key)
            if isinstance(value, str):
                normalized[key] = [value]
            elif value is None:
                normalized[key] = []
        for key in ("key_finding", "business_meaning"):
            value = normalized.get(key)
            if isinstance(value, list):
                normalized[key] = " ".join(str(item) for item in value)
        return normalized

    def _parse_generated(self, raw: str) -> GeneratedAnalysisCode:
        data = extract_json_object(raw)
        data = self._normalize_generated_payload(data)
        try:
            return GeneratedAnalysisCode.model_validate(data)
        except Exception as exc:
            raise ValidationAppError(
                "invalid_generated_analysis",
                "The model returned generated analysis that did not match the required schema.",
                details={"reason": str(exc)},
            ) from exc

    def _normalize_generated_payload(self, data: dict) -> dict:
        if "plan" in data and "code" in data:
            return data

        if "result_df" not in data and "chart_spec" not in data:
            return data

        result_expr = data.get("result_df", "df.head(10)")
        if not isinstance(result_expr, str) or not result_expr.strip():
            result_expr = "df.head(10)"
        chart_spec = data.get("chart_spec")
        if not isinstance(chart_spec, dict):
            chart_spec = {
                "chart_type": "table",
                "title": "Dataset Overview",
                "x": None,
                "y": None,
                "caption": "Generated dataset overview.",
            }

        chart_type = chart_spec.get("chart_type", ChartType.TABLE)
        required_columns = [
            value
            for value in (chart_spec.get("x"), chart_spec.get("y"), chart_spec.get("color"))
            if isinstance(value, str) and value
        ]
        code = "\n".join(
            [
                f"result_df = {result_expr}",
                f"chart_spec = {chart_spec!r}",
            ]
        )
        return {
            "plan": AnalysisPlan(
                operation=AnalysisOperation.OVERVIEW,
                objective=str(
                    chart_spec.get("caption")
                    or chart_spec.get("title")
                    or "Dataset overview"
                ),
                required_columns=required_columns,
                assumptions=[
                    "Model returned a compact result expression and chart spec; "
                    "backend normalized it to the executable analysis contract."
                ],
                chart_type=chart_type,
            ).model_dump(mode="json"),
            "code": code,
        }

    def _history_summary(self, response: AnalysisResponse) -> dict:
        return {
            "question": response.question,
            "operation": response.plan.operation,
            "key_finding": response.narrative.key_finding,
            "result_columns": response.execution.result_columns,
            "sample_rows": response.execution.result_rows[:5],
        }

    def _json_retry_prompt(
        self,
        *,
        original_user: str,
        bad_response: str,
        error: ValidationAppError,
        attempt: int,
    ) -> str:
        return json.dumps(
            {
                "instruction": (
                    "Your previous response was rejected. Return exactly one valid JSON object "
                    "matching the requested schema. Do not include markdown, comments, prose, "
                    "multiple JSON objects, or trailing text."
                ),
                "attempt": attempt,
                "validation_error": {
                    "code": error.code,
                    "message": error.message,
                    "details": error.details,
                },
                "previous_response_preview": bad_response[:1000],
                "original_request": json.loads(original_user),
            },
            ensure_ascii=True,
        )
