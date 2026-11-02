"""The actual selected Dayou line is identical on REST, MCP and CLI."""

import asyncio
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.heluo_current_source_reference import HEADER_COUNT, PENDING_COUNT
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as shared_rest

rest = shared_rest
ROOT = Path(__file__).parent / "fixtures/heluo_dayou_v1"
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
        assert (selected["hexagram"], selected["line"]) == ("火天大有", case["line"])
        t = selected["text"]
        assert t["detail"] == "".join(s["text"] for s in expected["sections"])
        assert t["commentary_sections"] == [
            dict(s, applicability=None) for s in expected["sections"]
        ]
        assert t["text_provenance"]["commentary_pdf_pages"] == expected["pdf_pages"]
        assert t["commentary_branch_selection"]["selected_section_ids"] == []
        assert t["text_provenance"]["poem_status"] == "inherited_poem_source_unverified"
        if not texts_only:
            assert t["detail"] in out["snapshot_text"]
            summary = out["numerology_evidence"]["commentary_collation"]
            assert (
                summary["collated_line_commentaries"],
                summary["pending_line_commentaries"],
            ) == (HEADER_COUNT, PENDING_COUNT)


def test_selected_dayou3_snapshot_distinguishes_unnumbered_reference_and_actual_hou(
    rest,
):
    case = next(c for c in CASES if c["line"] == 3)
    response = rest.post(
        SPECS["heluo"].rest_path,
        json=case["payload"],
        params={"response_char_limit": 0},
    )
    assert response.status_code == 200
    out = response.json()
    assert out["chart"]["xian"]["name"] == "火天大有"
    assert out["chart"]["hou"]["name"] == "澤火革"
    assert "未指定目标爻" in out["snapshot_text"]
    assert "None爻" not in out["snapshot_text"]
    t = out["numerology_evidence"]["selected_texts"][0]["text"]
    assert t["commentary_cross_references"][0]["target_line"] is None
