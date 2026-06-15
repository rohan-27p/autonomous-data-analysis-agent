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

        url = self.settings.ollama_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "reasoning_effort": self.settings.ollama_reasoning_effort,
            "stream": False,
        }
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
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise ExternalServiceError(
                "ollama_request_failed",
                "Ollama model request failed.",
                status_code=503,
                details={"reason": str(exc), "model": self.settings.ollama_model},
            ) from exc

