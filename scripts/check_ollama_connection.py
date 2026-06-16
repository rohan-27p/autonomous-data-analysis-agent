from __future__ import annotations

import json
from pathlib import Path

import httpx

from autodata_agent.core.config import Settings
from autodata_agent.core.errors import ExternalServiceError
from autodata_agent.services.llm import OllamaCloudClient


def load_env_file() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        import os

        os.environ[key.strip()] = value.strip()


def main() -> None:
    load_env_file()
    settings = Settings()
    api_key = settings.ollama_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        raise SystemExit("AUTODATA_OLLAMA_API_KEY is not set.")

    headers = {"Authorization": f"Bearer {api_key.get_secret_value()}"}
    tags_url = settings.ollama_base_url.rstrip("/") + "/api/tags"
    tags = httpx.get(tags_url, headers=headers, timeout=20)
    tags.raise_for_status()
    names = [item["name"] for item in tags.json().get("models", [])]
    print(f"Connected to {tags_url}")
    print(f"Visible model count: {len(names)}")
    print(f"Configured model: {settings.ollama_model}")
    print(f"Configured model visible: {settings.ollama_model in names}")

    try:
        content = OllamaCloudClient(settings).chat_json(
            system="Return only JSON.",
            user='Return {"status":"ok"} exactly as JSON.',
        )
    except ExternalServiceError as exc:
        print("Chat check failed:")
        print(
            json.dumps(
                {"code": exc.code, "message": exc.message, "details": exc.details},
                indent=2,
            )
        )
        raise SystemExit(1) from exc

    print("Chat check succeeded.")
    print(content[:500])


if __name__ == "__main__":
    main()
