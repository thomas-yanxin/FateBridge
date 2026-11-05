"""Original quarter-step units, date-rule scope and exact missing-data behavior."""

import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_lunar_phases as subject
from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_lunar_velocity import gujin_table_conjunction
from fatebridge.validation.guolao_lunar_phases import audit_lunar_phase_grid

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests/fixtures/guolao-lunar-phases-v1"


def test_primary_and_corroborating_original_bytes_and_nonblind_plan_pinned():
    reference = json.loads((FIXTURE / "reference.json").read_text())
    for row in reference["artifacts"] + reference["primary_images"]:
        raw = (FIXTURE / row["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    data, _ = subject._profile()
    assert (
        data["source_reference_sha256"]
        == hashlib.sha256((FIXTURE / "reference.json").read_bytes()).hexdigest()
    )
    plan = (FIXTURE / "plan-before-phase-grid.json").read_bytes()
    assert (
        hashlib.sha256(plan).hexdigest()
        == "1e7f9657b1e680f1d6fe70f097d2a04a190f42e3fb86234ab7ea50bdefd8013d"
    )
    assert reference["single_collator"] and not reference["independent_second_collator"]
    assert not reference["readings"]["rule_applies_to_new_moon"]
    assert "not blinded" in json.loads(plan)["prior_knowledge"]


@pytest.mark.parametrize(
    "index,offset",
    [
        (0, "-20.205"),
        (1, "-12.82235175"),
        (2, "-5.4397035"),
        (3, "1.94294475"),
        (4, "9.325593"),
    ],
)
def test_independent_mean_quarter_constants_and_initial_source_offsets(index, offset):
    result = subject.source_lunar_phase(F(), index)
    assert F(result["mean_phase_offset_from_winter_days_exact"]) == F(offset)
    assert F(result["mean_quarter_step_days_exact"]) == F("7.38264825")
    expected_angles = [F(), F("91.314375"), F("182.62875"), F("273.943125")]
    assert (
        F(result["source_target_separation_ancient_du_exact"])
        == expected_angles[index % 4]
    )
    assert not result["phase_instants_interpolated_between_new_moons"]
    assert not result["physical_phase_time_validated"]
    assert result["lunar_date"] is None


@pytest.mark.parametrize(
    "elapsed,index",
    [(0, 0), (19, 1), (31, 10), (45, 15), (243, 0), (318, 4), (399, 17)],
)
def test_every_fourth_phase_keeps_existing_new_moon_arithmetic(elapsed, index):
    middle = shoushi_winter_cycle(elapsed).zhongji_days
    old = gujin_table_conjunction(middle, index)
    new = subject.source_lunar_phase(
        middle, index * 4, source_sunrise_fraction=F(".999")
    )
    assert new["phase_kind"] == "new_moon"
    for new_key, old_key in [
        ("time_correction_days_exact", "time_correction_days_exact"),
        (
            "research_phase_offset_from_winter_days_exact",
            "research_conjunction_offset_from_winter_days_exact",
        ),
        ("research_phase_day_cycle_exact", "research_conjunction_day_cycle_exact"),
        (
            "research_phase_midnight_sexagenary_day",
            "research_conjunction_sexagenary_day",
        ),
        ("lunar_velocity", "lunar_velocity"),
    ]:
        assert new[new_key] == old[old_key]
    assert not new["sunrise_shift_applied_to_new_moon"]
    assert new["source_phase_day_assignment"]["sunrise_rollback_applied"] in (
        False,
        None,
    )


@pytest.mark.parametrize("kind", subject.KINDS[1:])
@pytest.mark.parametrize(
    "fraction,rollback", [(F(".2499"), True), (F(".25"), True), (F(".2501"), False)]
)
def test_printed_inclusive_sunrise_threshold_and_its_two_sides(
    kind, fraction, rollback
):
    result = subject.assign_source_phase_day(
        60 + fraction, kind, source_sunrise_fraction=F(1, 4)
    )
    assert result["sunrise_rollback_applied"] is rollback
    assert result["assigned_source_phase_day_integer"] == (59 if rollback else 60)
    assert result["assigned_source_phase_sexagenary_day"] == (
        "癸亥" if rollback else "甲子"
    )
    assert not result["modern_calendar_date_assigned"]
    assert not result["supplied_sunrise_location_or_ephemeris_verified"]


@pytest.mark.parametrize("sunrise", [None, F(), F(1, 4), F(".999")])
def test_new_moon_does_not_receive_the_quarter_full_moon_rule(sunrise):
    result = subject.assign_source_phase_day(
        F("60.1"), "new_moon", source_sunrise_fraction=sunrise
    )
    assert result["assigned_source_phase_day_integer"] == 60
    assert result["assigned_source_phase_sexagenary_day"] == "甲子"
    assert result["sunrise_rollback_applied"] is False
    assert not result["source_sunrise_required_for_phase_date"]


@pytest.mark.parametrize("kind", subject.KINDS[1:])
def test_missing_sunrise_preserves_known_instant_but_not_phase_day(kind):
    result = subject.assign_source_phase_day(F("60.1"), kind)
    assert result["civil_midnight_source_day_integer"] == 60
    assert result["event_fraction_of_source_day_exact"] == "1/10"
    assert result["assigned_source_phase_day_integer"] is None
    assert result["assigned_source_phase_sexagenary_day"] is None
    assert result["sunrise_rollback_applied"] is None
    assert result["status"] == "requires_explicit_source_sunrise"
    assert not result["sunrise_computed_or_defaulted"]


def test_missing_required_velocity_is_not_filled_or_replaced_by_mean_phase():
    middle = shoushi_winter_cycle(31).zhongji_days
    result = subject.source_lunar_phase(middle, 40, source_sunrise_fraction=F(1, 4))
    assert result["research_phase_offset_from_winter_days_exact"] is None
    assert result["lunar_velocity"]["whole_limit_index"] == 168
    assert result["source_phase_day_assignment"]["status"] == "phase_time_unavailable"
    assert (
        result["source_phase_day_assignment"]["assigned_source_phase_day_integer"]
        is None
    )


@pytest.mark.parametrize("kind", subject.KINDS)
def test_unavailable_time_never_yields_a_date_even_with_given_sunrise(kind):
    result = subject.assign_source_phase_day(
        None, kind, source_sunrise_fraction=F(1, 4)
    )
    assert result["assigned_source_phase_day_integer"] is None
    assert result["sunrise_rollback_applied"] is None


@pytest.mark.parametrize("sunrise", [F(-1, 10), F(1), F(2500)])
def test_source_sunrise_units_not_guessed_or_reduced(sunrise):
    with pytest.raises(ValueError):
        subject.assign_source_phase_day(
            F("60.1"), "full_moon", source_sunrise_fraction=sunrise
        )


@pytest.mark.parametrize("sunrise", [True, 0.25, "1/4"])
def test_nonfraction_sunrise_rejected(sunrise):
    with pytest.raises(TypeError):
        subject.assign_source_phase_day(
            F("60.1"), "full_moon", source_sunrise_fraction=sunrise
        )


@pytest.mark.parametrize("index", [True, 0.25, "2"])
def test_noninteger_phase_index_not_silently_coerced(index):
    with pytest.raises(TypeError):
        subject.source_lunar_phase(F(), index)


def test_negative_phase_does_not_borrow_lower_reckoning_for_upper_reckoning():
    with pytest.raises(ValueError):
        subject.source_lunar_phase(F(), -1)


def test_quarter_is_recomputed_instead_of_interpolating_neighboring_new_moons():
    first, quarter, next_moon = [subject.source_lunar_phase(F(), i) for i in (0, 1, 4)]
    times = [
        F(r["research_phase_offset_from_winter_days_exact"])
        for r in (first, quarter, next_moon)
    ]
    assert times[1] != (3 * times[0] + times[2]) / 4

    def keys(value):
        if isinstance(value, dict):
            for k, v in value.items():
                yield k
                yield from keys(v)
        elif isinstance(value, list):
            for v in value:
                yield from keys(v)

    assert not any("conjunction" in k for k in keys(quarter))


def test_sunrise_changes_source_day_label_without_moving_the_phase_instant():
    unknown = subject.source_lunar_phase(F(), 2)
    assigned = subject.source_lunar_phase(F(), 2, source_sunrise_fraction=F(".99"))
    assert (
        unknown["research_phase_offset_from_winter_days_exact"]
        == assigned["research_phase_offset_from_winter_days_exact"]
    )
    assert (
        unknown["time_correction_days_exact"] == assigned["time_correction_days_exact"]
    )
    assert (
        unknown["source_phase_day_assignment"]["assigned_source_phase_day_integer"]
        is None
    )
    assert assigned["source_phase_day_assignment"]["sunrise_rollback_applied"]


def test_small_partition_counts_missing_sunrise_separately_from_time_gaps():
    result = audit_lunar_phase_grid(0, 1)
    c = result["counts"]
    assert result["declared_positions"] == c["declared_positions"] == 72
    assert c["source_time_available"] + c.get("source_time_unavailable", 0) == 72
    assert c["source_phase_day_assigned"] == c["new_moon_time_available"]
    assert c["source_time_available_but_sunrise_missing"] == sum(
        c.get(k + "_time_available", 0) for k in subject.KINDS[1:]
    )
    assert not result["physical_phase_time_validated"]
    assert not result["source_sunrise_supplied_or_defaulted"]


@pytest.mark.parametrize("start,stop", [(0, 0), (-1, 2), (0, 401), (True, 2)])
def test_invalid_diagnostic_range_rejected(start, stop):
    with pytest.raises(ValueError):
        audit_lunar_phase_grid(start, stop)
