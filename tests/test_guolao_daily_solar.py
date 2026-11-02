"""Primary motion columns, uncorrected conflicts and explicit source policies."""

import copy
import csv
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_daily_solar as subject
from fatebridge.validation.guolao_daily_solar import audit_daily_solar

FIXTURE = Path(__file__).parent / "fixtures/guolao-daily-solar-v1"


def test_source_data_matches_complete_literal_columns_frozen_before_implementation():
    reference = json.loads((FIXTURE / "reference.json").read_text())
    assert (
        hashlib.sha256(subject.DATA.read_bytes()).hexdigest()
        == reference["data_sha256"]
    )
    for item in reference["artifacts"]:
        blob = (FIXTURE / item["path"]).read_bytes()
        assert len(blob) == item["bytes"]
        assert hashlib.sha256(blob).hexdigest() == item["sha256"]
    raw = json.loads(subject.DATA.read_bytes())
    files = {
        "winter": "winter-forward-motion-transcription.csv",
        "spring": "spring94-motion-transcription.csv",
        "summer": "summer-forward-motion-transcription.csv",
        "autumn": "autumn89-motion-transcription.csv",
    }
    count = empty = 0
    for name, filename in files.items():
        rows = list(csv.DictReader((FIXTURE / filename).open()))
        for expected, actual in zip(rows, raw["segments"][name]["rows"], strict=True):
            assert int(expected["index"]) == actual["index"]
            assert (expected["rate_du"] or None) == actual["rate_du"]
            count += actual["rate_du"] is not None
            empty += actual["rate_du"] is None
    assert (count, empty) == (366, 4)
    assert reference["single_unblinded_collator"]
    assert not reference["independent_expert_collation"]


def test_forward_reverse_glyph_conflicts_not_reversed_or_repaired():
    model = subject.load_daily_solar(subject.PROFILE)
    winter, spring, summer, autumn = model.segments
    assert winter.rates[38] == F("1.031411")
    assert autumn.rates[50] == F("1.031011")
    assert spring.rates[2] == F("0.498519")
    assert summer.rates[91] == F("0.998519")
    assert autumn.rates[21] == F("1.012884")
    assert winter.rates[67] == F("1.013884")
    audit = audit_daily_solar()
    assert any(
        q["reverse_minus_forward_du_exact"] == "-1/2"
        for q in audit["forward_reverse_literal_differences"]
    )
    assert audit["source_rate_repair_or_fitted_tolerance"] is None
    assert audit["modern_astronomical_comparison"] is None


def test_verified_primary_spring_span_retains_digital_transcription_difference():
    audit = audit_daily_solar()
    difference = audit["source_witness_differences"][0]
    assert difference["siku_literal_du"] == "91.632579"
    assert difference["digital_revision_620325_du"] == "91.622579"
    assert F(audit["earlier_autumn_midnight_short_value_du_exact"]) == F("278.1576")
    model = subject.load_daily_solar(subject.PROFILE)
    assert model.anchors[3] == F("278.157692")


@pytest.mark.parametrize("segment", range(4))
def test_source_prescribed_bridge_uses_all_printed_rates_and_no_fitted_endpoint(
    segment,
):
    model = subject.load_daily_solar(subject.PROFILE)
    s = model.segments[segment]
    daily = (
        model.anchors[segment + 1]
        - model.anchors[segment]
        - sum(s.rates[: s.days], F())
    ) / s.days
    assert model.difference(segment, policy=subject.POLICIES[0]) == daily
    assert (
        model.point(segment, s.days, policy=subject.POLICIES[0])
        == model.anchors[segment + 1]
    )
    for n in range(s.days):
        assert (
            model.point(segment, n + 1, policy=subject.POLICIES[0])
            - model.point(segment, n, policy=subject.POLICIES[0])
            == s.rates[n] + daily
        )
    assert model.audit()["segments"][segment][
        "bridge_closure_is_source_formula_identity_not_independent_acceptance"
    ]


def test_printed_difference_nonclosure_is_reported_at_every_cardinal_boundary():
    model = subject.load_daily_solar(subject.PROFILE)
    for boundary in model.offsets[1:]:
        day = model.day(boundary, policy=subject.POLICIES[1])
        assert F(day["cardinal_boundary_left_limit"]["left_minus_right_du_exact"]) != 0
        closed = model.day(boundary, policy=subject.POLICIES[0])
        assert (
            F(closed["cardinal_boundary_left_limit"]["left_minus_right_du_exact"]) == 0
        )
    assert (
        model.day(365, policy=subject.POLICIES[1])[
            "following_corrected_daily_motion_du_exact"
        ]
        is None
    )


