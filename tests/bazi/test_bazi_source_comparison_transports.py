"""All public transports retain calculated/source disagreement before projection."""

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.services.tool_catalog import CATALOG
from tests.evaluation.test_agentic_nested_outputs import (
    test_nested_fact_faults_are_internal_failures_on_all_surfaces as reject_bad_fact,
)
from tests.support.transports import business, call_cli, native
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

SPEC = next(s for s in CATALOG if s.key == "bazi_source_compare")


rest = _shared_rest


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize(
    "pillars,expected",
    [
        (["庚午", "乙酉", "庚午", "壬午"], "known_annotation_mismatch"),
        (["己丑", "丙寅", "甲子", "戊辰"], "unadjudicated_records_only"),
        (["甲子", "丙寅", "甲子", "甲子"], "no_registered_literal_case"),
        (["己巳", "辛未", "丙午", "丁酉"], "agrees_with_known_annotations"),
        (["癸卯", "丙辰", "甲辰", "丙寅"], "agrees_with_known_annotations"),
        (["癸丑", "壬戌", "丙午", "庚寅"], "agrees_with_known_annotations"),
        (["癸酉", "甲子", "丁卯", "丙午"], "agrees_with_known_annotations"),
        (["甲子", "丙子", "甲申", "己巳"], "agrees_with_known_annotations"),
    ],
)
def test_same_literal_comparison_full_and_published_view_on_three_surfaces(
    project, pillars, expected, surface_calls
):
    values = dict(
        zip(["year_pillar", "month_pillar", "day_pillar", "hour_pillar"], pillars)
    )
    options = {"response_char_limit": 0}
    flags = ["--response-char-limit", "0"]
    if project:
        fields = suggested_fields(SPEC, view="source_strength")
        # Retain every published field and explicitly request the policy version.
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
        assert result["source_comparison"]["status"] == expected
        assert (
            result["current_calculation"]["method_id"]
            == "season_root_revelation_relations_v12"
        )
        assert result["source_comparison"]["calculation_overridden"] is False
        assert (
            result["source_comparison"]["full_original_text_conformance_certified"]
            is False
        )
        assert result["input_context"]["birth_datetime_reconstructed"] is False
        SPEC.output_model.model_validate(result)
        if expected == "known_annotation_mismatch":
            assert result["current_calculation"]["strength_level"] == "强"
            assert result["source_comparison"]["retained_expected_strengths"] == ["弱"]
            assert "未改写计算" in result["summary"]


@pytest.mark.parametrize(
    "fault",
    [
        {"source_comparison": {"calculation_overridden": True}},
        {"source_comparison": {"full_original_text_conformance_certified": True}},
        {"source_comparison": {"known_annotation_count": "private-wrong-value"}},
        {"source_comparison": {"records": [{"retained_strength_annotation": "满分"}]}},
        {"current_calculation": {"strength_level": "权威"}},
    ],
)
def test_invalid_professional_facts_cannot_be_hidden_by_projection(
    fault, rest, monkeypatch, tmp_path, capsys
):
    reject_bad_fact("bazi_source_compare", fault, rest, monkeypatch, tmp_path, capsys)
