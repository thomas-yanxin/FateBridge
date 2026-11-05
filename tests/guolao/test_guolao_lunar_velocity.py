"""Full discrete table, empty endpoints, original step checks and four dated entries."""

import csv
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_lunar_velocity as v

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests/fixtures/guolao-lunar-velocity-v1"
SOURCE = json.loads((FIXTURE / "reference.json").read_text())
HALF = F("13.7773")
RATE = F("12.2")


def test_all_source_images_transcription_and_previous_reference_are_pinned():
    for artifact in SOURCE["artifacts"]:
        if artifact["path"].endswith("-cli-stdout.json"):
            continue  # Retired program output is not an independent source.
        assert (
            hashlib.sha256((FIXTURE / artifact["path"]).read_bytes()).hexdigest()
            == artifact["sha256"]
        )
    prior = SOURCE["prior_source_reference"]
    assert (
        hashlib.sha256((FIXTURE / prior["path"]).read_bytes()).hexdigest()
        == prior["sha256"]
    )
    assert not SOURCE["second_independent_collator"]
    assert SOURCE["single_collator"]
    rows = list(
        csv.DictReader((FIXTURE / "rates-transcribed.csv").read_text().splitlines())
    )
    actual = json.loads(v.DATA.read_bytes())["rows"]
    assert len(rows) == len(actual) == 169
    for expected, got in zip(rows, actual):
        for key in ["fast_ancient_du_per_limit", "slow_ancient_du_per_limit"]:
            assert (expected[key] or None) == got[key]
        assert int(expected["limit_index"]) == got["limit_index"]
        assert int(expected["djvu_page"]) == got["djvu_page"]
        assert expected["half"] == got["half"]
    assert actual == SOURCE["rows_transcribed"]
    assert (
        sum(
            row[k] is not None
            for row in actual
            for k in ["fast_ancient_du_per_limit", "slow_ancient_du_per_limit"]
        )
        == 336
    )
    assert (
        actual[168]["fast_ancient_du_per_limit"]
        is actual[168]["slow_ancient_du_per_limit"]
        is None
    )


def test_every_printed_numeric_cell_is_reachable_without_reflection_or_interpolation():
    for row in SOURCE["rows_transcribed"][:168]:
        index = row["limit_index"]
        within = F(2 * index + 1, 2) / RATE
        for phase, name in [
            (within, "fast_ancient_du_per_limit"),
            (HALF + within, "slow_ancient_du_per_limit"),
        ]:
            result = v.gujin45_lunar_velocity(phase)
            assert result["whole_limit_index"] == index
            assert result["printed_velocity_ancient_du_per_limit"] == row[name]
            assert F(result["discarded_fraction_of_limit_exact"]) == F(1, 2)
            assert not result["interpolated"]
            assert not result["reflected_or_periodically_filled"]


def test_all_integer_cell_boundaries_and_both_sides_use_exact_rational_input():
    epsilon = F(1, 10**14)
    for index in range(1, 169):
        within = F(index) / RATE
        for shift in [F(), HALF]:
            assert (
                v.gujin45_lunar_velocity(shift + within - epsilon)["whole_limit_index"]
                == index - 1
            )
            assert (
                v.gujin45_lunar_velocity(shift + within)["whole_limit_index"] == index
            )
            assert (
                v.gujin45_lunar_velocity(shift + within + epsilon)["whole_limit_index"]
                == index
            )


def test_half_anomaly_endpoint_stays_empty_and_is_not_replaced_by_opposite_initial_row():
    at = v.gujin45_lunar_velocity(HALF)
    assert at["phase"] == "疾"
    assert at["whole_limit_index"] == 168
    assert at["velocity_ancient_du_per_limit_exact"] is None
    assert at["status"] == "printed_empty_endpoint_no_value"
    epsilon = F(1, 10**14)
    after = v.gujin45_lunar_velocity(HALF + epsilon)
    assert after["phase"] == "遲"
    assert after["whole_limit_index"] == 0
    assert F(after["velocity_ancient_du_per_limit_exact"]) == F(".9855")
    assert (
        v.gujin45_lunar_velocity(2 * HALF)["printed_velocity_ancient_du_per_limit"]
        == "1.2071"
    )


def test_all_ten_reflection_disagreements_are_retained_not_normalized():
    data = json.loads(v.DATA.read_bytes())
    rows = data["rows"]
    mismatches = []
    for row in rows[:168]:
        other = rows[167 - row["limit_index"]]
        for a, b in [
            ("fast_ancient_du_per_limit", "slow_ancient_du_per_limit"),
            ("slow_ancient_du_per_limit", "fast_ancient_du_per_limit"),
        ]:
            if F(row[a]) != F(other[b]):
                mismatches.append(
                    dict(
                        index=row["limit_index"],
                        column=a,
                        printed=row[a],
                        opposite_index=other["limit_index"],
                        opposite_printed=other[b],
                    )
                )
    assert mismatches == SOURCE["reflection_comparison_without_emendation"]
    assert len(mismatches) == 10
    for mismatch in mismatches:
        phase = (F(mismatch["index"]) + F(1, 2)) / RATE
        if mismatch["column"] == "slow_ancient_du_per_limit":
            phase += HALF
        result = v.gujin45_lunar_velocity(phase)
        diagnostic = result["reflection_comparison_diagnostic"]
        assert not diagnostic["agrees"]
        assert diagnostic["opposite_index"] == mismatch["opposite_index"]
        assert diagnostic["opposite_printed_velocity"] == mismatch["opposite_printed"]
        assert not diagnostic["comparison_used_to_replace_selected_value"]
        assert result["printed_velocity_ancient_du_per_limit"] == mismatch["printed"]
    assert rows[58]["slow_ancient_du_per_limit"] == "1.0547"
    assert rows[144]["fast_ancient_du_per_limit"] == "1.0036"
    assert rows[145]["fast_ancient_du_per_limit"] == "1.0018"
    assert rows[149]["slow_ancient_du_per_limit"] == "1.1946"
    assert rows[150]["slow_ancient_du_per_limit"] == "1.1937"


