"""Exact boundary arithmetic must not fit labels or widen a tolerance band."""

import asyncio
import hashlib
import json
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
from tests.support import bazi_strength_reference_v3 as current_reference
from tests.support.transports import SPECS, business, call_cli, native
from tests.support.transports import rest as _rest_fixture

rest = _rest_fixture
NEAR = json.loads(
    (Path(__file__).parents[1] / "data/bazi/threshold-inputs.json").read_text()
)
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


def evaluate(values, policy=DEFAULT_POLICY):
    return _evaluate(
        dict(zip(("year", "month", "day", "hour"), map(tuple, values))),
        current_reference.seasonal_phases(values[1][1]),
        policy,
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
    receipt = evaluate(
        values,
    )["threshold_arithmetic"]
    patch = dict(patch)
    if receipt:
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


@pytest.mark.parametrize("birth", [(1988, 7, 5, 8), (1990, 3, 1, 12)])
@pytest.mark.parametrize("key", KEYS)
def test_boundary_births_use_independent_current_reference_on_all_public_transports(
    key, birth, rest, tmp_path, capsys
):
    year, month, day, hour = birth
    selected = SPECS[key]
    calendar = BaZiCalendar.get_four_pillars(
        datetime(year, month, day, hour), timezone_name="Asia/Shanghai"
    )
    values = ["".join(calendar[name]) for name in current_reference.ORDER]
    assessment = evaluate(values)
    expected = current_reference.reconstruct(values, assessment["relations"])
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
