from __future__ import annotations

import json

from autodata_agent.core.errors import ExecutionAppError, ValidationAppError
from autodata_agent.core.json_utils import extract_json_object
from autodata_agent.core.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    GeneratedAnalysisCode,
    Narrative,
)
from autodata_agent.services.datasets import DatasetStore
from autodata_agent.services.executor import CodeExecutor, compact_result_for_prompt
from autodata_agent.services.llm import LLMClient
from autodata_agent.storage.session_store import SessionStore

GENERATION_SYSTEM_PROMPT = """You are the code-generation brain for a data analysis backend.
Return only valid JSON. Do not include markdown.
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

        execution = self.executor.execute(stored.dataframe, generated.code)
        attempts = 1
        while not execution.success and attempts <= self.max_repair_attempts:
            generated = self._repair_code(
                question=request.question,
                profile=stored.profile.model_dump(mode="json"),
                failed_code=generated.code,
                error=execution.error or "Unknown execution error.",
            )
            attempts += 1
            execution = self.executor.execute(stored.dataframe, generated.code)
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
        raw = self.llm.chat_json(system=GENERATION_SYSTEM_PROMPT, user=user)
        return self._parse_generated(raw)

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
            return Narrative.model_validate(extract_json_object(raw))
        except ValidationAppError:
            raise
        except Exception as exc:
            raise ValidationAppError(
                "invalid_narrative",
                "The model returned a narrative that did not match the required schema.",
                details={"reason": str(exc)},
            ) from exc

    def _parse_generated(self, raw: str) -> GeneratedAnalysisCode:
        data = extract_json_object(raw)
        try:
            return GeneratedAnalysisCode.model_validate(data)
        except Exception as exc:
            raise ValidationAppError(
                "invalid_generated_analysis",
                "The model returned generated analysis that did not match the required schema.",
                details={"reason": str(exc)},
            ) from exc

    def _history_summary(self, response: AnalysisResponse) -> dict:
        return {
            "question": response.question,
            "operation": response.plan.operation,
            "key_finding": response.narrative.key_finding,
            "result_columns": response.execution.result_columns,
            "sample_rows": response.execution.result_rows[:5],
        }
