from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ChartType(StrEnum):
    BAR = "bar"
    LINE = "line"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    DISTRIBUTION = "distribution"
    TABLE = "table"


class DataSourceType(StrEnum):
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    SQL = "sql"


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    non_null_count: int
    null_count: int
    null_rate: float
    unique_count: int
    sample_values: list[Any] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class DatasetProfile(BaseModel):
    dataset_id: str
    source_name: str
    source_type: DataSourceType
    row_count: int
    column_count: int
    duplicate_rows: int
    columns: list[ColumnProfile]
    anomalies: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DatasetInfo(BaseModel):
    dataset_id: str
    source_name: str
    source_type: DataSourceType
    row_count: int
    column_count: int
    profile: DatasetProfile


class SQLIngestRequest(BaseModel):
    connection_uri: str = Field(..., description="SQLAlchemy connection URI.")
    query: str = Field(..., description="SELECT query to load into the analysis dataset.")
    source_name: str = "sql_dataset"


class AnalysisOperation(StrEnum):
    OVERVIEW = "overview"
    AGGREGATION = "aggregation"
    FILTERING = "filtering"
    GROUPING = "grouping"
    TREND = "trend_analysis"
    CORRELATION = "correlation"
    SEGMENTATION = "segmentation"
    DISTRIBUTION = "distribution"
    ANOMALY = "anomaly_detection"


class AnalysisPlan(BaseModel):
    operation: AnalysisOperation
    objective: str
    required_columns: list[str]
    assumptions: list[str] = Field(default_factory=list)
    chart_type: ChartType


class ChartSpec(BaseModel):
    chart_type: ChartType
    title: str
    x: str | None = None
    y: str | None = None
    color: str | None = None
    caption: str

    @field_validator("x", "y", "color", mode="before")
    @classmethod
    def normalize_optional_axis(cls, value: Any) -> Any:
        if value == [] or value == "":
            return None
        if isinstance(value, list):
            return str(value[0]) if value else None
        return value


class Narrative(BaseModel):
    key_finding: str
    business_meaning: str
    limitations: list[str]
    follow_up_questions: list[str]


class GeneratedAnalysisCode(BaseModel):
    plan: AnalysisPlan
    code: str = Field(..., description="Python code that creates result_df and chart_spec.")


class ExecutionResult(BaseModel):
    success: bool
    result_columns: list[str] = Field(default_factory=list)
    result_rows: list[dict[str, Any]] = Field(default_factory=list)
    chart_spec: ChartSpec | None = None
    stdout: str = ""
    error: str | None = None
    attempts: int = 1


class AnalysisRequest(BaseModel):
    dataset_id: str
    question: str
    session_id: str | None = None


class AnalysisResponse(BaseModel):
    session_id: str
    dataset_id: str
    question: str
    plan: AnalysisPlan
    generated_code: str
    execution: ExecutionResult
    narrative: Narrative
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SessionRecord(BaseModel):
    record_id: str
    session_id: str
    dataset_id: str
    question: str
    response: AnalysisResponse
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HealthStatus(BaseModel):
    status: Literal["ok"]
    environment: str
    model: str


class ErrorResponse(BaseModel):
    error: dict[str, Any]


class DatasetPreview(BaseModel):
    dataset_id: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    returned_rows: int

