"""Actual parent conditions and references survive full and selected-only delivery."""

import asyncio
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.support.heluo_source_facts import HEADER_COUNT, PENDING_COUNT
from tests.support.transports import SPECS, business, call_cli, native
from tests.support.transports import rest as shared_rest

rest = shared_rest
FIXTURE = Path(__file__).parents[1] / "fixtures/heluo_taipi_v1"
CASES = json.loads((FIXTURE / "cases.json").read_bytes())["cases"]
REFERENCES = json.loads((FIXTURE / "verified-readings.json").read_bytes())[
    "conditional_references"
]
KEYS = {
    ("地天泰", 2),
    ("地天泰", 4),
    ("地天泰", 5),
    ("天地否", 4),
    ("天地否", 5),
    ("天地否", 6),
}


@pytest.fixture(autouse=True)
def native_source_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize("texts_only", [False, True])
@pytest.mark.parametrize(
    "case",
    [c for c in CASES if (c["hexagram"], c["line"]) in KEYS],
    ids=lambda c: c["hexagram"] + str(c["line"]),
)
def test_parent_section_is_identical_on_three_transports(
    case, texts_only, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    fields = ["numerology_evidence.selected_texts"]
    if not texts_only:
        fields += [
            "chart",
            "numerology_evidence.commentary_collation",
            "numerology_evidence.yaoci_collation",
            "snapshot_text",
        ]
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("response_char_limit", "0"),
    ]
    response = rest.post(spec.rest_path, json=case["payload"], params=params)
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
    for output in outputs:
        spec.output_model.model_validate(output)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        e = output["numerology_evidence"]
        s = e["selected_texts"][case["phase"]]
        assert (s["hexagram"], s["line"]) == (case["hexagram"], case["line"])
        t = s["text"]
        assert all(
            section["applicability"] is None for section in t["commentary_sections"]
        )
        assert t["commentary_branch_selection"]["selected_section_ids"] == []
        expected = [
            r
            for r in REFERENCES
            if (r["source_hexagram"], r["source_line"])
            == (case["hexagram"], case["line"])
        ]
        assert t.get("commentary_cross_references", []) == expected
        if not texts_only:
            assert (
                e["commentary_collation"]["collated_line_commentaries"],
                e["commentary_collation"]["pending_line_commentaries"],
            ) == (HEADER_COUNT, PENDING_COUNT)
            assert e["yaoci_collation"]["collated_line_headers"] == HEADER_COUNT
            for ref in expected:
                assert ref["source_condition_label"] in output["snapshot_text"]
                assert "适用未定，不替代后天卦" in output["snapshot_text"]
                assert "小畜初引巽初" not in output["snapshot_text"]
