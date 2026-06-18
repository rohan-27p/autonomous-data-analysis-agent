from __future__ import annotations

import pytest

from autodata_agent.core.errors import ValidationAppError
from autodata_agent.core.schemas import ChartSpec, ChartType
from autodata_agent.services.charts import render_chart_figure


def test_render_bar_chart_returns_plotly_figure():
    chart_spec = ChartSpec(
        chart_type=ChartType.BAR,
        title="Sales by Category",
        x="category",
        y="sales",
        caption="Category A leads sales.",
    )
    rows = [
        {"category": "A", "sales": 150},
        {"category": "B", "sales": 75},
    ]

    figure = render_chart_figure(chart_spec, rows)

    assert figure["layout"]["title"]["text"] == "Sales by Category"
    assert figure["data"][0]["type"] == "bar"


def test_render_line_chart_returns_plotly_figure():
    chart_spec = ChartSpec(
        chart_type=ChartType.LINE,
        title="Revenue Trend",
        x="month",
        y="revenue",
        caption="Revenue increased over time.",
    )
    rows = [
        {"month": "Jan", "revenue": 100},
        {"month": "Feb", "revenue": 120},
    ]

    figure = render_chart_figure(chart_spec, rows)

    assert figure["data"][0]["type"] == "scatter"
    assert figure["data"][0]["mode"] == "lines"


def test_render_scatter_chart_returns_plotly_figure():
    chart_spec = ChartSpec(
        chart_type=ChartType.SCATTER,
        title="Price vs Units",
        x="price",
        y="units",
        caption="Higher prices correlate with lower units.",
    )
    rows = [
        {"price": 10, "units": 100},
        {"price": 20, "units": 80},
    ]

    figure = render_chart_figure(chart_spec, rows)

    assert figure["data"][0]["type"] == "scatter"
    assert figure["data"][0]["mode"] == "markers"


def test_render_distribution_chart_uses_numeric_column():
    chart_spec = ChartSpec(
        chart_type=ChartType.DISTRIBUTION,
        title="Sales Distribution",
        x="sales",
        y=None,
        caption="Sales are right-skewed.",
    )
    rows = [{"sales": 10}, {"sales": 20}, {"sales": 30}]

    figure = render_chart_figure(chart_spec, rows)

    assert figure["data"][0]["type"] == "histogram"


def test_render_heatmap_chart_pivots_values():
    chart_spec = ChartSpec(
        chart_type=ChartType.HEATMAP,
        title="Revenue Heatmap",
        x="region",
        y="category",
        color="revenue",
        caption="West region leads electronics revenue.",
    )
    rows = [
        {"region": "West", "category": "Electronics", "revenue": 100},
        {"region": "East", "category": "Electronics", "revenue": 80},
        {"region": "West", "category": "Apparel", "revenue": 60},
        {"region": "East", "category": "Apparel", "revenue": 40},
    ]

    figure = render_chart_figure(chart_spec, rows)

    assert figure["data"][0]["type"] == "heatmap"


def test_render_table_chart_returns_table_trace():
    chart_spec = ChartSpec(
        chart_type=ChartType.TABLE,
        title="Top Rows",
        x=None,
        y=None,
        caption="Preview of result rows.",
    )
    rows = [
        {"category": "A", "sales": 100},
        {"category": "B", "sales": 50},
    ]

    figure = render_chart_figure(chart_spec, rows)

    assert figure["data"][0]["type"] == "table"


def test_render_chart_rejects_empty_rows():
    chart_spec = ChartSpec(
        chart_type=ChartType.BAR,
        title="Empty",
        x="category",
        y="sales",
        caption="No data.",
    )

    with pytest.raises(ValidationAppError) as exc:
        render_chart_figure(chart_spec, [])

    assert exc.value.code == "empty_chart_data"


def test_render_chart_rejects_missing_columns():
    chart_spec = ChartSpec(
        chart_type=ChartType.BAR,
        title="Missing Columns",
        x="category",
        y="sales",
        caption="Invalid chart data.",
    )

    with pytest.raises(ValidationAppError) as exc:
        render_chart_figure(chart_spec, [{"category": "A"}])

    assert exc.value.code == "chart_columns_missing"