@pytest.mark.parametrize("example", SOURCE["gujin49_independent_step_checks"])
def test_original_juan49_116_and_118_limit_rates(example):
    result = v.gujin45_lunar_velocity(HALF + F(example["half_anomaly_days"]))
    assert result["phase"] == example["phase"]
    assert result["whole_limit_index"] == example["index"]
    assert F(result["velocity_ancient_du_per_limit_exact"]) == F(example["velocity"])
    if "eclipse_relative_velocity" in example:
        assert F(result["velocity_ancient_du_per_limit_exact"]) - F(".082") == F(
            example["eclipse_relative_velocity"]
        )


def test_original_juan49_time_correction_reports_rounding_residual_not_a_patched_answer():
    example = SOURCE["gujin49_correction_check"]
    result = v.gujin45_time_correction(
        F(example["solar_signed_ancient_du"]),
        F(example["lunar_signed_ancient_du"]),
        HALF + F("9.533458"),
    )
    assert F(result["time_correction_days_exact"]) == F(
        example["exact_calculated_correction_days"]
    )
    assert F(result["time_correction_days_exact"]) != F(
        example["printed_correction_days"]
    )
    assert abs(
        F(result["time_correction_days_exact"]) - F(example["printed_correction_days"])
    ) < F(".000001")
    assert not result["sun_daily_motion_subtracted_from_denominator"]
    assert not result["printed_shortcut_column_used"]


def test_empty_velocity_does_not_invent_a_time_correction():
    result = v.gujin45_time_correction(F(1), F(2), HALF)
    assert result["time_correction_days_exact"] is None


def test_four_original_entry_days_are_reproduced_from_two_independent_conjunctions():
    example = SOURCE["worked_example"]
    result = v.gujin_four_extras_table_days(F(example["zhongji_days"]))
    indices = set()
    for key, expected in example["factors"].items():
        actual = result["factors"][key]
        indices.add(actual["mean_lunation_candidate_index"])
        assert (
            actual["diagnostic_day_after_table_conjunction"] == expected["printed_day"]
        )
        assert actual["candidate_contains_event_civil_day"]
        assert actual["diagnostic_candidate_month_length_days"] in [29, 30]
        assert actual["assigned_lunar_month"] is None
        assert actual["lunar_date"] is None
        conjunction = actual["conjunction"]
        assert (
            conjunction["angular_components"]["source_profile"]["zhuanying_days"]
            == "13.1904"
        )
        assert not conjunction["complete_source_calendar_accepted"]
        assert not conjunction["used_in_native_birth_chart"]
    assert indices == set(SOURCE["independent_conjunction_indices"]) == {2, 4}
    assert not result["printed_calendar_dates_used_as_algorithm_inputs"]
    assert not result["lunar_dates_assigned"]
    assert not result["intercalation_reconstructed"]
    assert not result["modern_epoch_calibrated"]


def test_purple_conjunction_crosses_midnight_while_other_three_share_the_same_month_start():
    result = v.gujin_four_extras_table_days(F("116147.0196"))["factors"]
    purple = result["purple"]["conjunction"]
    assert F(purple["angular_components"]["mean_conjunction_day_cycle_exact"]) == F(
        "17.738455"
    )
    assert 18 < F(purple["research_conjunction_day_cycle_exact"]) < F("18.01")
    assert purple["midnight_displacement_from_mean_days"] == 1
    assert (
        result["apogee"]["conjunction"]
        == result["rahu"]["conjunction"]
        == result["ketu"]["conjunction"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "removed_row",
        "filled_endpoint",
        "missing_value",
        "precision",
        "period",
        "profile",
    ],
)
def test_corrupt_or_emended_data_is_rejected_without_guessing(
    tmp_path, monkeypatch, fault
):
    data = json.loads(v.DATA.read_bytes())
    if fault == "removed_row":
        data["rows"].pop(58)
    elif fault == "filled_endpoint":
        data["rows"][168]["fast_ancient_du_per_limit"] = "0.9855"
    elif fault == "missing_value":
        data["rows"][10]["fast_ancient_du_per_limit"] = None
    elif fault == "precision":
        data["rows"][10]["fast_ancient_du_per_limit"] = "1.200400"
    elif fault == "period":
        data["limits_per_day"] = "500/41"
    else:
        data["angular_profile_id"] = "li_zhang_1996_printed_formula"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(v, "DATA", path)
    with pytest.raises(ValueError):
        v.gujin45_lunar_velocity(F())


@pytest.mark.parametrize("bad", [0, True, "1", 2451545.0, None])
def test_explicit_fraction_units_required(bad):
    with pytest.raises(TypeError, match="Fraction"):
        v.gujin45_lunar_velocity(bad)
    with pytest.raises(TypeError, match="Fraction"):
        v.gujin_table_conjunction(bad, 0)
    with pytest.raises(TypeError, match="Fraction"):
        v.gujin45_time_correction(bad, F(), F())
