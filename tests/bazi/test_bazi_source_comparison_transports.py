"""All public transports retain calculated/source disagreement before projection."""

import json
from pathlib import Path

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.services.tool_catalog import CATALOG
from tests.evaluation.test_agentic_nested_outputs import (
    test_nested_fact_faults_are_internal_failures_on_all_surfaces as reject_bad_fact,
)
from tests.support.transports import business
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

SPEC = next(s for s in CATALOG if s.key == "bazi_source_compare")
SOURCE_UNITS = json.loads(
    (Path(__file__).parents[1] / "data/bazi/complete-units-source.json").read_text()
)["cases"]
CONTROLLER_CASES = json.loads(
    (Path(__file__).parents[1] / "data/bazi/controller-source.json").read_text()
)["cases"]


rest = _shared_rest


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize(
    "case_id,pillars,expected",
    [
        (None, ["庚午", "乙酉", "庚午", "壬午"], "known_annotation_mismatch"),
        (None, ["己丑", "丙寅", "甲子", "戊辰"], "unadjudicated_records_only"),
        (None, ["甲子", "丙寅", "甲子", "甲子"], "no_registered_literal_case"),
        (None, ["己巳", "辛未", "丙午", "丁酉"], "agrees_with_known_annotations"),
        (None, ["癸卯", "丙辰", "甲辰", "丙寅"], "agrees_with_known_annotations"),
        (None, ["癸丑", "壬戌", "丙午", "庚寅"], "agrees_with_known_annotations"),
        (None, ["癸酉", "甲子", "丁卯", "丙午"], "agrees_with_known_annotations"),
        (None, ["甲子", "丙子", "甲申", "己巳"], "agrees_with_known_annotations"),
        *[
            (
                None,
                row["pillars"],
                (
                    "unadjudicated_records_only"
                    if row["expected_strength"] is None
                    else "agrees_with_known_annotations"
                ),
            )
            for row in SOURCE_UNITS
        ],
        *[(row["id"], row["pillars"], None) for row in CONTROLLER_CASES],
        ("SJ05", ["甲午", "丁丑", "甲午", "丙寅"], None),
        ("GH07", ["甲申", "甲戌", "甲寅", "甲戌"], None),
    ],
)
def test_same_literal_comparison_full_and_published_view_on_three_surfaces(
    project, case_id, pillars, expected, surface_calls
):
    values = dict(
        zip(["year_pillar", "month_pillar", "day_pillar", "hour_pillar"], pillars)
    )
    options = {"response_char_limit": 0}
    flags = ["--response-char-limit", "0"]
    if project:
        fields = suggested_fields(SPEC, view="source_strength")
        if case_id is None:
            fields = [*fields, "current_calculation.method_id"]
        options.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    response, protocol, code, cli = surface_calls(
        SPEC, values, params=options, options=options, flags=flags, cli_first=False
    )
    assert (
        response.status_code == 200 and not protocol.is_error and code == 0
    ), response.text
    results = [response.json(), protocol.structured_content, cli]
    for result in results:
        assert business(result) == business(results[0])
        comparison = result["source_comparison"]
        if expected is not None:
            assert comparison["status"] == expected
            assert (
                result["current_calculation"]["method_id"]
                == "season_root_revelation_relations_v12"
            )
            assert comparison["full_original_text_conformance_certified"] is False
            assert result["input_context"]["birth_datetime_reconstructed"] is False
        assert result["source_comparison"]["calculation_overridden"] is False
        SPEC.output_model.model_validate(result)
        if expected == "known_annotation_mismatch":
            assert result["current_calculation"]["strength_level"] == "强"
            assert result["source_comparison"]["retained_expected_strengths"] == ["弱"]
            assert "未改写计算" in result["summary"]
        if case_id is not None:
            assert comparison["reference_index"]["total_registered_records"] == 367
            bounds = comparison["bounded_comparison"]
            assert bounds["exact_strength_label_assigned"] is False
            if case_id in {"SJ05", "DTCW1947-QQ-02"}:
                assert result["current_calculation"]["strength_level"] == "弱"
                assert comparison["status"] == "unadjudicated_records_only"
                assert bounds["status"] == "violates_registered_bounds"
                assert bounds["claim_count"] == bounds["violated_count"] == 1
                claim = bounds["claims"][0]
                assert claim["forbidden_strengths"] == ["弱"]
                assert claim["source_reference"]["edition"]
                assert claim["source_reference"]["pdf_pages"]
                assert "集合约束被当前计算违反" in result["summary"]
            if case_id == "GH07":
                assert bounds["claim_count"] == 1
                assert bounds["status"] == "satisfies_registered_bounds"
            if case_id == "DTCW1947-QQ-01":
                assert result["current_calculation"]["strength_level"] == "弱"
                assert comparison["status"] == "known_annotation_mismatch"
                assert comparison["retained_expected_strengths"] == ["强"]


@pytest.mark.parametrize(
    "fault",
    [
        {"source_comparison": {"calculation_overridden": True}},
        {"source_comparison": {"full_original_text_conformance_certified": True}},
        {"source_comparison": {"known_annotation_count": "private-wrong-value"}},
        {"source_comparison": {"records": [{"retained_strength_annotation": "满分"}]}},
        {"current_calculation": {"strength_level": "权威"}},
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
def test_invalid_professional_facts_cannot_be_hidden_by_projection(
    fault, rest, monkeypatch, tmp_path, capsys
):
    reject_bad_fact("bazi_source_compare", fault, rest, monkeypatch, tmp_path, capsys)
