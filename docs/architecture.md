# Backend Architecture

## Assignment Mapping

| Assignment requirement | Backend implementation |
|---|---|
| Data ingestion | `DatasetStore.put_file` and `DatasetStore.put_sql` |
| Automatic profiling | `services/profiling.py` |
| Natural-language query | `AnalysisService` sends question, profile, and session history to Ollama |
| Code generation/execution | `OllamaCloudClient` plus `CodeExecutor` |
| Error correction | `AnalysisService` repair loop |
| Visualization | Generated and validated `ChartSpec` |
| Findings narrative | Narrative prompt returning `Narrative` schema |
| Analysis history | SQLite `SessionStore` |

## Runtime Flow

1. API receives file upload or SQL request.
2. Dataset is loaded into a pandas DataFrame.
3. Profiler builds schema, null rates, summaries, and anomaly hints.
4. User submits a business question.
5. Analysis service sends question, profile, and recent history to Ollama.
6. Ollama returns JSON containing an analysis plan and Python code.
7. Analysis service validates that required plan columns exist in the profiled dataset.
8. Executor validates code for blocked operations.
9. Executor runs code in a separate subprocess with timeout.
10. If validation or execution fails, the error and code are sent to the repair prompt.
11. Successful output returns `result_df`, chart spec, narrative, and session history.

## Failure Policy

The backend should fail gracefully, not silently fall back.

- Missing Ollama key returns `ollama_api_key_missing`.
- Invalid model JSON returns `invalid_llm_json`.
- Invalid generated schema returns `invalid_generated_analysis`.
- Unsafe generated code returns `unsafe_generated_code`.
- Generated plans that reference unknown columns are repaired before execution.
- Execution timeout returns `analysis_timeout`.
- Failed repair attempts return `analysis_execution_failed`.
- Missing dataset returns `dataset_not_found`.
- Malformed or incomplete API requests return `request_validation_failed`.

Each failure is returned as:

```json
{
  "error": {
    "code": "machine_readable_code",
    "message": "Human readable message.",
    "details": {}
  }
}
```

## Sandboxing Notes

The executor is not a full security container. It is a controlled MVP runner:

- runs generated code in a subprocess
- applies a timeout
- blocks imports, file access, network access, subprocess usage, dunder access, and eval/exec/compile in generated code
- exposes only `df`, `pd`, `np`, `duckdb`, `math`, and `statistics`
- requires output variables `result_df` and `chart_spec`

For production, replace this with container isolation or a restricted worker service.

## Model Choice

Default model for direct Ollama Cloud API in this repo: `qwen3-coder:480b`

Rationale:

- Cloud model on Ollama.
- Coding-focused and available to the current API key.
- Good fit for generated Python/pandas analysis code.
- Native cloud API host is `https://ollama.com`; chat requests use `/api/chat`.

Premium recommendation if the account has subscription access: `kimi-k2.7-code`, because Ollama describes it as a current coding-focused agentic model with a 256K context window. Alternate premium model: `glm-5.1`, because Ollama describes it as a flagship agentic engineering model with strong coding capabilities.
