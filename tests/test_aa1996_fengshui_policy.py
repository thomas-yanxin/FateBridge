"""A named model keeps existing candidate and numerical acceptance gates."""

from datetime import datetime, timedelta, timezone

from fatebridge.core.aa1996_solar import MODEL_ID
from fatebridge.core.fengshui.calendar import (
    boundary_model_policy,
    boundary_uncertainty_reason,
)
from fatebridge.core.fengshui.snapshot import _calendar_cautions
from fatebridge.validation.fengshui_solar_terms import compare_resolution


def test_named_model_keeps_five_second_candidate_guard():
    moment = datetime(2026, 2, 4, tzinfo=timezone.utc)
    record = dict(
        moment=moment.isoformat(), ephemeris_model=MODEL_ID, approximate=False
    )
    policy = boundary_model_policy(record)
    assert policy["operational_guard_seconds"] == 5.0
    assert (
        policy["uncertainty_reason"]
        == "aa1996_solar_model_guard_not_accuracy_certification"
    )
    for offset in [-5, 0, 5]:
        assert (
            boundary_uncertainty_reason(moment + timedelta(seconds=offset), record)
            == policy["uncertainty_reason"]
        )
    assert (
        boundary_uncertainty_reason(moment + timedelta(seconds=5.001), record) is None
    )
    assert boundary_model_policy({**record, "approximate": True}) is None


def test_readout_names_actual_aa1996_model():
    lines = _calendar_cautions({"resolution": {"ephemeris_model": MODEL_ID}})
    assert any("AA1996" in line for line in lines)
    assert not any("完整范围尚未通过" in line for line in lines)


def test_named_provider_requires_both_root_and_actual_civil_gate():
    from fatebridge.core.astro.time_scales import ephemeris_time

    moment = datetime(2026, 2, 4, tzinfo=timezone.utc)
    tt = ephemeris_time(moment).jd_tt
    row = dict(year=2026, term_index=2, term="立春", jd_tt=tt)
    record = dict(
        moment=moment.isoformat(),
        provider="moshier_aa1996",
        approximate=False,
        ephemeris_model=MODEL_ID,
        time_basis={"root_time_scale": "TT"},
        solar_model_details={"selected_crossing_jd_tt": tt},
    )
    assert compare_resolution(row, record)["within_tolerance"]
    assert not compare_resolution(row, {**record, "solar_model_details": {}})[
        "within_tolerance"
    ]
    assert not compare_resolution(
        row,
        {**record, "solar_model_details": {"selected_crossing_jd_tt": tt + 2 / 86400}},
    )["within_tolerance"]
    assert not compare_resolution(
        row, {**record, "moment": (moment + timedelta(seconds=2)).isoformat()}
    )["within_tolerance"]
