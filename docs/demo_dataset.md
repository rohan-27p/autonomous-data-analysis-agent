# Demo Dataset — Acme Retail Sales 2025

A clean, single-table sales dataset built specifically to showcase the agent during a
presentation/viva. It is intentionally a **single flat sheet with simple column names**, so
the LLM reliably generates good pandas and every analysis type produces a crisp answer.

## Files

| File | Use |
|---|---|
| [`demo_sales_dataset.csv`](demo_sales_dataset.csv) | Recommended for the live demo (most reliable) |
| [`demo_sales_dataset.xlsx`](demo_sales_dataset.xlsx) | Same data as a single-sheet workbook, if you want to show Excel ingestion |

Regenerate (reproducible, fixed seed) with:

```powershell
python scripts/build_demo_sales_dataset.py
```

## What's in it

320 order rows across the 2025 calendar year, 15 columns:

| Column | Type | Notes |
|---|---|---|
| `order_id` | int | Unique order identifier |
| `order_date` | date | Spans Jan–Dec 2025 (enables trend questions) |
| `region` | text | West, East, North, South, Central |
| `country` | text | USA / Canada / Mexico |
| `product_category` | text | Widgets, Gadgets, Gizmos, Accessories |
| `product` | text | 12 specific products |
| `customer_segment` | text | Consumer, SMB, Corporate |
| `sales_channel` | text | Online, Retail, Partner |
| `units` | int | Units sold |
| `unit_price` | float | Price per unit |
| `discount` | float | 0.00–0.30 (a few deep outliers) |
| `revenue` | float | `units * unit_price * (1 - discount)` |
| `cost` | float | `units * unit_cost` |
| `profit` | float | `revenue - cost` |
| `customer_satisfaction` | int | 1–5, with ~8% missing (for data-quality questions) |

**Built-in talking points** (so insights are not flat):
- **Trend:** revenue grows through the year with a clear seasonal spike.
- **Segments:** Corporate has the largest deals; Consumer has the most orders.
- **Categories:** Gizmos drive the most revenue; Accessories are high-volume/low-value.
- **Outliers:** 2 bulk Corporate orders (revenue outliers) and 1 deep-discount loss-making order — perfect for anomaly questions.
- **Data quality:** 25 missing `customer_satisfaction` values to demonstrate profiling.

## Suggested demo script

Each question below was verified end-to-end against the running agent and returns an
LLM-generated analysis (table/chart + business narrative). They cover every capability.

| # | Ask the agent | Capability shown |
|---|---|---|
| 1 | What columns are in this dataset? | Profiling / schema |
| 2 | Which product category generated the highest total revenue? | Aggregation + bar chart |
| 3 | Show the monthly revenue trend across the year. | Trend / time series |
| 4 | What is the total profit by customer segment? | Grouping |
| 5 | What are the top 5 products by revenue? | Ranking |
| 6 | List all orders in the West region with a discount over 20%. | Filtering / lookup |
| 7 | Compare average order value across customer segments. | Segmentation |
| 8 | Is there a relationship between discount and units sold? | Correlation |
| 9 | Find unusual or outlier orders by revenue. | Anomaly detection |
| 10 | Summarize missing values by column. | Data quality |

Tip: ask #2 then click a suggested follow-up to show the conversational session flow, and
use the **Export** button to download the JSON/Markdown report of the session.

## Optional: SQL ingestion demo (PostgreSQL)

To also demo the SELECT-only SQL source, the same data is available in a local
PostgreSQL database:

- **Connection URI:** `postgresql://adaa_user:1234@127.0.0.1:5432/adaa_demo`
- **Table:** `sales` (320 rows, same 15 columns as the CSV)

In the app's **Data Sources → SQL Connection** panel, paste the URI and a query such as:

```sql
SELECT region, product_category, revenue, profit, units FROM sales
```

Then ask, e.g., "Which region has the highest total profit?". Requires the
`psycopg2-binary` driver (already in `pyproject.toml`). Reload the table any time with:

```powershell
python scripts/load_demo_sales_to_postgres.py
```

## Why this dataset (vs. a multi-sheet workbook)

Wide, multi-sheet workbooks flatten into very large profiles, which can occasionally make
the model time out or return malformed output (the backend degrades gracefully to a data
overview in that case). This single-sheet dataset keeps the prompt small and the answers
sharp, so the demo stays predictable.
