from __future__ import annotations

import json
from typing import Any

import plotly.graph_objects as go
import streamlit as st
from api_client import ApiError, AutodataApiClient


def _render_chart(client: AutodataApiClient, analysis: dict[str, Any]) -> None:
    execution = analysis.get("execution") or {}
    chart_spec = execution.get("chart_spec")
    result_rows = execution.get("result_rows") or []

    if not chart_spec:
        st.warning("This analysis did not return a chart specification.")
        return
    if not result_rows:
        st.warning("This analysis did not return rows to chart.")
        return

    try:
        rendered = client.render_chart(chart_spec, result_rows)
    except ApiError as exc:
        st.error(f"Chart rendering failed: {exc.message} (`{exc.code}`)")
        if exc.details:
            st.json(exc.details)
        return

    figure = go.Figure(rendered["figure"])
    st.plotly_chart(figure, use_container_width=True)
    st.caption(rendered.get("caption") or chart_spec.get("caption", ""))


def _load_session_history(client: AutodataApiClient, session_id: str) -> list[dict[str, Any]]:
    try:
        return client.session_history(session_id)
    except ApiError as exc:
        st.error(f"Could not load session history: {exc.message} (`{exc.code}`)")
        return []


def _render_export_button(client: AutodataApiClient, session_id: str) -> None:
    try:
        report = client.export_session(session_id)
    except ApiError as exc:
        st.error(f"Could not build export: {exc.message} (`{exc.code}`)")
        return

    st.download_button(
        "Download report",
        data=json.dumps(report, indent=2),
        file_name=f"analysis-report-{session_id[:8]}.json",
        mime="application/json",
        use_container_width=True,
    )


def _render_history_item(record: dict[str, Any], index: int) -> None:
    response = record.get("response") or {}
    narrative = response.get("narrative") or {}
    plan = response.get("plan") or {}
    question = record.get("question", "Untitled question")
    created_at = record.get("created_at", "")

    with st.container(border=True):
        st.markdown(f"**Q{index + 1}. {question}**")
        if created_at:
            st.caption(created_at)
        st.write(narrative.get("key_finding", ""))
        st.caption(
            f"Operation: {str(plan.get('operation', '—')).replace('_', ' ')} · "
            f"Chart: {plan.get('chart_type', '—')}"
        )

        action_cols = st.columns(2)
        with action_cols[0]:
            if st.button(
                "View chart",
                key=f"view_chart_{record['record_id']}",
                use_container_width=True,
            ):
                st.session_state["selected_analysis"] = response
                st.rerun()
        with action_cols[1]:
            if st.button(
                "Reuse question",
                key=f"reuse_question_{record['record_id']}",
                use_container_width=True,
            ):
                st.session_state["analysis_question"] = question
                st.rerun()


def render_charts_history(client: AutodataApiClient) -> None:
    st.session_state.setdefault("selected_analysis", None)

    session_id = st.session_state.get("session_id")
    last_analysis = st.session_state.get("last_analysis")

    if not session_id and not last_analysis:
        st.info("Run an analysis to view charts and session history.")
        return

    if last_analysis and st.session_state.get("selected_analysis") is None:
        st.session_state["selected_analysis"] = last_analysis

    chart_col, history_col = st.columns([3, 2])

    with chart_col:
        st.markdown("### Chart")
        selected_analysis = st.session_state.get("selected_analysis") or last_analysis
        if selected_analysis:
            st.caption(selected_analysis.get("question", ""))
            _render_chart(client, selected_analysis)
        else:
            st.info("Select an analysis from session history to view its chart.")

    with history_col:
        st.markdown("### Session history")
        if not session_id:
            st.info("No active session yet.")
            return

        history_actions = st.columns(2)
        with history_actions[0]:
            if st.button("Refresh history", use_container_width=True):
                st.session_state.pop("session_history_cache", None)
                st.rerun()
        with history_actions[1]:
            _render_export_button(client, session_id)

        cache_key = f"session_history_cache::{session_id}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = _load_session_history(client, session_id)

        history = st.session_state.get(cache_key) or []
        if not history:
            st.info("No prior questions in this session yet.")
            return

        st.caption(f"{len(history)} question(s) in this session")
        for index, record in enumerate(history):
            _render_history_item(record, index)
