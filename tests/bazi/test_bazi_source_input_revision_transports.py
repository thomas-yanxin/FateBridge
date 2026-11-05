"""All transports retain revised inputs, raw provenance and unadjudicated labels."""

import asyncio
import json
from pathlib import Path

import pytest

from fatebridge.application.examples import suggested_fields
from tests.bazi.test_bazi_source_comparison_transports import (
    SPEC,
    business,
    call_cli,
    native,
    reject_bad_fact,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[2]
RECORDS = [
    r
    for r in json.loads(
        (
            ROOT / "src/fatebridge/data/reference/bazi-source-annotations.json"
        ).read_text()
    )["records"]
    if "input_reading_evidence" in r
]


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("patch", RECORDS, ids=[p["reference_id"] for p in RECORDS])
def test_all_six_revised_records_and_provenance_on_all_surfaces(
    patch, project, rest, tmp_path, capsys
):
    values = dict(
        zip(
            ("year_pillar", "month_pillar", "day_pillar", "hour_pillar"),
            patch["pillars"],
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
        comp = result["source_comparison"]
        assert comp["status"] == "unadjudicated_records_only"
        record = next(
            r for r in comp["records"] if r["reference_id"] == patch["reference_id"]
        )
        assert {k: v for k, v in record.items() if k != "comparison"} == patch
        assert record["comparison"] == "unadjudicated"
        assert (
            record["input_reading_evidence"]["source_strength_label_assigned"] is False
        )
        assert comp["calculation_overridden"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_strength_label_assigned", True),
        ("independent_edition_or_expert_review", True),
        ("new_independent_validation_credit", 1),
    ],
)
def test_invalid_revision_claims_rejected_before_projection(
    field, value, rest, monkeypatch, tmp_path, capsys
):
    fault = {
        "source_comparison": {"records": [{"input_reading_evidence": {field: value}}]}
    }
    reject_bad_fact("bazi_source_compare", fault, rest, monkeypatch, tmp_path, capsys)
