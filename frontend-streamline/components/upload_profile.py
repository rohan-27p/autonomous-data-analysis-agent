from __future__ import annotations

from typing import Any

import streamlit as st
from api_client import ApiError, AutodataApiClient


def _format_column_summary(column: dict[str, Any]) -> str:
    summary = column.get("summary") or {}
    if top_values := summary.get("top_values"):
        return ", ".join(f"{item['value']} ({item['count']})" for item in top_values[:3])
    if "mean" in summary:
        return (
            f"min={summary.get('min')}, mean={summary.get('mean')}, "
            f"max={summary.get('max')}"
        )
    if "min" in summary and "max" in summary:
        return f"min={summary.get('min')}, max={summary.get('max')}"
    if sample_values := column.get("sample_values"):
        return ", ".join(str(value) for value in sample_values[:3])
    return "—"


def _store_dataset(result: dict[str, Any]) -> None:
    st.session_state["dataset_id"] = result["dataset_id"]
    st.session_state["dataset_info"] = result


def _render_profile_summary(profile: dict[str, Any]) -> None:
    metric_cols = st.columns(4)
    metric_cols[0].metric("Rows", profile["row_count"])
    metric_cols[1].metric("Columns", profile["column_count"])
    metric_cols[2].metric("Duplicate rows", profile["duplicate_rows"])
    metric_cols[3].metric("Source type", str(profile["source_type"]).upper())

    st.caption(
        f"Dataset `{profile['source_name']}` · ID `{profile['dataset_id']}`"
    )

    anomalies = profile.get("anomalies") or []
    if anomalies:
        st.markdown("**Anomaly hints**")
        for anomaly in anomalies:
            st.warning(anomaly, icon="⚠️")
    else:
        st.success("No anomaly hints detected in the automatic profile.")

    column_rows = [
        {
            "Column": column["name"],
            "Type": column["dtype"],
            "Null %": f"{column['null_rate'] * 100:.1f}%",
            "Unique": column["unique_count"],
            "Summary": _format_column_summary(column),
        }
        for column in profile.get("columns", [])
    ]
    st.markdown("**Column profile**")
    st.dataframe(column_rows, use_container_width=True, hide_index=True)


def _render_preview(client: AutodataApiClient, dataset_id: str) -> None:
    preview_limit = st.slider("Preview rows", min_value=5, max_value=50, value=20)
    try:
        preview = client.get_preview(dataset_id, limit=preview_limit)
    except ApiError as exc:
        st.error(f"Could not load preview: {exc.message} (`{exc.code}`)")
        return

    st.markdown("**Data preview**")
    st.dataframe(preview.get("rows", []), use_container_width=True, hide_index=True)
    st.caption(
        f"Showing {preview.get('returned_rows', 0)} of {preview.get('row_count', 0)} rows"
    )


def render_upload_profile(client: AutodataApiClient) -> None:
    if "dataset_id" not in st.session_state:
        st.session_state["dataset_id"] = None
    if "dataset_info" not in st.session_state:
        st.session_state["dataset_info"] = None

    uploaded_file = st.file_uploader(
        "Upload CSV, Excel, or JSON",
        type=["csv", "xlsx", "xls", "json"],
        help="Supported formats: CSV, Excel (.xlsx/.xls), and JSON.",
    )

    upload_cols = st.columns([1, 1])
    with upload_cols[0]:
        upload_clicked = st.button(
            "Upload and profile dataset",
            type="primary",
            disabled=uploaded_file is None,
            use_container_width=True,
        )
    with upload_cols[1]:
        clear_clicked = st.button("Clear dataset", use_container_width=True)

    if clear_clicked:
        st.session_state["dataset_id"] = None
        st.session_state["dataset_info"] = None
        st.rerun()

    if upload_clicked and uploaded_file is not None:
        with st.spinner("Uploading dataset and building profile..."):
            try:
                result = client.upload_dataset(uploaded_file.name, uploaded_file.getvalue())
            except ApiError as exc:
                st.error(f"Upload failed: {exc.message} (`{exc.code}`)")
            else:
                _store_dataset(result)
                st.success(f"Uploaded `{result['source_name']}` successfully.")
                st.rerun()

    with st.expander("Connect with SQL (SELECT only)", expanded=False):
        connection_uri = st.text_input(
            "Connection URI",
            placeholder="sqlite:///path/to/database.sqlite3",
        )
        query = st.text_area(
            "SELECT query",
            placeholder="SELECT * FROM orders LIMIT 1000",
            height=120,
        )
        source_name = st.text_input("Source name", value="sql_dataset")
        if st.button("Load SQL dataset", use_container_width=True):
            if not connection_uri.strip() or not query.strip():
                st.error("Connection URI and SELECT query are required.")
            else:
                with st.spinner("Loading SQL dataset and building profile..."):
                    try:
                        result = client.ingest_sql(
                            connection_uri.strip(),
                            query.strip(),
                            source_name=source_name.strip() or "sql_dataset",
                        )
                    except ApiError as exc:
                        st.error(f"SQL ingestion failed: {exc.message} (`{exc.code}`)")
                    else:
                        _store_dataset(result)
                        st.success(f"Loaded SQL dataset `{result['source_name']}`.")
                        st.rerun()

    dataset_info = st.session_state.get("dataset_info")
    if not dataset_info:
        st.info("Upload a dataset to view its automatic profile and preview.")
        return

    profile = dataset_info.get("profile") or {}
    _render_profile_summary(profile)
    _render_preview(client, dataset_info["dataset_id"])
