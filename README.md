# Autonomous Data Analysis Agent Backend

Python backend for Assignment 9: Autonomous Data Analysis Agent.

The backend accepts structured data, profiles it, sends business questions to an Ollama cloud model, executes generated analysis code in a controlled runner, repairs failed generated code, returns chart metadata and a business narrative, and stores session history for follow-up questions.

## Current Default Model

Default for direct Ollama Cloud API in this repo: `qwen3-coder:480b`

Reason: `qwen3-coder:480b` is a cloud coding model available to the current API key and is suited for generated Python/pandas analysis code. The best premium choice remains `kimi-k2.7-code`, but the current account receives a subscription-required error for that model. `glm-5.1` is also a strong agentic engineering model, but it currently returns the same subscription-required error on this key.

References:
- https://ollama.com/library/kimi-k2.7-code
- https://ollama.com/library/glm-5.1
- https://docs.ollama.com/api/openai-compatibility

## Features Implemented

- CSV, Excel, JSON ingestion.
- SQL ingestion through SQLAlchemy for SELECT queries.
- Automatic dataset profiling: schema, data types, null rates, distributions, duplicate rows, and anomaly hints.
- Ollama Cloud client using native `/api/chat`.
- Generated Python analysis code contract: `result_df` and `chart_spec`.
- Controlled subprocess execution with blocked unsafe operations and timeout.
- Error repair loop with configurable retry count.
- Chart specification validation for bar, line, scatter, heatmap, distribution, and table outputs.
- Findings narrative generation with limitations and follow-up questions.
- SQLite-backed session history.
- Demo Excel workbook, CSV, and JSON fixtures under `data/`.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
Copy-Item .env.example .env
```

Edit `.env`:

```text
AUTODATA_OLLAMA_API_KEY=your_ollama_key
AUTODATA_OLLAMA_BASE_URL=https://ollama.com
AUTODATA_OLLAMA_MODEL=qwen3-coder:480b
AUTODATA_OLLAMA_THINK=false
AUTODATA_OLLAMA_NUM_PREDICT=1200
```

Run the API:

```powershell
uvicorn autodata_agent.api.app:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Check Ollama Cloud connectivity:

```powershell
python scripts/check_ollama_connection.py
```

## Main API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Backend health and configured model |
| POST | `/api/v1/datasets/upload` | Upload CSV/XLSX/JSON |
| POST | `/api/v1/datasets/sql` | Ingest SQL SELECT query |
| GET | `/api/v1/datasets/{dataset_id}/profile` | View automatic profile |
| POST | `/api/v1/analysis` | Ask a business question |
| GET | `/api/v1/sessions/{session_id}/history` | Read session history |

## Example Request Flow

1. Upload `data/autodata_demo_business_dataset.xlsx` to `/api/v1/datasets/upload`.
2. Copy the returned `dataset_id`.
3. POST to `/api/v1/analysis`:

```json
{
  "dataset_id": "paste_dataset_id_here",
  "question": "Which product categories generated the highest total revenue?"
}
```

4. Reuse the returned `session_id` for follow-up questions:

```json
{
  "dataset_id": "paste_dataset_id_here",
  "session_id": "paste_session_id_here",
  "question": "For the weakest-margin segment, which categories are causing the problem?"
}
```

## Testing

```powershell
pytest
ruff check .
```

The tests use fake LLM clients where needed. Production analysis does not silently fall back when Ollama is missing; it returns a structured service error.

## Publishing With GitHub Desktop

This workspace is already initialized as a git repository on `main` with logical commits.

To publish the remote repository:

1. Open GitHub Desktop.
2. Add/open this local repository:
   `C:\Users\lostdecimal27\Documents\Codex\2026-06-15\gen-ai-project-agent`
3. Click **Publish repository**.
4. Recommended repository name: `autonomous-data-analysis-agent-backend`.
5. Keep the repo private until submission details are final, unless your course requires public access.

## Demo Data

Generated files:

- `data/autodata_demo_business_dataset.xlsx`
- `data/autodata_demo_orders.csv`
- `data/autodata_demo_orders.json`

Regenerate them with:

```powershell
node scripts/build_demo_workbook.mjs
```

The workbook includes a dashboard, order-level data, summary tables, a data dictionary, demo questions, and QA checks.
