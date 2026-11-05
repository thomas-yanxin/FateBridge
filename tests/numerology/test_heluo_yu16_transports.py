"""The actual selected Yu16 line is identical on REST, MCP and CLI."""

import asyncio
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest
from tests.support.heluo_source_facts import HEADER_COUNT, PENDING_COUNT

rest = shared_rest
ROOT = Path(__file__).parents[1] / "fixtures/heluo_yu16_v1"
CASES = json.loads((ROOT / "cases.json").read_bytes())["cases"]
READINGS = json.loads((ROOT / "verified-readings.json").read_bytes())["entries"]


@pytest.fixture(autouse=True)
def native_source_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize("texts_only", [False, True])
@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["line"]))
def test_actual_source_line_and_complete_conditions_on_all_adapters(
    case, texts_only, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    fields = ["numerology_evidence.selected_texts"]
    if not texts_only:
        fields += ["chart", "numerology_evidence.commentary_collation", "snapshot_text"]
    response = rest.post(
        spec.rest_path,
        json=case["payload"],
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("response_char_limit", "0")],
    )
    code, cli = call_cli(
        spec,
        case["payload"],
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    mcp = asyncio.run(
        native(
            spec,
            {
                **case["payload"],
                "fields": fields,
                "strict_fields": True,
                "response_char_limit": 0,
            },
        )
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    expected = next(e for e in READINGS if e["line"] == case["line"])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        selected = out["numerology_evidence"]["selected_texts"][case["phase"]]
        assert (selected["hexagram"], selected["line"]) == ("雷地豫", case["line"])
        t = selected["text"]
        assert t["detail"] == "".join(s["text"] for s in expected["sections"])
        assert t["commentary_sections"] == [
            dict(s, applicability=None) for s in expected["sections"]
        ]
        assert t["text_provenance"]["commentary_pdf_pages"] == expected["pdf_pages"]
        header = next(
            e
            for e in json.loads((ROOT / "verified-readings.json").read_bytes())[
                "headers"
            ]
            if e["line"] == case["line"]
        )
        assert t["text_provenance"]["review_status"] == header["review_status"]
        assert t["text_provenance"]["header_reading_notes"] == header["reading_notes"]
        assert t["commentary_branch_selection"]["selected_section_ids"] == []
        assert t["text_provenance"]["poem_status"] == "inherited_poem_source_unverified"
        if not texts_only:
            assert t["detail"] in out["snapshot_text"]
            if case["line"] == 4:
                assert "爻辞仍有字形未决" in out["snapshot_text"]
            if case["line"] == 2:
                assert "字形未决" in out["snapshot_text"]
            summary = out["numerology_evidence"]["commentary_collation"]
            assert (
                summary["collated_line_commentaries"],
                summary["pending_line_commentaries"],
            ) == (HEADER_COUNT, PENDING_COUNT)
