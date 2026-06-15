# Implementation Notes

## 2026-06-16

### Backend Scope

Built a backend-only Python service. No frontend is included yet. FastAPI is used because it gives an interactive API contract through `/docs`, which is useful for demos and viva.

### Main Design Decisions

1. Use pandas as the canonical in-memory data representation.
2. Use SQLAlchemy for SQL ingestion so SQLite, Postgres, and MySQL can share one path.
3. Keep generated analysis code on a strict contract:
   - `result_df`
   - `chart_spec`
4. Do not silently fall back if Ollama is unavailable.
5. Use dependency injection so tests can use fake LLM responses while production uses Ollama Cloud.
6. Store session history in SQLite instead of only memory.
7. Persist ingested datasets and profiles under runtime storage for process restart recovery.
8. Generate demo data in repeatable scripts.

### Ollama Notes

The configured base URL is `https://ollama.com/v1`, which matches Ollama's OpenAI-compatible API shape. The client calls `/chat/completions` and sends:

- `model`
- `messages`
- `temperature`
- `response_format`
- `reasoning_effort`
- `stream`

The required API key is read from `AUTODATA_OLLAMA_API_KEY`.

### Generated Code Contract

The model must return JSON matching `GeneratedAnalysisCode`.

The generated Python code must not import modules and must define:

```python
result_df = ...
chart_spec = {
    "chart_type": "bar",
    "title": "...",
    "x": "...",
    "y": "...",
    "caption": "..."
}
```

### Testing Strategy

Tests currently cover:

- CSV ingestion and profile creation.
- Excel and JSON ingestion.
- Successful sandbox execution.
- Unsafe generated code rejection.
- Analysis repair loop using a fake LLM.
- Health endpoint.
- Graceful missing Ollama key error.

### Known Limits

- Dataset persistence uses CSV plus profile JSON. This is reliable for demo and tabular business data, but richer type preservation can be improved with parquet later.
- The sandbox is a controlled subprocess runner, not a hardened container.
- The LLM is expected to produce valid JSON. Invalid JSON is handled gracefully, but not auto-repaired yet.
- Chart output is an API spec, not a rendered image. The future frontend can render the spec with Plotly.

### Next Implementation Tasks

1. Upgrade persisted dataset format from CSV to parquet or SQLite for stronger type preservation.
2. Add auth or API key protection if deployed publicly.
3. Add a `/reports/export` endpoint for HTML/PDF summaries.
4. Add richer chart specs for Plotly rendering.
5. Add integration tests against a real Ollama key when available.
