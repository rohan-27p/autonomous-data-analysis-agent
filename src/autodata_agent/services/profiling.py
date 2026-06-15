from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from autodata_agent.core.schemas import ColumnProfile, DatasetProfile, DataSourceType


def _json_safe(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _numeric_summary(series: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {}
    q1 = clean.quantile(0.25)
    q3 = clean.quantile(0.75)
    return {
        "min": _json_safe(clean.min()),
        "mean": _json_safe(clean.mean()),
        "median": _json_safe(clean.median()),
        "max": _json_safe(clean.max()),
        "std": _json_safe(clean.std(ddof=0)),
        "q1": _json_safe(q1),
        "q3": _json_safe(q3),
    }


def _categorical_summary(series: pd.Series) -> dict[str, Any]:
    counts = series.dropna().astype(str).value_counts().head(10)
    return {"top_values": [{"value": idx, "count": int(value)} for idx, value in counts.items()]}


def _datetime_summary(series: pd.Series) -> dict[str, Any]:
    dates = pd.to_datetime(series, errors="coerce").dropna()
    if dates.empty:
        return {}
    return {"min": dates.min().isoformat(), "max": dates.max().isoformat()}


def build_profile(
    df: pd.DataFrame,
    *,
    dataset_id: str,
    source_name: str,
    source_type: DataSourceType,
) -> DatasetProfile:
    row_count = int(len(df))
    duplicate_rows = int(df.duplicated().sum()) if row_count else 0
    columns: list[ColumnProfile] = []
    anomalies: list[str] = []

    if row_count == 0:
        anomalies.append("Dataset has zero rows.")

    if duplicate_rows:
        anomalies.append(f"Dataset contains {duplicate_rows} duplicate rows.")

    for name in df.columns:
        series = df[name]
        null_count = int(series.isna().sum())
        null_rate = float(null_count / row_count) if row_count else 0.0
        non_null = int(row_count - null_count)
        unique_count = int(series.nunique(dropna=True))
        dtype = str(series.dtype)

        if null_rate >= 0.3:
            anomalies.append(f"Column '{name}' has high missingness ({null_rate:.1%}).")
        if row_count and unique_count == row_count and not pd.api.types.is_numeric_dtype(series):
            anomalies.append(f"Column '{name}' appears to be a row identifier.")

        summary: dict[str, Any]
        if pd.api.types.is_numeric_dtype(series):
            summary = _numeric_summary(series)
            clean = pd.to_numeric(series, errors="coerce").dropna()
            if len(clean) >= 8:
                q1 = clean.quantile(0.25)
                q3 = clean.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    outlier_count = int(((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).sum())
                    if outlier_count:
                        summary["iqr_outliers"] = outlier_count
                        anomalies.append(f"Column '{name}' has {outlier_count} IQR outliers.")
        elif pd.api.types.is_datetime64_any_dtype(series):
            summary = _datetime_summary(series)
        else:
            parsed_dates = pd.to_datetime(series, errors="coerce", format="mixed")
            if parsed_dates.notna().mean() >= 0.8:
                summary = _datetime_summary(series)
                summary["inferred_type"] = "datetime"
            else:
                summary = _categorical_summary(series)

        sample_values = [_json_safe(value) for value in series.dropna().head(5).tolist()]
        columns.append(
            ColumnProfile(
                name=str(name),
                dtype=dtype,
                non_null_count=non_null,
                null_count=null_count,
                null_rate=round(null_rate, 4),
                unique_count=unique_count,
                sample_values=sample_values,
                summary=summary,
            )
        )

    return DatasetProfile(
        dataset_id=dataset_id,
        source_name=source_name,
        source_type=source_type,
        row_count=row_count,
        column_count=int(len(df.columns)),
        duplicate_rows=duplicate_rows,
        columns=columns,
        anomalies=anomalies,
    )
