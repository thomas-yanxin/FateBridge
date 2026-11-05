"""Real source facts survive projection; contradictory claims fail before it."""

import asyncio
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

import fatebridge.application.execution as execution
from fatebridge.application.examples import suggested_fields
from fatebridge.services.source_comparison import calculate_bazi_source_compare
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as shared_rest_fixture

rest = shared_rest_fixture
ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads(
    (ROOT / "src/fatebridge/data/reference/bazi-source-conditions.json").read_text()
)
SPEC = SPECS["bazi_source_compare"]


def arguments(row):
    return dict(
        zip(
            ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"],
            row["review"]["pillars"],
        )
    )


@pytest.mark.parametrize("row", PLAN["reviews"], ids=lambda r: r["review"]["case_id"])
def test_all19_real_conditions_and_old_annotations_agree_across_surfaces(
    row, rest, tmp_path, capsys
):
    args = arguments(row)
    fields = suggested_fields(SPEC, view="source_conditions")
    flags = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    response = rest.post(SPEC.rest_path, json=args, params=flags)
    protocol = asyncio.run(native(SPEC, args, **flags))
    code, cli = call_cli(
        SPEC,
        args,
        tmp_path,
        capsys,
        [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and not protocol.is_error and code == 0
    values = [response.json(), protocol.structured_content, cli]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        SPEC.output_model.model_validate(value)
        for record in value["source_comparison"]["records"]:
            if record["reference_id"] in {ref for ref in row["reference_ids"]}:
                assert (
                    record["source_condition_review"]["review_id"]
                    == row["review"]["review_id"]
                )


@pytest.mark.parametrize(
    "fault", ["day", "force", "excerpt", "page", "record", "numeric_bool"]
)
def test_contradictory_registered_conditions_cannot_hide_behind_unrelated_projection(
    fault, rest, monkeypatch, tmp_path, capsys
):
    row = PLAN["reviews"][-1]
    args = arguments(row)
    payload = calculate_bazi_source_compare(*row["review"]["pillars"])
    record = next(
        r for r in payload["source_comparison"]["records"] if r["case_id"] == "ML-02"
    )
    review = record["source_condition_review"]
    if fault == "day":
        review["relative_timing_statements"][0]["source_elapsed_days"] = 7
    elif fault == "force":
        review["effective_force_adjudication"] = "strong"
    elif fault == "excerpt":
        review["reading_excerpt"] = "made up"
    elif fault == "page":
        review["source_page_anchors"][0]["pdf_page"] = 171
    elif fault == "record":
        record["reference_id"] = "original:ZP37-LIANG"
    else:
        review["relative_timing_statements"][0]["calendar_instant_reconstructed"] = 0
    original = execution.execute_spec

    def broken(spec, request):
        if spec.key == SPEC.key:
            spec = replace(spec, bind=lambda _: (lambda: deepcopy(payload), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    fields = ["current_calculation.strength_level"]
    response = rest.post(
        SPEC.rest_path, json=args, params={"fields": fields, "strict_fields": True}
    )
    protocol = asyncio.run(native(SPEC, args, fields=fields, strict_fields=True))
    code, cli = call_cli(
        SPEC, args, tmp_path, capsys, ["--fields", *fields, "--strict-fields", "true"]
    )
    for name, value in [
        ("rest", response.json()),
        ("mcp", protocol.structured_content),
        ("cli", cli),
    ]:
        (tmp_path / (name + "-actual-response.json")).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        )
    assert response.status_code == 500 and protocol.is_error and code == 1
    assert (
        response.json()["error_code"]
        == protocol.structured_content["error_code"]
        == cli["error_code"]
        == "internal_error"
    )
