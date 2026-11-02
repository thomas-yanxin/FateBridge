"""Exact boundary arithmetic must not fit labels or widen a tolerance band."""

import asyncio
import copy
import gzip
import hashlib
import importlib.util
import json
import math
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_strength_thresholds import StrengthThresholdArithmetic
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate
from fatebridge.core.strength_thresholds import threshold_snapshot_lines
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as _rest_fixture

rest = _rest_fixture
FIXTURE = Path(__file__).parent / "fixtures/bazi_strength_threshold_v1"
spec = importlib.util.spec_from_file_location(
    "threshold_independent_reference", FIXTURE / "independent_reference_v2.py"
)
assert spec is not None and spec.loader is not None
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
NEAR = [
    r
    for line in gzip.decompress(
        (FIXTURE / "baseline-first-objects.jsonl.gz").read_bytes()
    ).splitlines()
    if (r := json.loads(line))["event"] == "near_threshold_first_return"
]
KEYS = ["analyze_destiny", "bazi_birth"] + [
    "bazi_" + x
    for x in (
        "career",
        "wealth",
        "health",
        "children",
        "education",
        "personality",
        "relatives",
        "marriage",
        "romance",
    )
]


def delivered_payload(value):
    """Read the same response's retained payload, without another calculation."""
    delivery = value.get("result_delivery")
    if not delivery:
        return value
    wrapper = json.loads(Path(delivery["file_path"]).read_bytes())
    payload = wrapper[delivery["file_payload_path"]]
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    assert hashlib.sha256(raw).hexdigest() == delivery["sha256"]
    if value.get("run_metadata", {}).get("run_id"):
        assert payload["run_metadata"]["run_id"] == value["run_metadata"]["run_id"]
    return payload


def evaluate(values, policy=DEFAULT_POLICY, mode="precise_binding_only_v1"):
    return _evaluate(
        dict(zip(("year", "month", "day", "hour"), map(tuple, values))),
        ElementAnalysis.seasonal_phases(values[1][1]),
        policy,
        stem_effect_mode=mode,
    )


@pytest.mark.parametrize("row", NEAR, ids=lambda r: str(r["index"]))
def test_every_first_boundary_object_matches_independent_rational_arithmetic(row):
    before = row["result"]
    expected = reference.reconstruct(row["pillars"], before["relations"])
    after = evaluate(row["pillars"])
    receipt = after["threshold_arithmetic"]
    assert receipt["support_exact"] == str(expected["support"])
    assert receipt["weaken_exact"] == str(expected["weaken"])
    assert receipt["share_exact"] == str(expected["share"])
    assert (
        after["structural_decision"]["numerical_label"] == expected["numerical_grade"]
    )
    for key in (
        "support_strength",
        "weaken_strength",
        "support_share",
        "effective_elements_unrounded",
        "hidden_stem_ledger",
        "relations",
        "stem_effects",
    ):
        assert after[key] == before[key]
    StrengthThresholdArithmetic.model_validate(receipt)


@pytest.mark.parametrize(
    "field,threshold,direction,expected",
    [
        ("strong_share", 0.6, 0, "强"),
        ("strong_share", 0.6, 1, "中和"),
        ("weak_share", 0.4, 0, "中和"),
        ("weak_share", 0.4, 1, "弱"),
    ],
)
def test_one_ulp_declared_parameter_change_is_not_erased_by_an_epsilon(
    field, threshold, direction, expected
):
    row = next(
        r for r in NEAR if r["index"] == (39568 if field == "strong_share" else 53298)
    )
    policy = replace(DEFAULT_POLICY, **{field: math.nextafter(threshold, direction)})
    result = evaluate(row["pillars"], policy)
    assert result["threshold_arithmetic"]["numerical_label"] == expected


def test_historical_private_mode_is_not_relabelled_as_exact_public_arithmetic():
    values = next(r for r in NEAR if r["index"] == 39568)["pillars"]
    assert "threshold_arithmetic" not in evaluate(values, mode="legacy_v5")


@pytest.mark.parametrize(
    "patch",
    [
        {"share_exact": "1/0"},
        {"share_exact": "nan"},
        {"share_exact": "2/5"},
        {"numerical_label": "强"},
        {"float_comparison_differs": False},
        {"support_above_half": False},
    ],
)
def test_contradictory_exact_receipt_is_rejected_but_projection_stays_partial(patch):
    values = next(r for r in NEAR if r["index"] == 39568)["pillars"]
    receipt = evaluate(values)["threshold_arithmetic"]
    with pytest.raises(ValidationError):
        StrengthThresholdArithmetic.model_validate({**receipt, **patch})
    assert StrengthThresholdArithmetic.model_validate(
        {"share_exact": "3/5"}
    ).model_dump(exclude_none=True) == {"share_exact": "3/5"}


def test_explanation_reads_the_supplied_exact_decision():
    values = next(r for r in NEAR if r["index"] == 39568)["pillars"]
    assessment = evaluate(values)
    before = copy.deepcopy(assessment)
    line = threshold_snapshot_lines(assessment)[0]
    assert "3/5" in line and "数值档为中和" in line and "浮点比较原为强" in line
    assert assessment == before
    assert threshold_snapshot_lines({}) == []


@pytest.mark.parametrize(
    "birth", [(1988, 7, 5, 8, "3/5", "强"), (1990, 3, 1, 12, "2/5", "弱")]
)
@pytest.mark.parametrize("key", KEYS)
def test_both_supported_boundary_births_across_all_public_transports(
    key, birth, rest, tmp_path, capsys
):
    year, month, day, hour, fraction, legacy = birth
    selected = SPECS[key]
    payload = {
        "name": "虚构精确阈值回归",
        "birth_year": year,
        "birth_month": month,
        "birth_day": day,
        "birth_hour": hour,
        "birth_minute": 0,
        "birth_second": 0,
        "birth_timezone": "Asia/Shanghai",
        "use_true_solar_time": False,
        "gender": "男",
    }
    if key != "analyze_destiny":
        payload.update(analysis_year=2026, analysis_month=10, analysis_day=25)
    fields = suggested_fields(selected, view="thresholds")
    flags = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 8192,
    }
    protocol = asyncio.run(native(selected, payload, **flags))
    code, local = call_cli(
        selected,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--strict-fields",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ],
    )
    assert not protocol.is_error and code == 0
    for name, value in (("native", protocol.structured_content), ("cli", local)):
        (tmp_path / (name + "-original-response.json")).write_text(
            json.dumps(value, ensure_ascii=False)
        )
    received = delivered_payload(protocol.structured_content)
    local = delivered_payload(local)
    assert business(received) == business(local)
    if selected.rest_path:
        response = rest.post(selected.rest_path, json=payload, params=flags)
        assert response.status_code == 200, response.text
        (tmp_path / "rest-original-response.json").write_text(
            json.dumps(response.json(), ensure_ascii=False)
        )
        assert business(delivered_payload(response.json())) == business(local)
    selected.output_model.model_validate(local)
    receipt = local
    for part in fields[0].split("."):
        receipt = receipt[part]
    assert receipt["share_exact"] == fraction
    assert receipt["numerical_label"] == "中和"
    assert receipt["legacy_float_numerical_label"] == legacy
    assert receipt["float_comparison_differs"] is True
