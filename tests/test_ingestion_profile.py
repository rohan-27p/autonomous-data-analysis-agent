from __future__ import annotations

import io

import pandas as pd

from autodata_agent.core.schemas import DataSourceType
from autodata_agent.services.datasets import DatasetStore


def test_csv_ingestion_builds_profile(tmp_path):
    store = DatasetStore(tmp_path, max_upload_bytes=5_000_000)
    content = b"date,region,sales,profit\n2026-01-01,North,100,20\n2026-01-02,South,150,-5\n"

    info = store.put_file("orders.csv", content)

    assert info.source_type == DataSourceType.CSV
    assert info.row_count == 2
    assert info.column_count == 4
    assert [column.name for column in info.profile.columns] == ["date", "region", "sales", "profit"]


def test_excel_and_json_ingestion(tmp_path):
    store = DatasetStore(tmp_path, max_upload_bytes=5_000_000)
    df = pd.DataFrame(
        [
            {"date": "2026-01-01", "segment": "Consumer", "sales": 100.0},
            {"date": "2026-01-02", "segment": "Corporate", "sales": 200.0},
        ]
    )

    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_info = store.put_file("orders.xlsx", excel_buffer.getvalue())
    json_info = store.put_file("orders.json", df.to_json(orient="records").encode("utf-8"))

    assert excel_info.source_type == DataSourceType.EXCEL
    assert json_info.source_type == DataSourceType.JSON
    assert excel_info.profile.row_count == json_info.profile.row_count == 2


def test_dataset_store_rehydrates_from_disk(tmp_path):
    upload_dir = tmp_path / "uploads"
    dataset_dir = tmp_path / "datasets"
    store = DatasetStore(upload_dir, max_upload_bytes=5_000_000, dataset_dir=dataset_dir)
    info = store.put_file("orders.csv", b"category,sales\nA,100\nB,50\n")

    restarted_store = DatasetStore(upload_dir, max_upload_bytes=5_000_000, dataset_dir=dataset_dir)
    restored = restarted_store.get(info.dataset_id)

    assert restored.profile.row_count == 2
    assert list(restored.dataframe.columns) == ["category", "sales"]
