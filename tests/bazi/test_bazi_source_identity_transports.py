"""Printed identity corrections and false-credit guards survive all surfaces."""

import asyncio

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.services.tool_catalog import CATALOG
from tests.evaluation.test_agentic_nested_outputs import (
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest_fixture
from tests.evaluation.test_agentic_nested_outputs import (
    test_nested_fact_faults_are_internal_failures_on_all_surfaces as reject_bad_fact,
)

SPEC = next(s for s in CATALOG if s.key == "bazi_source_compare")
rest = shared_rest_fixture


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize(
    "pillars,printed_name,grade",
    [
        (["壬寅", "戊申", "壬辰", "壬寅"], "馬參政", "强"),
        (["己巳", "癸酉", "癸未", "庚申"], "茅狀元", "弱"),
        (["甲申", "壬申", "乙巳", "戊寅"], None, None),
        (["甲子", "丙寅", "甲子", "甲子"], None, None),
    ],
)
def test_exact_corrected_identity_and_retained_labels_on_three_surfaces(
    project, pillars, printed_name, grade, rest, tmp_path, capsys
):
    arguments = dict(
        zip(["year_pillar", "month_pillar", "day_pillar", "hour_pillar"], pillars)
    )
    options = {"response_char_limit": 0}
    flags = ["--response-char-limit", "0"]
    if project:
        fields = suggested_fields(SPEC, view="source_strength")
        options.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    response = rest.post(SPEC.rest_path, json=arguments, params=options)
    protocol = asyncio.run(native(SPEC, arguments, **options))
    code, cli = call_cli(SPEC, arguments, tmp_path, capsys, flags=flags)
    assert response.status_code == 200 and not protocol.is_error and code == 0
    results = [response.json(), protocol.structured_content, cli]
    for result in results:
        assert business(result) == business(results[0])
        SPEC.output_model.model_validate(result)
        comparison = result["source_comparison"]
        assert comparison["new_independent_validation_credit"] == 0
        assert (
            comparison["reference_index"]["method_id"]
            == "registered_literal_source_annotations_v1"
        )
        if printed_name:
            row = next(
                r
                for r in comparison["records"]
                if r.get("name_as_printed") == printed_name
            )
            assert (
                row["pillars"] == pillars
                and row["retained_strength_annotation"] == grade
            )
            assert (
                row["source_identity_revision"]["name_correction"][
                    "historical_person_identity_asserted"
                ]
                is False
            )
            assert comparison["status"] == "known_annotation_mismatch"
        if pillars[0] == "甲申":
            assert any(
                "上海世界图书馆发行" in r["source_reference"]["edition"]
                for r in comparison["records"]
            )
        if pillars[0] == "甲子":
            assert comparison["records"] == []


@pytest.mark.parametrize(
    "fault",
    [
        {"source_identity_revision": {"new_independent_validation_credit": 1}},
        {"source_identity_revision": {"new_independent_validation_credit": False}},
        {
            "source_identity_revision": {
                "source_strength_label_assigned_or_regraded": True
            }
        },
        {"source_identity_revision": {"source_strength_label_assigned_or_regraded": 0}},
        {"source_identity_revision": {"source_pdf_page": 73}},
        {"source_identity_revision": {"source_pdf_page": True}},
        {
            "source_identity_revision": {
                "name_correction": {"historical_person_identity_asserted": True}
            }
        },
        {
            "source_identity_revision": {
                "name_correction": {"historical_person_identity_asserted": 0}
            }
        },
        {"source_identity_revision": {"name_correction": {"name_as_printed": 123}}},
        {"source_identity_revision": {"name_correction": {"source_pdf_page": 72}}},
        {"name_as_printed": 123},
    ],
)
def test_false_identity_claims_and_coerced_types_fail_before_projection(
    fault, rest, monkeypatch, tmp_path, capsys
):
    reject_bad_fact(
        "bazi_source_compare",
        {"source_comparison": {"records": [fault]}},
        rest,
        monkeypatch,
        tmp_path,
        capsys,
    )
