"""Load the demo sales dataset into a local PostgreSQL table.

Prerequisites: the role/database must already exist, e.g.
    user = adaa_user, password = 1234, database = adaa_demo
(and the psycopg2-binary driver, which is in pyproject.toml).

Run:
    python scripts/load_demo_sales_to_postgres.py

Override the target with AUTODATA_DEMO_PG_URI if your credentials differ.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

URI = os.environ.get(
    "AUTODATA_DEMO_PG_URI",
    "postgresql://adaa_user:1234@127.0.0.1:5432/adaa_demo",
)
CSV = Path(__file__).resolve().parent.parent / "docs" / "demo_sales_dataset.csv"
TABLE = "sales"


def main() -> None:
    df = pd.read_csv(CSV)
    engine = create_engine(URI)
    df.to_sql(TABLE, engine, if_exists="replace", index=False)
    with engine.connect() as conn:
        count = conn.execute(text(f"SELECT count(*) FROM {TABLE}")).scalar()
    print(f"Loaded {count} rows into '{TABLE}' at {URI.rsplit('@', 1)[-1]}")


if __name__ == "__main__":
    main()
