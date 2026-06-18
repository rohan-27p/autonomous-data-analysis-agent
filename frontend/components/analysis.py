from __future__ import annotations

from typing import Any

import streamlit as st

from api_client import ApiError, AutodataApiClient

DEMO_QUESTIONS = [
    "Which product categories generated the highest total revenue?",
    "How did monthly revenue trend over time?",
    "Which customer segments have the weakest profit margins?",
    "Are there unusual outliers in order value?",
    "What are the top 5 regions by total sales?",
]


def _init_analysis_state() -> None:
    defaults = {
        "session_id": None,
        "last_analysis": None,
        "analysis_question": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _render_plan(plan: dict[str, Any]) -> None:
    st.markdown("**Analysis plan**")
    plan_cols = st.columns(3)
    plan_cols[0].metric("Operation", str(plan.get("operation", "—")).replace("_", " ").title())
    plan_cols[1].metric("Chart type", str(plan.get("chart_type", "—")).title())
    plan_cols[2].metric(
        "Required columns",
        len(plan.get("required_columns") or []),
    )
    st.write(plan.get("objective", ""))
    assumptions = plan.get("assumptions") or []
    if assumptions:
        st.caption("Assumptions: " + "; ".join(assumptions))


def _render_execution(execution: dict[str, Any]) -> None:
    attempts = execution.get("attempts", 1)
    if attempts > 1:
        st.info(f"Code was repaired and executed successfully after {attempts} attempts.")
    else:
        st.success("Analysis code executed successfully on the first attempt.")

    result_rows = execution.get("result_rows") or []
    if result_rows:
        st.markdown("**Result table**")
        st.dataframe(result_rows, use_container_width=True, hide_index=True)
    else:
        st.warning("Analysis completed but returned no result rows.")

    chart_spec = execution.get("chart_spec")
    if chart_spec:
        st.markdown("**Chart specification**")
        st.json(chart_spec)

    stdout = (execution.get("stdout") or "").strip()
    if stdout:
        with st.expander("Execution stdout"):
            st.code(stdout)


def _render_narrative(narrative: dict[str, Any]) -> None:
    st.markdown("**Key finding**")
    st.write(narrative.get("key_finding", ""))

    st.markdown("**Business meaning**")
    st.write(narrative.get("business_meaning", ""))

    limitations = narrative.get("limitations") or []
    if limitations:
        st.markdown("**Limitations**")
        for item in limitations:
            st.write(f"- {item}")

    follow_ups = narrative.get("follow_up_questions") or []
    if follow_ups:
        st.markdown("**Suggested follow-up questions**")
        for index, follow_up in enumerate(follow_ups):
            if st.button(follow_up, key=f"follow_up_{index}", use_container_width=True):
                st.session_state["analysis_question"] = follow_up
                st.rerun()


def _render_analysis_result(response: dict[str, Any]) -> None:
    st.markdown(f"**Question:** {response.get('question', '')}")
    _render_plan(response.get("plan") or {})

    with st.expander("Generated Python code", expanded=False):
        st.code(response.get("generated_code", ""), language="python")

    _render_execution(response.get("execution") or {})
    _render_narrative(response.get("narrative") or {})


def render_analysis(client: AutodataApiClient) -> None:
    _init_analysis_state()

    dataset_id = st.session_state.get("dataset_id")
    if not dataset_id:
        st.info("Upload a dataset first, then ask a business question.")
        return

    if st.session_state.get("session_id"):
        st.caption(f"Follow-up session active · `{st.session_state['session_id']}`")

    with st.expander("Example business questions", expanded=False):
        demo_cols = st.columns(2)
        for index, demo_question in enumerate(DEMO_QUESTIONS):
            column = demo_cols[index % 2]
            if column.button(demo_question, key=f"demo_question_{index}", use_container_width=True):
                st.session_state["analysis_question"] = demo_question
                st.rerun()

    question = st.text_area(
        "Business question",
        key="analysis_question",
        height=120,
        placeholder="Which product categories generated the highest total revenue?",
    )

    submit = st.button("Run analysis", type="primary", disabled=not question.strip())

    if submit:
        with st.spinner("Generating analysis code, executing it, and writing findings..."):
            try:
                response = client.analyze(
                    dataset_id,
                    question.strip(),
                    session_id=st.session_state.get("session_id"),
                )
            except ApiError as exc:
                st.error(f"Analysis failed: {exc.message} (`{exc.code}`)")
                if exc.details:
                    st.json(exc.details)
            else:
                st.session_state["session_id"] = response["session_id"]
                st.session_state["last_analysis"] = response
                st.success("Analysis completed.")
                st.rerun()

    last_analysis = st.session_state.get("last_analysis")
    if last_analysis:
        st.divider()
        st.markdown("### Latest analysis")
        _render_analysis_result(last_analysis)

        reset_cols = st.columns([1, 3])
        with reset_cols[0]:
            if st.button("Start new session", use_container_width=True):
                st.session_state["session_id"] = None
                st.session_state["last_analysis"] = None
                st.rerun()
