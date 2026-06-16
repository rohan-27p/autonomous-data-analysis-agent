from __future__ import annotations

from typing import Protocol

import httpx

from autodata_agent.core.config import Settings
from autodata_agent.core.errors import ExternalServiceError


class LLMClient(Protocol):
    def chat_json(self, *, system: str, user: str) -> str:
        """Return model text that should contain a JSON object."""


class OllamaCloudClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def chat_json(self, *, system: str, user: str) -> str:
        api_key = self.settings.ollama_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise ExternalServiceError(
                "ollama_api_key_missing",
                "Ollama API key is not configured. Set AUTODATA_OLLAMA_API_KEY.",
                status_code=503,
            )

        url = self.settings.ollama_base_url.rstrip("/") + "/api/chat"
        payload = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": self.settings.ollama_num_predict,
            },
            "stream": False,
        }
        if self.settings.ollama_think.strip().lower() not in {"", "0", "false", "off", "none"}:
            payload["think"] = self.settings.ollama_think
        headers = {"Authorization": f"Bearer {api_key.get_secret_value()}"}
        try:
            response = httpx.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
        except httpx.HTTPStatusError as exc:
            ollama_error = _extract_ollama_error(exc.response)
            raise ExternalServiceError(
                "ollama_request_failed",
                ollama_error or "Ollama model request failed.",
                status_code=503,
                details={
                    "reason": str(exc),
                    "status_code": exc.response.status_code,
                    "response_body": exc.response.text[:1000],
                    "ollama_error": ollama_error,
                    "model": self.settings.ollama_model,
                    "url": url,
                },
            ) from exc
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ExternalServiceError(
                "ollama_request_failed",
                "Ollama model request failed.",
                status_code=503,
                details={
                    "reason": str(exc),
                    "model": self.settings.ollama_model,
                    "url": url,
                },
            ) from exc


def _extract_ollama_error(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    return error if isinstance(error, str) and error else None
