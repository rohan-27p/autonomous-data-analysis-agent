from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from autodata_agent.core.errors import ValidationAppError
from autodata_agent.core.schemas import DatasetInfo, DataSourceType, SQLIngestRequest
from autodata_agent.services.profiling import build_profile


@dataclass(frozen=True)
class StoredDataset:
    dataset_id: str
    dataframe: pd.DataFrame
    source_name: str
    source_type: DataSourceType
    profile: object


class DatasetStore:
    def __init__(self, upload_dir: Path, max_upload_bytes: int) -> None:
        self.upload_dir = upload_dir
        self.max_upload_bytes = max_upload_bytes
        self._datasets: dict[str, StoredDataset] = {}

    def put_file(self, filename: str, content: bytes) -> DatasetInfo:
        if not content:
            raise ValidationAppError("empty_upload", "Uploaded file is empty.")
        if len(content) > self.max_upload_bytes:
            raise ValidationAppError(
                "upload_too_large",
                "Uploaded file exceeds the configured size limit.",
                details={"max_upload_bytes": self.max_upload_bytes},
            )

        suffix = Path(filename).suffix.lower()
        if suffix == ".csv":
            source_type = DataSourceType.CSV
            df = pd.read_csv(io.BytesIO(content))
        elif suffix in {".xlsx", ".xls"}:
            source_type = DataSourceType.EXCEL
            df = pd.read_excel(io.BytesIO(content))
        elif suffix == ".json":
            source_type = DataSourceType.JSON
            df = pd.read_json(io.BytesIO(content))
        else:
            raise ValidationAppError(
                "unsupported_file_type",
                "Supported file types are CSV, Excel, and JSON.",
                details={"filename": filename},
            )

        saved_name = f"{uuid.uuid4().hex}_{Path(filename).name}"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        (self.upload_dir / saved_name).write_bytes(content)
        return self._store(df, Path(filename).name, source_type)

    def put_sql(self, request: SQLIngestRequest) -> DatasetInfo:
        cleaned = request.query.strip().lower()
        if not cleaned.startswith("select"):
            raise ValidationAppError(
                "unsafe_sql_query",
                "Only SELECT queries are allowed for SQL ingestion.",
            )
        try:
            engine = create_engine(request.connection_uri)
            with engine.connect() as connection:
                df = pd.read_sql_query(text(request.query), connection)
        except Exception as exc:  # noqa: BLE001 - returned as structured API error
            raise ValidationAppError(
                "sql_ingestion_failed",
                "SQL ingestion failed.",
                details={"reason": str(exc)},
            ) from exc
        return self._store(df, request.source_name, DataSourceType.SQL)

    def get(self, dataset_id: str) -> StoredDataset:
        try:
            return self._datasets[dataset_id]
        except KeyError as exc:
            raise ValidationAppError(
                "dataset_not_found",
                "Dataset was not found in the current backend session.",
                status_code=404,
                details={"dataset_id": dataset_id},
            ) from exc

    def _store(
        self,
        df: pd.DataFrame,
        source_name: str,
        source_type: DataSourceType,
    ) -> DatasetInfo:
        if df.empty:
            raise ValidationAppError("empty_dataset", "Dataset contains no rows.")
        df = df.copy()
        df.columns = [str(column).strip() for column in df.columns]
        if not all(df.columns):
            raise ValidationAppError("invalid_columns", "Dataset contains blank column names.")
        dataset_id = uuid.uuid4().hex
        profile = build_profile(
            df,
            dataset_id=dataset_id,
            source_name=source_name,
            source_type=source_type,
        )
        self._datasets[dataset_id] = StoredDataset(
            dataset_id,
            df,
            source_name,
            source_type,
            profile,
        )
        return DatasetInfo(
            dataset_id=dataset_id,
            source_name=source_name,
            source_type=source_type,
            row_count=profile.row_count,
            column_count=profile.column_count,
            profile=profile,
        )
