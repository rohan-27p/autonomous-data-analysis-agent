from __future__ import annotations

import sqlite3

from autodata_agent.core.schemas import SQLIngestRequest
from autodata_agent.services.datasets import DatasetStore


def test_sql_ingestion_accepts_select_queries(tmp_path):
    db_path = tmp_path / "orders.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE orders(category TEXT, sales REAL)")
        conn.executemany("INSERT INTO orders VALUES (?, ?)", [("A", 100), ("B", 50)])

    store = DatasetStore(tmp_path / "uploads", max_upload_bytes=5_000_000)
    info = store.put_sql(
        SQLIngestRequest(
            connection_uri=f"sqlite:///{db_path}",
            query="SELECT category, sales FROM orders",
            source_name="orders_sql",
        )
    )

    assert info.source_type == "sql"
    assert info.row_count == 2
    assert info.profile.source_name == "orders_sql"
