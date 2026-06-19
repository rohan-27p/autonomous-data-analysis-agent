from __future__ import annotations

import json
import re
from typing import Any

from autodata_agent.core.errors import ValidationAppError


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract one JSON object from an LLM response."""

    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()

    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        if start == -1:
            raise ValidationAppError(
                "invalid_llm_json",
                "The model did not return a JSON object.",
                details={"response_preview": stripped[:500]},
            ) from None
        try:
            value, _ = json.JSONDecoder().raw_decode(stripped[start:])
        except json.JSONDecodeError as exc:
            raise ValidationAppError(
                "invalid_llm_json",
                "The model returned malformed JSON.",
                details={"response_preview": stripped[:500], "json_error": str(exc)},
            ) from exc

    if not isinstance(value, dict):
        raise ValidationAppError("invalid_llm_json", "The model response JSON must be an object.")
    return value