@pytest.mark.parametrize("policy", subject.POLICIES)
def test_full_named_year_grid_and_noon_keep_source_units_and_unresolved_sunrise(policy):
    model = subject.load_daily_solar(subject.PROFILE)
    days = [model.day(n, policy=policy) for n in range(366)]
    assert len(days) == 366
    for n, day in enumerate(days):
        assert day["unwrapped_source_day_integer"] == 42 + n
        assert not day["physical_solar_position_validated"]
        assert not day["modern_calendar_date_assigned"]
        assert day["folded_sunrise_argument"] is None
        assert not day["sunrise_or_phase_day_backfilled"]
        if n < 365:
            assert (
                F(day["noon_unwrapped_from_ji_start_du_exact"])
                == F(day["midnight_unwrapped_from_ji_start_du_exact"])
                + F(day["following_corrected_daily_motion_du_exact"]) / 2
            )
        else:
            assert day["noon_unwrapped_from_ji_start_du_exact"] is None


def test_independently_printed_first8_day_cumulative_and_all12_comparisons_kept():
    audit = audit_daily_solar()
    nodes = audit["worked_cumulative_comparison"]["residuals"]
    assert len(nodes) == 12
    first = nodes[0]
    assert first["day_offset"] == 8
    assert F(first["literal_rate_sum_du_exact"]) == F("8.394749")
    assert F(first["rate_sum_minus_worked_cumulative_du_exact"]) == 0
    assert any(F(q["rate_sum_minus_worked_cumulative_du_exact"]) != 0 for q in nodes)
    assert not audit["worked_cumulative_comparison"][
        "new_independent_facsimile_collation_of_all12_worked_cumulative_values"
    ]


@pytest.mark.parametrize("value", [True, False, 1.5, F(1), "1"])
def test_index_types_not_coerced_to_source_days(value):
    with pytest.raises(TypeError):
        subject.load_daily_solar(subject.PROFILE).day(value, policy=subject.POLICIES[0])


@pytest.mark.parametrize("value", [-1, 366])
def test_no_year_extrapolation_or_modulo_wrap(value):
    with pytest.raises(ValueError):
        subject.load_daily_solar(subject.PROFILE).day(value, policy=subject.POLICIES[0])


def test_explicit_profile_and_policy_required():
    with pytest.raises(ValueError):
        subject.load_daily_solar("best_fit")
    model = subject.load_daily_solar(subject.PROFILE)
    with pytest.raises(ValueError):
        model.day(1, policy="default")
    with pytest.raises(TypeError):
        model.day(1)


@pytest.mark.parametrize("index", [-1, 4, True, 0.0])
def test_segment_indices_cannot_use_python_negative_or_boolean_index(index):
    model = subject.load_daily_solar(subject.PROFILE)
    with pytest.raises((ValueError, TypeError)):
        model.point(index, 0, policy=subject.POLICIES[0])


@pytest.mark.parametrize("offset", [-1, 89, False, F(1)])
def test_segment_offsets_preserve_integer_day_scope(offset):
    model = subject.load_daily_solar(subject.PROFILE)
    with pytest.raises((ValueError, TypeError)):
        model.point(0, offset, policy=subject.POLICIES[0])


@pytest.mark.parametrize("mutation", ["unit", "blank", "bool", "missing"])
def test_corrupt_or_missing_source_rate_cannot_be_replaced(
    monkeypatch, tmp_path, mutation
):
    raw = copy.deepcopy(json.loads(subject.DATA.read_bytes()))
    if mutation == "unit":
        raw["coordinate_unit"] = "modern_degrees"
    elif mutation == "blank":
        raw["segments"]["summer"]["rows"][-1]["rate_du"] = "0.000000"
    elif mutation == "bool":
        raw["segments"]["summer"]["rows"][0]["rate_du"] = False
    else:
        raw["segments"]["summer"]["rows"].pop(3)
    file = tmp_path / "source.json"
    file.write_text(json.dumps(raw))
    monkeypatch.setattr(subject, "DATA", file)
    with pytest.raises(ValueError):
        subject.load_daily_solar(subject.PROFILE)
