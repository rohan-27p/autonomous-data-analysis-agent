# Autonomous Data Analysis Agent Backend

Python backend for Assignment 9: Autonomous Data Analysis Agent.

The backend accepts structured data, profiles it, sends business questions to an Ollama cloud model, executes generated analysis code in a controlled runner, repairs failed generated code, returns chart metadata and a business narrative, and stores session history for follow-up questions.

## Current Default Model

Default: `kimi-k2.7-code:cloud`

Reason: Ollama lists it as a current cloud model focused on agentic coding, with tool/thinking support and a 256K context window. That fits this backend because the model must generate and repair Python analysis code from schema/profile context. `glm-5.1:cloud` is the documented alternate for agentic engineering.

References:
- https://ollama.com/library/kimi-k2.7-code
- https://ollama.com/library/glm-5.1
- https://docs.ollama.com/api/openai-compatibility

## Features Implemented

- CSV, Excel, JSON ingestion.
- SQL ingestion through SQLAlchemy for SELECT queries.
- Automatic dataset profiling: schema, data types, null rates, distributions, duplicate rows, and anomaly hints.
- Ollama Cloud client using OpenAI-compatible `/chat/completions`.
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
AUTODATA_OLLAMA_MODEL=kimi-k2.7-code:cloud
```

Run the API:

```powershell
uvicorn autodata_agent.api.app:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
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

