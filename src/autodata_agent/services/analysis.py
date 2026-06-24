from __future__ import annotations

import json
from typing import Any

from autodata_agent.core.errors import AppError, ExecutionAppError, ValidationAppError
from autodata_agent.core.json_utils import extract_json_object
from autodata_agent.core.schemas import (
    AnalysisOperation,
    AnalysisPlan,
    AnalysisRequest,
    AnalysisResponse,
    ChartSpec,
    ChartType,
    ExecutionResult,
    GeneratedAnalysisCode,
    Narrative,
    ResponseKind,
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
  "code_lines": ["Python code lines. They must define result_df and chart_spec."]
}
Allowed operation values: overview, aggregation, filtering, grouping, trend_analysis,
correlation, segmentation, distribution, anomaly_detection.
Do not return top-level result_df. Do not return top-level chart_spec. Do not include markdown.
Generate Python/pandas code against an existing DataFrame named df.
Prefer code_lines instead of a multiline code string so the JSON stays valid.
The code must define:
1. result_df: a pandas DataFrame containing the final answer.
2. chart_spec: a dict with chart_type, title, x, y, optional color, and caption.
Do not import modules. Use only pd, np, duckdb, math, statistics, and df.
Do not read files, call networks, access environment variables, or mutate external state.
Choose chart_type from: bar, line, scatter, heatmap, distribution, table.
For list, lookup, show-all, or extraction questions, return all matching rows unless the user asks for a limit.
For broad greetings, jokes, insults, or prompts unrelated to the active dataset, create an empty result_df
and a table chart_spec, and state in the objective that no dataset analysis was requested.
"""


REPAIR_SYSTEM_PROMPT = """You repair failed pandas analysis code.
Return only valid JSON with the same schema as the original generation.
Do not include markdown. Do not import modules. Keep the output contract unchanged.
"""


NARRATIVE_SYSTEM_PROMPT = """You write concise business findings for data analysis results.
Return only valid JSON with key_finding, business_meaning, limitations, follow_up_questions.
State uncertainty and limitations clearly. Do not invent facts not supported by result rows.
follow_up_questions must be suggested next user queries the user can click.
Do not ask the user for clarification or context. Avoid phrases like "can you provide",
"would you like", "are there specific", "do you need", or "should I".
"""


ROUTER_SYSTEM_PROMPT = """You are the routing brain for a data-analysis agent.
Return only valid JSON with this schema:
{
  "route": "conversation|profile|preview|lookup|analysis",
  "reason": "short reason",
  "limit": 1-200 or null
}
Choose profile only for structural questions: column names, schema, or data types.
Choose preview when the user asks to see sample rows, first rows, data preview, or wants to check what records look like.
Choose analysis for everything else about the data: listing/finding/filtering specific
records, computation, aggregation, trends, comparisons, charts, correlations, rankings,
summaries, "what is this about", or any derived insight. The analysis path generates real
pandas code against the user's file, so prefer it whenever the answer depends on contents.
Choose conversation only for greetings, thanks, or clearly non-data chat.
Do not generate code in this step.
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
        profile = stored.profile.model_dump(mode="json")
        route = self._route_question(
            question=request.question,
            profile=profile,
            history=[self._history_summary(record.response) for record in history],
        )
        routed_response = self._execute_routed_answer(
            route=route,
            request=request,
            session_id=session_id,
            stored=stored,
        )
        if routed_response is not None:
            self.sessions.append(session_id, request.dataset_id, request.question, routed_response)
            return routed_response

        # The model drives analysis, but a failed/garbled model response must never
        # surface as an error during a live demo. Every LLM step degrades to a
        # guaranteed data overview built directly from the uploaded file.
        try:
            generated = self._generate_code(
                question=request.question,
                profile=profile,
                history=[self._history_summary(record.response) for record in history],
            )
        except AppError:
            generated = self._fallback_overview_code()

        execution = self._execute_generated(stored.dataframe, generated)
        attempts = 1
        while not execution.success and attempts <= self.max_repair_attempts:
            try:
                generated = self._repair_code(
                    question=request.question,
                    profile=profile,
                    failed_code=generated.code,
                    error=execution.error or "Unknown execution error.",
                )
            except AppError:
                break
            attempts += 1
            execution = self._execute_generated(stored.dataframe, generated)

        if not execution.success:
            generated = self._fallback_overview_code()
            execution = self._execute_generated(stored.dataframe, generated)
        execution.attempts = attempts

        try:
            narrative = self._generate_narrative(
                question=request.question,
                profile=stored.profile.model_dump(mode="json"),
                execution=compact_result_for_prompt(execution),
            )
        except AppError:
            narrative = self._fallback_narrative(request.question, execution)
        response = AnalysisResponse(
            session_id=session_id,
            dataset_id=request.dataset_id,
            question=request.question,
            response_kind=self._classify_response_kind(request.question, generated, execution),
            plan=generated.plan,
            generated_code=generated.code,
            execution=execution,
            narrative=narrative,
        )
        self.sessions.append(session_id, request.dataset_id, request.question, response)
        return response

    def _fallback_overview_code(self) -> GeneratedAnalysisCode:
        # A safety net that works for ANY dataset: show the first rows as a table.
        # Used only when the model cannot produce runnable analysis code, so the
        # user always gets a valid answer instead of an error.
        plan = AnalysisPlan(
            operation=AnalysisOperation.OVERVIEW,
            objective="Show a direct overview of the dataset.",
            required_columns=[],
            assumptions=[
                "Automated analysis code was unavailable, so the backend returned a "
                "direct overview of the uploaded data."
            ],
            chart_type=ChartType.TABLE,
        )
        code = (
            "result_df = df.head(50)\n"
            "chart_spec = {"
            "'chart_type': 'table', 'title': 'Dataset overview', "
            "'x': None, 'y': None, "
            "'caption': 'Direct overview of the uploaded dataset.'"
            "}"
        )
        return GeneratedAnalysisCode(plan=plan, code=code)

    @staticmethod
    def _fallback_narrative(question: str, execution: ExecutionResult) -> Narrative:
        row_count = len(execution.result_rows)
        columns = ", ".join(execution.result_columns[:8]) or "the available columns"
        return Narrative(
            key_finding=(
                f"Showing {row_count} row{'' if row_count == 1 else 's'} from the dataset "
                f"for: {question}"
            ),
            business_meaning=(
                f"The result includes {columns}. Review the rows directly to interpret the answer."
            ),
            limitations=[
                "This response was built directly from the data because the AI summary step "
                "was unavailable for this request."
            ],
            follow_up_questions=[],
        )

    def _route_question(
        self,
        *,
        question: str,
        profile: dict,
        history: list[dict],
    ) -> dict[str, Any]:
        user = json.dumps(
            {
                "question": question,
                "dataset_profile": self._compact_profile_for_router(profile),
                "session_history": history,
            },
            ensure_ascii=True,
        )
        try:
            raw = self.llm.chat_json(system=ROUTER_SYSTEM_PROMPT, user=user)
            payload = extract_json_object(raw)
            route = str(payload.get("route", "")).strip().lower()
            if route in {"conversation", "profile", "preview", "lookup", "analysis"}:
                limit = payload.get("limit")
                return {
                    "route": route,
                    "reason": str(payload.get("reason", "")).strip(),
                    "limit": limit if isinstance(limit, int) and 1 <= limit <= 200 else None,
                    "source": "llm",
                }
        except Exception:
            pass
        return self._heuristic_route(question)

    @staticmethod
    def _compact_profile_for_router(profile: dict) -> dict[str, Any]:
        return {
            "source_name": profile.get("source_name"),
            "source_type": profile.get("source_type"),
            "row_count": profile.get("row_count"),
            "column_count": profile.get("column_count"),
            "columns": [
                {
                    "name": column.get("name"),
                    "dtype": column.get("dtype"),
                    "sample_values": column.get("sample_values", [])[:3],
                }
                for column in profile.get("columns", [])
            ],
        }

    @staticmethod
    def _profile_for_prompt(profile: dict) -> dict[str, Any]:
        # Wide, multi-sheet files produce a large full profile (with per-column
        # summaries) that can bloat the prompt to tens of KB. Large JSON inputs make
        # some models echo/truncate instead of emitting the schema, which then fails
        # JSON parsing. Send a compact-but-useful profile so the model still has
        # column names, types, null rates, and a few samples to write pandas with.
        return {
            "source_name": profile.get("source_name"),
            "source_type": profile.get("source_type"),
            "row_count": profile.get("row_count"),
            "column_count": profile.get("column_count"),
            "columns": [
                {
                    "name": column.get("name"),
                    "dtype": column.get("dtype"),
                    "null_rate": column.get("null_rate"),
                    "sample_values": column.get("sample_values", [])[:5],
                }
                for column in profile.get("columns", [])
            ],
        }

    @staticmethod
    def _profile_for_prompt(profile: dict) -> dict[str, Any]:
        # Wide, multi-sheet files produce a large full profile (with per-column
        # summaries) that bloats the prompt to tens of KB. Large JSON inputs make
        # some models echo/truncate instead of emitting the schema, which then
        # fails JSON parsing. Send a compact-but-useful profile so the model has
        # column names, types, null rates, and a few samples to write pandas with.
        return {
            "source_name": profile.get("source_name"),
            "source_type": profile.get("source_type"),
            "row_count": profile.get("row_count"),
            "column_count": profile.get("column_count"),
            "columns": [
                {
                    "name": column.get("name"),
                    "dtype": column.get("dtype"),
                    "null_rate": column.get("null_rate"),
                    "sample_values": column.get("sample_values", [])[:5],
                }
                for column in profile.get("columns", [])
            ],
        }

    def _heuristic_route(self, question: str) -> dict[str, Any]:
        if self._answer_conversational_prompt(
            AnalysisRequest(dataset_id="router", question=question),
            session_id="router",
        ) is not None:
            return {"route": "conversation", "reason": "Greeting or short conversation.", "limit": None, "source": "heuristic"}
        if self._is_preview_question(question):
            return {"route": "preview", "reason": "The user asked to inspect sample rows.", "limit": 10, "source": "heuristic"}
        if self._is_profile_question(question):
            return {"route": "profile", "reason": "The user asked about dataset structure.", "limit": None, "source": "heuristic"}
        return {"route": "analysis", "reason": "The user asked for analysis, lookup, or computation.", "limit": None, "source": "heuristic"}

    def _execute_routed_answer(
        self,
        *,
        route: dict[str, Any],
        request: AnalysisRequest,
        session_id: str,
        stored,
    ) -> AnalysisResponse | None:
        selected_route = route.get("route")
        if selected_route == "conversation":
            return self._answer_conversational_prompt(request, session_id)
        if selected_route == "profile":
            return self._answer_profile_prompt(request, session_id, stored.profile, route=route)
        if selected_route == "preview":
            return self._answer_preview_prompt(request, session_id, stored.dataframe, route=route)
        # "lookup" and "analysis" both fall through to LLM-generated pandas so the
        # model has full control over how it filters/retrieves rows from the file.
        return None

    def _answer_conversational_prompt(
        self,
        request: AnalysisRequest,
        session_id: str,
    ) -> AnalysisResponse | None:
        normalized = request.question.strip().lower()
        normalized = normalized.strip(" .!?")
        if normalized not in {"hi", "hello", "hey", "yo", "sup", "thanks", "thank you"}:
            return None

        execution = ExecutionResult(
            success=True,
            result_columns=[],
            result_rows=[],
            chart_spec=None,
        )
        narrative = Narrative(
            key_finding="Hi. Ask me a question about the uploaded dataset and I will answer it directly.",
            business_meaning="For example, ask for a list, a summary, a comparison, or a specific lookup from the file.",
            limitations=[],
            follow_up_questions=[
                "List all classes in the uploaded syllabus.",
                "Summarize the evaluations in this dataset.",
            ],
        )
        plan = AnalysisPlan(
            operation=AnalysisOperation.OVERVIEW,
            objective="No dataset analysis was requested.",
            required_columns=[],
            assumptions=[],
            chart_type=ChartType.TABLE,
        )
        return AnalysisResponse(
            session_id=session_id,
            dataset_id=request.dataset_id,
            question=request.question,
            response_kind=ResponseKind.CONVERSATION,
            plan=plan,
            generated_code="",
            execution=execution,
            narrative=narrative,
        )

    def _answer_profile_prompt(
        self,
        request: AnalysisRequest,
        session_id: str,
        profile,
        route: dict[str, Any] | None = None,
    ) -> AnalysisResponse | None:
        if route is None and not self._is_profile_question(request.question):
            return None

        rows = [
            {
                "Column": column.name,
                "Type": column.dtype,
                "Non-null": column.non_null_count,
                "Null %": round(column.null_rate * 100, 2),
                "Unique": column.unique_count,
                "Examples": ", ".join(format(value) for value in column.sample_values[:3]),
            }
            for column in profile.columns
        ]
        chart_spec = ChartSpec(
            chart_type=ChartType.TABLE,
            title="Dataset columns",
            x="Column",
            y="Type",
            caption="Column profile from the uploaded dataset.",
        )
        execution = ExecutionResult(
            success=True,
            result_columns=["Column", "Type", "Non-null", "Null %", "Unique", "Examples"],
            result_rows=rows,
            chart_spec=chart_spec,
        )
        column_names = [column.name for column in profile.columns]
        preview_names = ", ".join(column_names[:8])
        extra_count = max(0, len(column_names) - 8)
        extra_text = f", and {extra_count} more" if extra_count else ""
        narrative = Narrative(
            key_finding=(
                f"{profile.source_name} is a {profile.source_type.value.upper()} dataset with "
                f"{profile.row_count} rows and {profile.column_count} columns."
            ),
            business_meaning=(
                f"The columns indicate the file contains records described by: {preview_names}{extra_text}."
            ),
            limitations=[
                "This is a structural summary from the uploaded file profile; it does not infer domain meaning beyond the available column names and sample values."
            ],
            follow_up_questions=[
                "Show a preview of the first rows.",
                "Summarize missing values by column.",
                "Find the highest value in a numeric column.",
            ],
        )
        plan = AnalysisPlan(
            operation=AnalysisOperation.OVERVIEW,
            objective="Answer a dataset profile question from stored metadata.",
            required_columns=[],
            assumptions=[self._route_assumption(route, "The user asked about dataset structure rather than a computed analysis.")],
            chart_type=ChartType.TABLE,
        )
        return AnalysisResponse(
            session_id=session_id,
            dataset_id=request.dataset_id,
            question=request.question,
            response_kind=ResponseKind.ANSWER,
            plan=plan,
            generated_code="",
            execution=execution,
            narrative=narrative,
        )

    def _answer_preview_prompt(
        self,
        request: AnalysisRequest,
        session_id: str,
        df,
        route: dict[str, Any] | None = None,
    ) -> AnalysisResponse | None:
        if route is None and not self._is_preview_question(request.question):
            return None
        limit = route.get("limit") if route else None
        if not isinstance(limit, int):
            limit = 10
        result_df = df.head(max(1, min(limit, 50))).copy()
        result_rows = self._records_from_dataframe(result_df)
        chart_spec = ChartSpec(
            chart_type=ChartType.TABLE,
            title="Data preview",
            x=str(result_df.columns[0]) if len(result_df.columns) else None,
            y=str(result_df.columns[1]) if len(result_df.columns) > 1 else None,
            caption="Preview rows from the uploaded dataset.",
        )
        execution = ExecutionResult(
            success=True,
            result_columns=[str(column) for column in result_df.columns],
            result_rows=result_rows,
            chart_spec=chart_spec,
        )
        narrative = Narrative(
            key_finding=f"Showing the first {len(result_rows)} row{'' if len(result_rows) == 1 else 's'} from the uploaded dataset.",
            business_meaning="Use this preview to inspect the raw record shape, column values, and whether the file was parsed as expected.",
            limitations=["This is a row preview, not an analytical summary."],
            follow_up_questions=[
                "Summarize this dataset.",
                "Show missing values by column.",
                "Which columns are numeric?",
            ],
        )
        plan = AnalysisPlan(
            operation=AnalysisOperation.OVERVIEW,
            objective="Show a raw data preview.",
            required_columns=[],
            assumptions=[self._route_assumption(route, "The user asked to inspect sample rows.")],
            chart_type=ChartType.TABLE,
        )
        return AnalysisResponse(
            session_id=session_id,
            dataset_id=request.dataset_id,
            question=request.question,
            response_kind=ResponseKind.ANSWER,
            plan=plan,
            generated_code="",
            execution=execution,
            narrative=narrative,
        )

    @staticmethod
    def _is_profile_question(question: str) -> bool:
        # Only structural questions (columns / schema / types) take the cheap
        # deterministic fast path. Interpretive questions ("what is this about",
        # "summarize", "what does it mean") fall through to LLM-generated analysis
        # so the model interprets the user's actual file.
        question_lower = question.lower()
        return any(
            phrase in question_lower
            for phrase in (
                "list all columns",
                "show all columns",
                "what are the columns",
                "which columns",
                "column names",
                "columns",
                "data types",
                "dtypes",
                "schema",
            )
        )

    @staticmethod
    def _is_preview_question(question: str) -> bool:
        question_lower = question.lower()
        return any(
            phrase in question_lower
            for phrase in (
                "show some rows",
                "show rows",
                "sample rows",
                "first rows",
                "preview",
                "head",
                "check data",
                "data in it",
                "what records look like",
            )
        )

    @staticmethod
    def _route_assumption(route: dict[str, Any] | None, default: str) -> str:
        if route and route.get("source") == "llm" and route.get("reason"):
            return f"LLM router selected this path: {route['reason']}"
        return default

    @staticmethod
    def _records_from_dataframe(df) -> list[dict[str, Any]]:
        rows = json.loads(df.where(df.notnull(), None).to_json(orient="records"))
        cleaned = []
        for row in rows:
            content_values = [
                value
                for key, value in row.items()
                if str(key).lower() not in {"sheet_name", "__sheet_name"}
            ]
            if any(value not in (None, "") for value in content_values):
                cleaned.append(row)
        return cleaned

    def _classify_response_kind(
        self,
        question: str,
        generated: GeneratedAnalysisCode,
        execution: ExecutionResult,
    ) -> ResponseKind:
        question_lower = question.lower()
        is_lookup = any(
            token in question_lower
            for token in ("list", "show", "which", "what", "who", "find", "lookup", "give me")
        )
        if generated.plan.chart_type == ChartType.TABLE or is_lookup:
            return ResponseKind.ANSWER
        if execution.chart_spec and execution.chart_spec.chart_type == ChartType.TABLE:
            return ResponseKind.ANSWER
        return ResponseKind.ANALYSIS

    def _execute_generated(
        self,
        df,
        generated: GeneratedAnalysisCode,
    ) -> ExecutionResult:
        # The model drives the analysis: run its code directly and let the real
        # pandas execution (plus the repair loop) surface any genuine errors.
        # We intentionally do not pre-reject the plan's declared required_columns,
        # because the model legitimately lists derived/output column names there
        # (e.g. "avg_revenue_per_unit"), which are not present in the source file.
        try:
            return self.executor.execute(df, generated.code)
        except ExecutionAppError as exc:
            return ExecutionResult(
                success=False,
                error=f"{exc.code}: {exc.message}",
            )

    def _generate_code(
        self,
        *,
        question: str,
        profile: dict,
        history: list[dict],
    ) -> GeneratedAnalysisCode:
        user = json.dumps(
            {
                "question": question,
                "dataset_profile": self._profile_for_prompt(profile),
                "session_history": history,
            },
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
                "dataset_profile": self._profile_for_prompt(profile),
                "failed_code": failed_code,
                "execution_error": error,
            },
            ensure_ascii=True,
        )
        raw = self.llm.chat_json(system=REPAIR_SYSTEM_PROMPT, user=user)
        return self._parse_generated(raw)

    def _generate_narrative(self, *, question: str, profile: dict, execution: dict) -> Narrative:
        user = json.dumps(
            {
                "question": question,
                "dataset_profile": self._profile_for_prompt(profile),
                "execution_result": execution,
            },
            ensure_ascii=True,
        )
        last_error: ValidationAppError | None = None
        for attempt in range(2):
            raw = self.llm.chat_json(system=NARRATIVE_SYSTEM_PROMPT, user=user)
            try:
                return Narrative.model_validate(
                    self._normalize_narrative_payload(extract_json_object(raw))
                )
            except ValidationAppError as exc:
                last_error = exc
                user = self._json_retry_prompt(
                    original_user=user,
                    bad_response=raw,
                    error=exc,
                    attempt=attempt + 1,
                )
            except Exception as exc:
                last_error = ValidationAppError(
                    "invalid_narrative",
                    "The model returned a narrative that did not match the required schema.",
                    details={"reason": str(exc)},
                )
                user = self._json_retry_prompt(
                    original_user=user,
                    bad_response=raw,
                    error=last_error,
                    attempt=attempt + 1,
                )
        if last_error is not None:
            raise last_error
        raise ValidationAppError("invalid_narrative", "The model returned invalid narrative output.")

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
        normalized["follow_up_questions"] = self._normalize_followups(
            normalized.get("follow_up_questions", [])
        )
        return normalized

    def _normalize_followups(self, followups: list[str]) -> list[str]:
        blocked_prefixes = (
            "are there",
            "can you",
            "could you",
            "do you",
            "should i",
            "should we",
            "would you",
        )
        cleaned: list[str] = []
        for followup in followups:
            text = str(followup).strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered.startswith(blocked_prefixes):
                continue
            cleaned.append(text)
        return cleaned[:4]

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
        if "code_lines" in data and "code" not in data:
            code_lines = data.get("code_lines")
            if isinstance(code_lines, list):
                data = dict(data)
                data["code"] = "\n".join(str(line) for line in code_lines)

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
