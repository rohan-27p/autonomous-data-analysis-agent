# Autonomous Data Analysis Agent - Project Pack

Source PDF: `C:\Users\lostdecimal27\Downloads\Group Projects.pdf`  
Assignment: Assignment 9: Autonomous Data Analysis Agent  
Project deadline: 18 June 2026  
Viva starts: 22 June 2026

## 1. Source-Grounded Assignment Extract

### Exact Project Line

"Drop in a CSV. Ask a business question. Get the full analysis - not just a chart."

### Assignment Metadata

| Field | Value |
|---|---|
| Assignment | #9 of 15 |
| Category | Data AI |
| Group size | 5 students |
| Marks | 15 + 3 Bonus |

### Exact Problem Statement

"Any business user should be able to get a rigorous data answer without knowing SQL or Python. Data scientists are bottlenecked with ad-hoc queries. This tool eliminates that bottleneck."

### What You Are Building

"A conversational data analysis agent: upload data, ask questions, watch code get written and executed, receive visualisations and plain-English findings with uncertainty clearly stated."

### Core Features From Source

1. Data Ingestion - Accept CSV, Excel, JSON, and SQL connections. Profile the data automatically: schema, data types, null rates, value distributions, and anomalies.
2. Natural Language Query - Accept business questions in plain English. Translate to analytical operations: aggregation, filtering, grouping, trend analysis, correlation, or segmentation.
3. Code Generation & Execution - Generate Python or SQL for the required analysis. Execute in a sandboxed environment. Handle errors iteratively - retry with corrected code if execution fails.
4. Visualisation - Generate appropriate charts: bar, line, scatter, heatmap, distribution. Return chart with title, axis labels, and a plain-English caption.
5. Findings Narrative - Write a plain-English explanation: what was found, what it means, what the limitations are, and what follow-up questions the data suggests.
6. Analysis History - Maintain a session history of all questions, code, and results. Allow iterative follow-up questions that build on earlier analyses.

### Success Metrics From Source

1. Agent correctly answers 5 diverse business questions from a test dataset.
2. Code execution errors are caught and corrected without user intervention.
3. Visualisations use the appropriate chart type for the data and question.
4. Findings narrative correctly identifies the key insight and its limitations.
5. Iterative questions correctly build on context from previous answers in the session.

## 2. MVP Architecture

Recommended fast-build stack for the 18 June deadline: Streamlit frontend, Python backend logic, pandas/DuckDB for analysis, Plotly for charts, SQLAlchemy for SQL connections, and an LLM API or local LLM wrapper for natural-language planning and narrative generation.

### User Flow

1. User uploads data or connects SQL.
2. System profiles the dataset.
3. User asks a business question.
4. Agent converts the question into an analysis plan.
5. Agent generates Python or SQL code.
6. Code runs in a controlled execution layer.
7. If code fails, the error is fed back to the agent and corrected.
8. Results are visualized.
9. Agent writes findings, limitations, and follow-up suggestions.
10. Session history stores question, plan, code, chart, result, and narrative.

### Components

| Component | MVP Responsibility |
|---|---|
| UI layer | Upload files, collect questions, display profile, code, chart, findings, and history |
| Ingestion service | Load CSV, Excel, JSON, and SQL table/query data into a DataFrame |
| Profiler | Generate schema, dtypes, missing values, distributions, duplicate counts, and anomaly hints |
| Query planner | Classify user question into operations: aggregation, filtering, grouping, trend, correlation, segmentation |
| Code generator | Produce pandas/DuckDB code from the question, profile, and session context |
| Sandbox executor | Run generated code with restricted globals, timeout, and allowed libraries only |
| Error repair loop | Capture traceback, ask generator for corrected code, retry up to a fixed limit |
| Visualization selector | Choose bar, line, scatter, heatmap, or distribution based on question and result shape |
| Narrative generator | Explain insight, business meaning, limitations, and follow-up questions |
| Session store | Save every question, generated code, result summary, chart metadata, and follow-up context |

### Practical MVP Boundaries

Must-have for submission:
- File ingestion for CSV, Excel, JSON.
- At least one SQL path, preferably SQLite/Postgres via SQLAlchemy or DuckDB SQL over uploaded files.
- Dataset profile shown before questions.
- Five question demos with code, chart, and narrative.
- Error correction demo using an intentionally failing generated snippet or a real failed first attempt.
- Follow-up question using previous context.

Stretch/bonus:
- Multiple table SQL joins.
- Stronger sandboxing using subprocess/container isolation.
- Export analysis report as PDF/HTML.
- User-selectable chart alternatives.
- Confidence/uncertainty score based on missingness, sample size, and assumptions.

## 3. Implementation Backlog Ordered By Deadline

