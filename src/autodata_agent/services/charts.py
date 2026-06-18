from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from autodata_agent.core.errors import ValidationAppError
from autodata_agent.core.schemas import ChartSpec, ChartType


def render_chart_figure(chart_spec: ChartSpec, result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not result_rows:
        raise ValidationAppError(
            "empty_chart_data",
            "Cannot render a chart without result rows.",
        )

    df = pd.DataFrame(result_rows)
    chart_type = chart_spec.chart_type

    if chart_type == ChartType.TABLE:
        figure = _table_figure(df, chart_spec)
    elif chart_type == ChartType.BAR:
        figure = _bar_figure(df, chart_spec)
    elif chart_type == ChartType.LINE:
        figure = _line_figure(df, chart_spec)
    elif chart_type == ChartType.SCATTER:
        figure = _scatter_figure(df, chart_spec)
    elif chart_type == ChartType.HEATMAP:
        figure = _heatmap_figure(df, chart_spec)
    elif chart_type == ChartType.DISTRIBUTION:
        figure = _distribution_figure(df, chart_spec)
    else:
        raise ValidationAppError(
            "unsupported_chart_type",
            f"Chart type '{chart_type}' is not supported for rendering.",
        )

    figure.update_layout(
        title=chart_spec.title,
        margin={"l": 40, "r": 40, "t": 60, "b": 40},
    )
    if chart_type != ChartType.TABLE:
        figure.update_layout(
            xaxis_title=chart_spec.x,
            yaxis_title=chart_spec.y,
        )

    payload = figure.to_plotly_json()
    if isinstance(payload, dict):
        return payload
    return dict(payload)


def _require_columns(
    df: pd.DataFrame,
    columns: list[str | None],
    *,
    chart_type: str,
) -> None:
    required = [column for column in columns if column]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValidationAppError(
            "chart_columns_missing",
            f"Result data is missing columns required for {chart_type} chart rendering.",
            details={"missing_columns": missing, "available_columns": list(df.columns)},
        )


def _value_column(df: pd.DataFrame, chart_spec: ChartSpec, exclude: set[str]) -> str:
    if chart_spec.color and chart_spec.color in df.columns and chart_spec.color not in exclude:
        return chart_spec.color
    for column in df.columns:
        if column in exclude:
            continue
        if pd.api.types.is_numeric_dtype(df[column]):
            return str(column)
    raise ValidationAppError(
        "chart_value_column_missing",
        "Could not determine a numeric value column for chart rendering.",
        details={"available_columns": list(df.columns)},
    )


def _distribution_column(df: pd.DataFrame, chart_spec: ChartSpec) -> str:
    for column in (chart_spec.x, chart_spec.y):
        if column and column in df.columns:
            return column
    for column in df.columns:
        if pd.api.types.is_numeric_dtype(df[column]):
            return str(column)
    raise ValidationAppError(
        "chart_distribution_column_missing",
        "Could not determine a column for distribution chart rendering.",
        details={"available_columns": list(df.columns)},
    )


def _bar_figure(df: pd.DataFrame, chart_spec: ChartSpec) -> go.Figure:
    _require_columns(df, [chart_spec.x, chart_spec.y], chart_type="bar")
    color = chart_spec.color if chart_spec.color and chart_spec.color in df.columns else None
    return px.bar(df, x=chart_spec.x, y=chart_spec.y, color=color)


def _line_figure(df: pd.DataFrame, chart_spec: ChartSpec) -> go.Figure:
    _require_columns(df, [chart_spec.x, chart_spec.y], chart_type="line")
    color = chart_spec.color if chart_spec.color and chart_spec.color in df.columns else None
    return px.line(df, x=chart_spec.x, y=chart_spec.y, color=color)


def _scatter_figure(df: pd.DataFrame, chart_spec: ChartSpec) -> go.Figure:
    _require_columns(df, [chart_spec.x, chart_spec.y], chart_type="scatter")
    color = chart_spec.color if chart_spec.color and chart_spec.color in df.columns else None
    return px.scatter(df, x=chart_spec.x, y=chart_spec.y, color=color)


def _distribution_figure(df: pd.DataFrame, chart_spec: ChartSpec) -> go.Figure:
    column = _distribution_column(df, chart_spec)
    return px.histogram(df, x=column)


def _heatmap_figure(df: pd.DataFrame, chart_spec: ChartSpec) -> go.Figure:
    _require_columns(df, [chart_spec.x, chart_spec.y], chart_type="heatmap")
    value_column = _value_column(
        df,
        chart_spec,
        exclude={chart_spec.x or "", chart_spec.y or ""},
    )
    pivot = df.pivot_table(
        index=chart_spec.x,
        columns=chart_spec.y,
        values=value_column,
        aggfunc="mean",
    )
    return px.imshow(
        pivot,
        labels={"x": chart_spec.y, "y": chart_spec.x, "color": value_column},
        aspect="auto",
    )


def _table_figure(df: pd.DataFrame, chart_spec: ChartSpec) -> go.Figure:
    return go.Figure(
        data=[
            go.Table(
                header=dict(values=[str(column) for column in df.columns]),
                cells=dict(values=[df[column].tolist() for column in df.columns]),
            )
        ]
    )
