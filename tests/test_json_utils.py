from __future__ import annotations

from autodata_agent.core.json_utils import extract_json_object


def test_extract_json_object_ignores_trailing_text():
    assert extract_json_object('prefix {"ok": true} trailing text') == {"ok": True}


def test_extract_json_object_uses_first_complete_object():
    assert extract_json_object('{"first": true}{"second": true}') == {"first": True}


def test_extract_json_object_handles_braces_inside_strings():
    assert extract_json_object('text {"code": "chart_spec = {}"} done') == {
        "code": "chart_spec = {}"
    }
