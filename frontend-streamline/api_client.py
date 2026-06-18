from __future__ import annotations

from typing import Any

import httpx


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | list[Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code


class AutodataApiClient:
    def __init__(self, base_url: str, *, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes]] | None = None,
    ) -> Any:
        response = httpx.request(
            method,
            self._url(path),
            json=json,
            params=params,
            files=files,
            timeout=self.timeout,
        )
        if response.is_error:
            self._raise_api_error(response)
        if not response.content:
            return {}
        return response.json()

    def _raise_api_error(self, response: httpx.Response) -> None:
        try:
            payload = response.json()
        except ValueError:
            raise ApiError(
                "api_error",
                response.text or "Backend request failed.",
                status_code=response.status_code,
            ) from None

        error = payload.get("error", {})
        raise ApiError(
            error.get("code", "api_error"),
            error.get("message", "Backend request failed."),
            details=error.get("details"),
            status_code=response.status_code,
        )

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def upload_dataset(self, filename: str, content: bytes) -> dict[str, Any]:
        return self._request(
            "POST",
            "/datasets/upload",
            files={"file": (filename, content)},
        )

    def ingest_sql(
        self,
        connection_uri: str,
        query: str,
        *,
        source_name: str = "sql_dataset",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/datasets/sql",
            json={
                "connection_uri": connection_uri,
                "query": query,
                "source_name": source_name,
            },
        )

    def get_profile(self, dataset_id: str) -> dict[str, Any]:
        return self._request("GET", f"/datasets/{dataset_id}/profile")

    def get_preview(self, dataset_id: str, *, limit: int = 20) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/preview",
            params={"limit": limit},
        )

    def analyze(
        self,
        dataset_id: str,
        question: str,
        *,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "dataset_id": dataset_id,
            "question": question,
        }
        if session_id:
            payload["session_id"] = session_id
        return self._request("POST", "/analysis", json=payload)

    def render_chart(
        self,
        chart_spec: dict[str, Any],
        result_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/charts/render",
            json={"chart_spec": chart_spec, "result_rows": result_rows},
        )

    def session_history(self, session_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/sessions/{session_id}/history")

    def export_session(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}/export")
