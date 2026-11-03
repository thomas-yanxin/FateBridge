"""Exact boundary arithmetic must not fit labels or widen a tolerance band."""

import asyncio
import copy
import gzip
import hashlib
import importlib.util
import json
import math
from dataclasses import replace
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_strength_thresholds import StrengthThresholdArithmetic
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate
from fatebridge.core.strength_thresholds import threshold_snapshot_lines
from tests import bazi_strength_reference_v3 as current_reference
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


def evaluate(
    values, policy=DEFAULT_POLICY, mode="precise_binding_only_v1", *, legacy=False
):
    """Use current phases unless a historical arithmetic premise is explicit."""
    return _evaluate(
        dict(zip(("year", "month", "day", "hour"), map(tuple, values))),
        current_reference.seasonal_phases(values[1][1], legacy=legacy),
        policy,
        stem_effect_mode=mode,
    )


@pytest.mark.parametrize("month_branch", "子丑寅卯辰巳午未申酉戌亥")
def test_adopted_season_map_matches_all_literal_five_season_cells(month_branch):
    assert ElementAnalysis.seasonal_phases(
        month_branch
    ) == current_reference.seasonal_phases(month_branch)


def test_independent_v3_reference_has_a_closed_form_seasonal_budget_anchor():
    # Four 寅 branches contain total physical 甲/丙/戊 budgets 40/7,20/7,10/7.
    # Revealed 甲 adds 5/4, the three rooted non-day 甲 add 6; spring's
    # 火相 and 土死 supply factors 3/2 and 1/2. No relation premise is needed.
    expected = current_reference.reconstruct(["甲寅"] * 4, [])
    assert expected["energies"] == {
        "木": Fraction(142, 7),
        "火": Fraction(30, 7),
        "土": Fraction(5, 7),
        "金": Fraction(0),
        "水": Fraction(0),
    }
    assert expected["share"] == Fraction(142, 177)
    assert expected["body_within_support"] == 1
    assert expected["requires_special_structure_review"] is False


@pytest.mark.parametrize("row", NEAR, ids=lambda r: str(r["index"]))
def test_every_historical_first_boundary_object_keeps_its_exact_arithmetic(row):
    before = row["result"]
    expected = reference.reconstruct(row["pillars"], before["relations"])
    after = evaluate(row["pillars"], legacy=True)
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
def test_historical_one_ulp_parameter_change_is_not_erased_by_an_epsilon(
    field, threshold, direction, expected
):
    row = next(
        r for r in NEAR if r["index"] == (39568 if field == "strong_share" else 53298)
    )
    policy = replace(DEFAULT_POLICY, **{field: math.nextafter(threshold, direction)})
    result = evaluate(row["pillars"], policy, legacy=True)
    assert result["threshold_arithmetic"]["numerical_label"] == expected


def test_historical_private_mode_is_not_relabelled_as_exact_public_arithmetic():
    values = next(r for r in NEAR if r["index"] == 39568)["pillars"]
    assert "threshold_arithmetic" not in evaluate(values, mode="legacy_v5", legacy=True)


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
@pytest.mark.parametrize("legacy", [False, True], ids=["current_v11", "historical"])
def test_contradictory_exact_receipt_is_rejected_but_projection_stays_partial(
    patch, legacy
):
    values = next(r for r in NEAR if r["index"] == 39568)["pillars"]
    receipt = evaluate(values, legacy=legacy)["threshold_arithmetic"]
    patch = dict(patch)
    if not legacy:
        # Historical constants can become valid after a semantic correction.
        # Current faults must actually contradict this receipt.
        for key, value in patch.items():
            if isinstance(value, bool):
                patch[key] = not receipt[key]
            elif key == "numerical_label" and value == receipt[key]:
                patch[key] = "中和" if value != "中和" else "强"
            elif key == "share_exact" and value == receipt[key]:
                patch[key] = "3/5" if value != "3/5" else "2/5"
    with pytest.raises(ValidationError):
        StrengthThresholdArithmetic.model_validate({**receipt, **patch})
    assert StrengthThresholdArithmetic.model_validate(
        {"share_exact": "3/5"}
    ).model_dump(exclude_none=True) == {"share_exact": "3/5"}


def test_historical_explanation_reads_the_supplied_exact_decision():
    values = next(r for r in NEAR if r["index"] == 39568)["pillars"]
    assessment = evaluate(values, legacy=True)
    before = copy.deepcopy(assessment)
    line = threshold_snapshot_lines(assessment)[0]
    assert "3/5" in line and "数值档为中和" in line and "浮点比较原为强" in line
    assert assessment == before
    assert threshold_snapshot_lines({}) == []


@pytest.mark.parametrize(
    "birth", [(1988, 7, 5, 8, "3/5", "强"), (1990, 3, 1, 12, "2/5", "弱")]
)
@pytest.mark.parametrize("key", KEYS)
def test_historical_boundary_births_use_v11_reference_on_all_public_transports(
    key, birth, rest, tmp_path, capsys
):
    year, month, day, hour, fraction, legacy = birth
    # These immutable identities were boundaries under the old seasonal map.
    # Retain that counterexample without requiring v11 to keep the old answer.
    historical = next(
        row for row in NEAR if row["index"] == (39568 if fraction == "3/5" else 53298)
    )
    replay = evaluate(historical["pillars"], legacy=True)["threshold_arithmetic"]
    assert replay["share_exact"] == fraction
    assert replay["numerical_label"] == "中和"
    assert replay["legacy_float_numerical_label"] == legacy
    assert replay["float_comparison_differs"] is True
    pillars = BaZiCalendar.get_four_pillars(
        datetime(year, month, day, hour), timezone_name="Asia/Shanghai"
    )
    values = ["".join(pillars[name]) for name in current_reference.ORDER]
    assert values == historical["pillars"]
    assessment = ElementAnalysis.analyze_day_master_strength(pillars)["assessment"]
    assert assessment["method_id"] == "season_root_revelation_relations_v11"
    # Independence is numerical, conditional on these actual discrete relations.
    expected = current_reference.reconstruct(values, assessment["relations"])
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
    assert receipt["energies_exact"] == {
        element: str(value) for element, value in expected["energies"].items()
    }
    assert receipt["support_exact"] == str(expected["support"])
    assert receipt["weaken_exact"] == str(expected["weaken"])
    assert receipt["share_exact"] == str(expected["share"])
    assert receipt["numerical_label"] == expected["numerical_grade"]
    assert (
        receipt["requires_special_structure_review"]
        is expected["requires_special_structure_review"]
    )