### 15 June 2026 - Foundation

1. Confirm repo, stack, team split, and dataset.
2. Build Streamlit app shell: upload panel, profile panel, chat/question panel, output panel, history panel.
3. Implement ingestion for CSV, XLSX, JSON.
4. Implement basic profiling:
   - rows/columns
   - column names and dtypes
   - null counts and null rates
   - numeric min/mean/max/std
   - categorical top values
   - duplicate rows
5. Choose one test dataset and write five target business questions.

### 16 June 2026 - Agent Core

1. Implement question classifier for aggregation, grouping, trend, correlation, segmentation, filtering, and distribution.
2. Add LLM prompt/template that receives schema, profile, previous context, and user question.
3. Generate pandas or DuckDB code with a required output contract:
   - `result_df`
   - `chart_spec`
   - `caption`
   - `limitations`
4. Build executor with allowed imports only, timeout, and traceback capture.
5. Add error correction loop with max 2 retries.
6. Store question, generated code, execution status, result preview, chart metadata, and narrative in session state.

### 17 June 2026 - Visuals, Narrative, Demo Reliability

1. Implement chart selector:
   - bar for grouped comparisons
   - line for time trends
   - scatter for relationships
   - heatmap for correlations
   - histogram/box for distributions
2. Add Plotly chart rendering with title, axis labels, and caption.
3. Implement narrative output:
   - key finding
   - business meaning
   - uncertainty/limitations
   - suggested follow-ups
4. Add SQL connection support:
   - minimum: SQLite file or DuckDB SQL query
   - better: SQLAlchemy URI for Postgres/MySQL/SQLite
5. Run all five demo questions and save screenshots or notes.
6. Add README with setup, features, limitations, and viva talking points.

### 18 June 2026 - Submission Stabilization

1. Freeze the demo dataset and demo questions.
2. Test fresh setup on another machine or clean environment.
3. Verify source success metrics one by one.
4. Prepare final demo script.
5. Prepare viva explanation sheet.
6. Tag/zip/submit repo with README, requirements, sample dataset, and screenshots.

### 19-21 June 2026 - Viva Prep

1. Rehearse 8-10 minute demo.
2. Prepare answers for sandboxing, hallucination risk, chart choice, limitations, and error repair.
3. Prepare backup screenshots in case live LLM/API fails.
4. Prepare one slide/page explaining architecture.

## 4. Demo Script With 5 Diverse Business Questions

Use one business dataset with columns like `date`, `region`, `product_category`, `customer_segment`, `sales`, `profit`, `discount`, `quantity`, `customer_id`, and `order_id`. A retail/e-commerce sales dataset works well because it supports trend, grouping, segmentation, correlation, and distribution questions.

### Demo Opening

"This project is an autonomous data analysis agent for business users. The user uploads business data, asks a natural-language question, and the system generates executable analysis code, visualizes the result, explains the insight, states limitations, and remembers the session for follow-up questions."

### Question 1 - Aggregation / Ranking

Business question: "Which product categories generated the highest total revenue?"

Expected operation: group by product category, sum sales, sort descending.  
Expected chart: bar chart.  
Narrative angle: identify top categories and whether revenue is concentrated.

### Question 2 - Trend Analysis

Business question: "How have monthly sales and profit changed over time?"

Expected operation: parse date, group by month, sum sales and profit.  
Expected chart: line chart.  
Narrative angle: growth/decline periods, seasonality, profit-sales divergence.

### Question 3 - Segmentation

Business question: "Which customer segment is most profitable, and where are margins weakest?"

Expected operation: group by customer segment, compute sales, profit, and profit margin.  
Expected chart: bar chart or grouped bar.  
Narrative angle: high-revenue segment may not be highest-margin segment.

### Question 4 - Correlation / Relationship

Business question: "Is discount level related to profit?"

Expected operation: calculate correlation between discount and profit; optionally bin discounts and compare average profit.  
Expected chart: scatter plot or heatmap.  
Narrative angle: discounting may increase sales but reduce profit.

### Question 5 - Distribution / Anomalies

Business question: "Are there unusual orders with very high sales, very high discounts, or negative profit?"

Expected operation: detect outliers using thresholds/IQR and filter negative profit rows.  
Expected chart: distribution plot or scatter plot.  
Narrative angle: anomalies need investigation before making business decisions.

### Follow-Up Question To Prove Session History

After Question 3, ask: "For that weakest-margin segment, which categories are causing the problem?"

Expected behavior: the agent understands "that weakest-margin segment" from previous context and filters/group-analyzes within that segment.

### Error Correction Demo

Use one of these controlled options:

