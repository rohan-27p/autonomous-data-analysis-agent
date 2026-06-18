from __future__ import annotations

import httpx
import streamlit as st

from api_client import ApiError, AutodataApiClient
from components.analysis import render_analysis
from components.upload_profile import render_upload_profile

DEFAULT_API_URL = "http://127.0.0.1:8000"


@st.cache_resource
def get_api_client(base_url: str) -> AutodataApiClient:
    return AutodataApiClient(base_url)


def check_backend_health(client: AutodataApiClient) -> dict | None:
    try:
        st.session_state.pop("backend_error", None)
        return client.health()
    except ApiError as exc:
        st.session_state["backend_error"] = exc
        return None
    except httpx.HTTPError:
        st.session_state["backend_error"] = ApiError(
            "backend_unreachable",
            "Could not connect to the backend API.",
        )
        return None


st.set_page_config(
    page_title="Autonomous Data Analysis Agent",
    page_icon="📊",
    layout="wide",
)

st.title("Autonomous Data Analysis Agent")
st.caption("Upload data, ask business questions, and review analysis results.")

with st.sidebar:
    st.header("Backend")
    api_url = st.text_input(
        "API base URL",
        value=st.session_state.get("api_url", DEFAULT_API_URL),
        help="FastAPI server root, for example http://127.0.0.1:8000",
    )
    st.session_state["api_url"] = api_url.rstrip("/")
    client = get_api_client(st.session_state["api_url"])

    if st.button("Check backend health", use_container_width=True):
        st.session_state["backend_health"] = check_backend_health(client)

    if st.session_state.get("dataset_id"):
        st.divider()
        st.markdown("**Active dataset**")
        dataset_info = st.session_state.get("dataset_info") or {}
        st.caption(dataset_info.get("source_name", "Unknown source"))
        st.code(st.session_state["dataset_id"], language=None)

    if st.session_state.get("session_id"):
        st.divider()
        st.markdown("**Analysis session**")
        st.code(st.session_state["session_id"], language=None)

if "backend_health" not in st.session_state:
    st.session_state["backend_health"] = check_backend_health(client)

health = st.session_state.get("backend_health")
backend_error = st.session_state.get("backend_error")

if health:
    st.success(
        f"Backend connected · model: `{health['model']}` · environment: `{health['environment']}`"
    )
elif backend_error:
    st.error(f"Backend unavailable: {backend_error.message} (`{backend_error.code}`)")
else:
    st.warning("Backend not reachable. Start the API server and verify the sidebar URL.")

st.divider()

st.subheader("1. Upload & Profile")
render_upload_profile(client)

st.divider()

st.subheader("2. Ask Questions")
render_analysis(client)

st.divider()

st.subheader("3. Charts & History")
st.info("Chart rendering and session history UI will be added in the next commit.")
