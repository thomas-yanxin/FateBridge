"""Editorial notes stay visible and correctly attributed across three transports."""

import asyncio
import json
from pathlib import Path

import pytest

from fatebridge.application.examples import suggested_fields
from tests.test_bazi_source_comparison_transports import (
    SPEC,
    business,
    call_cli,
    native,
    reject_bad_fact,
    rest,
)

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-editorial-annotation-projection-v1"
CASES = json.loads((STUDY / "transport-case-selection-first.json").read_text())["cases"]
PLAN = json.loads((STUDY / "protocol-first.json").read_text())
PATCHES = {p["reference_id"]: p for p in PLAN["patches"]}


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_editorial_notes_and_original_failures_full_and_projected_on_all_surfaces(
    case, project, rest, tmp_path, capsys
):
    values = dict(
        zip(
            ("year_pillar", "month_pillar", "day_pillar", "hour_pillar"),
            case["pillars"],
        )
    )
    options, flags = {"response_char_limit": 0}, ["--response-char-limit", "0"]
    if project:
        fields = suggested_fields(SPEC, view="source_strength")
        options.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    response = rest.post(SPEC.rest_path, json=values, params=options)
    protocol = asyncio.run(native(SPEC, values, **options))
    code, cli = call_cli(SPEC, values, tmp_path, capsys, flags=flags)
    assert response.status_code == 200 and not protocol.is_error and code == 0
    results = [response.json(), protocol.structured_content, cli]
    for result in results:
        assert business(result) == business(results[0])
        SPEC.output_model.model_validate(result)
        comparison = result["source_comparison"]
        assert (
            comparison["reference_index"]["total_registered_editorial_annotations"]
            == 149
        )
        assert comparison["calculation_overridden"] is False
        for row in comparison["records"]:
            if row["reference_id"] not in PATCHES:
                continue
            patch = PATCHES[row["reference_id"]]
            assert (
                row["annotation_basis"]
                == row["retained_context"]
                == patch["source_record"]["annotation"]
            )
            assert (
                row["editorial_annotation_provenance"]
                == patch["after"]["editorial_annotation_provenance"]
            )
            assert (
                row["retained_strength_annotation"]
                == patch["before"]["retained_strength_annotation"]
            )
            assert (
                row["editorial_annotation_provenance"]["is_verbatim_original_text"]
                is False
            )
            assert PLAN["summary_note"] in result["summary"]
        if case["case_id"] == "known_original_disagreement":
            assert comparison["status"] == "known_annotation_mismatch"
            assert comparison["retained_expected_strengths"] == ["弱"]
            assert result["current_calculation"]["strength_level"] == "强"
        if case["case_id"] == "violated_bound":
            assert comparison["bounded_comparison"]["violated_count"] == 1
            assert (
                comparison["bounded_comparison"]["status"]
                == "violates_registered_bounds"
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("is_verbatim_original_text", True),
        ("strength_label_assigned_or_regraded", True),
        ("new_independent_validation_credit", 1),
    ],
)
def test_false_editorial_origin_or_grade_claims_rejected_before_projection(
    field, value, rest, monkeypatch, tmp_path, capsys
):
    fault = {
        "source_comparison": {
            "records": [{"editorial_annotation_provenance": {field: value}}]
        }
    }
    reject_bad_fact("bazi_source_compare", fault, rest, monkeypatch, tmp_path, capsys)
