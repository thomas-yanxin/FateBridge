"""Expose whole-source additions and bounded violations on REST, MCP and CLI."""

import json
from pathlib import Path

import pytest

from fatebridge.application.examples import suggested_fields
from tests.bazi.test_bazi_source_comparison_transports import (
    SPEC,
    business,
    reject_bad_fact,
)
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = json.loads((ROOT / "tests/data/bazi/controller-source.json").read_text())
CASES = [
    *[(r["id"], r["pillars"]) for r in SOURCE["cases"]],
    ("SJ05", ["甲午", "丁丑", "甲午", "丙寅"]),
    ("GH07", ["甲申", "甲戌", "甲寅", "甲戌"]),
]


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("case_id,pillars", CASES, ids=[r[0] for r in CASES])
def test_complete_source_cases_and_constraints_on_all_surfaces(
    case_id, pillars, project, surface_calls
):
    payload = dict(
        zip(["year_pillar", "month_pillar", "day_pillar", "hour_pillar"], pillars)
    )
    options, flags = {"response_char_limit": 0}, ["--response-char-limit", "0"]
    if project:
        fields = suggested_fields(SPEC, view="source_strength")
        options.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    response, mcp, code, cli = surface_calls(
        SPEC, payload, params=options, options=options, flags=flags, cli_first=False
    )
    assert response.status_code == 200 and not mcp.is_error and code == 0
    results = [response.json(), mcp.structured_content, cli]
    for result in results:
        assert business(result) == business(results[0])
        SPEC.output_model.model_validate(result)
        comparison = result["source_comparison"]
        assert comparison["reference_index"]["total_registered_records"] == 367
        assert comparison["calculation_overridden"] is False
        assert (
            comparison["bounded_comparison"]["exact_strength_label_assigned"] is False
        )
        if case_id in {"SJ05", "DTCW1947-QQ-02"}:
            assert result["current_calculation"]["strength_level"] == "弱"
            assert comparison["status"] == "unadjudicated_records_only"
            bounds = comparison["bounded_comparison"]
            assert bounds["status"] == "violates_registered_bounds"
            assert bounds["claim_count"] == bounds["violated_count"] == 1
            claim = bounds["claims"][0]
            assert claim["forbidden_strengths"] == ["弱"]
            assert claim["source_reference"]["edition"]
            assert claim["source_reference"]["pdf_pages"]
            assert "集合约束被当前计算违反" in result["summary"]
        if case_id == "GH07":
            bounds = comparison["bounded_comparison"]
            assert bounds["claim_count"] == 1
            assert bounds["status"] == "satisfies_registered_bounds"
        if case_id == "DTCW1947-QQ-01":
            assert result["current_calculation"]["strength_level"] == "弱"
            assert comparison["status"] == "known_annotation_mismatch"
            assert comparison["retained_expected_strengths"] == ["强"]


@pytest.mark.parametrize(
    "fault",
    [
        {
            "source_comparison": {
                "bounded_comparison": {"exact_strength_label_assigned": True}
            }
        },
        {
            "source_comparison": {
                "bounded_comparison": {"claims": [{"forbidden_strengths": ["权威"]}]}
            }
        },
    ],
)
def test_invalid_bounded_facts_cannot_hide_behind_projection(
    fault, rest, monkeypatch, tmp_path, capsys
):
    reject_bad_fact("bazi_source_compare", fault, rest, monkeypatch, tmp_path, capsys)