1. Ask a question that references a likely alias: "Show revenue by category" when the dataset column is named `sales`, not `revenue`.
2. Temporarily make first generated code use a wrong column name, capture `KeyError`, then show the repair loop mapping `revenue` to `sales`.
3. Use a date question where dates are strings, causing an initial datetime issue, then show automatic correction with `pd.to_datetime`.

## 5. Viva-Friendly Explanation Sheet

### Data Ingestion

The system accepts structured business data from files and SQL. For files, CSV, Excel, and JSON are parsed into a DataFrame. For SQL, the MVP can connect through SQLAlchemy or DuckDB and load a selected table/query. Immediately after loading, the system profiles the data so the agent knows column names, data types, missing values, distributions, and possible anomalies before generating analysis.

Viva answer: "Profiling reduces hallucination because the model is not guessing column names or data types. It receives the actual schema and summary statistics before writing code."

### Natural-Language Query Translation

The user asks a plain-English business question. The agent classifies the intent into analytical operations such as aggregation, filtering, grouping, trend analysis, correlation, or segmentation. The schema, profile, and session history are included as context so the generated plan matches the available data.

Viva answer: "The system converts business language into an analysis plan first, then code. This makes the process explainable and easier to debug."

### Code Generation And Execution

The generator produces Python/pandas or SQL code for the analysis. The code follows a fixed contract, such as returning `result_df`, chart metadata, and a short result summary. The executor runs this code with restricted imports, a timeout, and controlled access to the uploaded dataset.

Viva answer: "We separate generation from execution. The model writes code, but the application controls what can run and validates whether expected outputs were produced."

### Visualization

The visualization layer selects chart types based on the question and output shape. Grouped comparisons use bar charts, time trends use line charts, relationships use scatter plots, correlations use heatmaps, and distributions use histograms or box plots. Every chart includes a title, axis labels, and a plain-English caption.

Viva answer: "The chart is not random; it is selected from the analytical intent and result structure."

### Findings Narrative

The narrative explains what was found, what it means for the business, what limitations exist, and what follow-up questions are useful. Limitations may include missing data, small sample size, correlation not implying causation, outlier sensitivity, or incomplete date ranges.

Viva answer: "The answer is more than a chart. It includes interpretation and uncertainty, which is important for business decisions."

### Error Correction

If execution fails, the traceback and generated code are passed back into the correction step. The agent repairs the code and retries automatically up to a fixed limit. Common fixes include wrong column names, date parsing, missing imports, invalid aggregation syntax, or empty filters.

Viva answer: "The success metric requires execution errors to be caught and corrected without user intervention, so the retry loop is a core feature, not an extra."

### Session History

Each interaction stores the user question, inferred intent, generated code, execution result, chart, narrative, and key entities such as selected segment/category/date range. Follow-up questions can refer to previous outputs, for example "that segment" or "same period."

Viva answer: "Session history makes the agent conversational. It allows iterative analysis instead of isolated one-shot queries."

## 6. Source Success Metric Checklist

| Source metric | Demo evidence to prepare |
|---|---|
| Correctly answers 5 diverse business questions | Run the five demo questions above on the same dataset |
| Code execution errors are caught and corrected | Show one retry with captured error and corrected code |
| Visualisations use appropriate chart type | Use bar, line, scatter/heatmap, and distribution charts |
| Findings narrative identifies key insight and limitations | Every answer must include insight + limitation |
| Iterative questions build on previous context | Use the "weakest-margin segment" follow-up |

## 7. Missing Inputs Needed From User

1. Repository path or confirmation that a new repo should be created.
2. Chosen stack, if already decided.
3. Team member names and roles.
4. Current project progress, if any.
5. Dataset choice and whether it can be included in the submission.
6. Whether internet/API access is allowed during demo.
7. LLM provider/model preference and available API key setup.
8. Required submission format: GitHub link, ZIP, report, PPT, video, or live demo.
9. Target SQL connection requirement: SQLite only, Postgres/MySQL, or any SQL database.
10. University rules around using external LLM APIs.
11. Whether bonus marks are being targeted.
12. Viva duration and whether each team member must explain a module.

## 8. Suggested Team Split For 5 Students

1. Ingestion and profiling owner.
2. NL planning and prompt/code generation owner.
3. Execution sandbox and error correction owner.
4. Visualization and narrative owner.
5. UI, session history, testing, README, and demo owner.

## 9. High-Risk Areas To Handle Early

1. SQL connections may take longer than file upload. Implement SQLite/DuckDB first.
2. Generated code can be unsafe or flaky. Restrict execution and use output contracts.
3. LLM may invent columns. Always include exact schema and reject code using unknown columns.
4. Demo can fail if API/network fails. Prepare cached demo outputs or screenshots.
5. Narratives can overclaim. Force a limitations section in every answer.

