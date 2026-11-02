"""Source-held four-cardinal targets, dimensional distinction and raw residuals."""

import hashlib
import json
import subprocess
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

import fatebridge.core.guolao_cardinals as module
from fatebridge.core.guolao_huangchi import load_table

ROOT = Path(__file__).parents[1]
FIXTURE = Path(__file__).parent / "fixtures/guolao-cardinals-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


@pytest.mark.parametrize("profile", ["nlc166", "wikisource"])
def test_printed_quarter_is_year_based_and_not_the_coordinate_circle(profile):
    r = module.gujin43_cardinal_example(profile=profile)
    lane = r["printed_operands_lane"]
    assert F(lane["year_quarter_du_exact"]) == F("91.31055")
    assert F(lane["coordinate_circle_quarter_du_exact"]) == F("91.31445")
    assert F(lane["corrected_quarter_du_exact"]) == F("91.31085")
    assert list(map(F, lane["huangchi_differences_du_exact"])) == list(
        map(F, REFERENCE["printed_huangchi_differences_du"])
    )
    assert lane["next_winter_closure_residual_du_exact"] == "0"
    assert F(lane["wrong_circle_quarter_closure_residual_du_exact"]) == F("0.0156")


@pytest.mark.parametrize("index", range(5))
def test_all_five_source_cardinal_longitudes_are_compared_before_modulo(index):
    lane = module.gujin43_cardinal_example(profile="wikisource")[
        "printed_operands_lane"
    ]
    actual = lane["positions"][index]
    expected = REFERENCE["printed_unwrapped_ecliptic_positions_du"][index]
    assert F(actual["unwrapped_from_ji_start_du_exact"]) == F(expected)
    if index == 4:
        assert F(actual["modulo_circle_from_ji_start_du_exact"]) == F("4.6236")
    assert "mansion" not in actual and "longitude" not in actual


@pytest.mark.parametrize("index", range(5))
def test_source_times_preserve_full_cycle_wraps_and_fractional_days(index):
    r = module.gujin43_cardinal_example(profile="wikisource")
    actual = r["cardinal_times"][index]
    assert F(actual["sexagenary_cycle_day_exact"]) == F(
        REFERENCE["printed_cycle_days"][index]
    )
    assert F(actual["unwrapped_source_day_exact"]) == F(
        ["42.0796", "130.98875", "224.7007", "318.41265", "407.3218"][index]
    )
    assert actual["sexagenary_day"] == ["丙午", "甲戌", "戊申", "壬午", "辛亥"][index]
    assert r["integer_day_distances"] == REFERENCE["printed_integer_day_distances"]
    assert r["source_time_spans_minus_year_days_exact"] == "0"
    assert r["next_winter_time_closure_residual_days_exact"] == "0"


@pytest.mark.parametrize("profile", ["nlc166", "wikisource"])
def test_unrounded_initial_rate_chain_preserves_both_quotients_and_residuals(profile):
    r = module.gujin43_cardinal_example(profile=profile)
    hand = REFERENCE["independent_hand_checks"]
    lane = r["unrounded_rate_lane"]
    assert list(map(F, lane["winter_ecliptic_du_exact"])) == list(
        map(F, hand["unrounded_ecliptic_winter_du_exact"])
    )
    assert list(map(F, r["unrounded_minus_printed_winter_du_exact"])) == list(
        map(F, hand["unrounded_minus_printed_winter_du_exact"])
    )
    assert F(lane["corrected_quarter_du_exact"]) != F("91.31085")
    assert lane["next_winter_closure_residual_du_exact"] == "0"
    assert not r["intermediate_rounding_applied"]
    assert not r["printed_values_used_in_unrounded_lane"]
    assert not r["printed_precision_policy_established"]


def test_mansion_relative_winter_degree_is_not_a_solstice_local_accumulation():
    r = module.gujin43_cardinal_example(profile="wikisource")
    # Source says 初日下赤道率, not the row for this mansion-relative degree.
    wrong = load_table("wikisource").convert(
        F("5.0392"), origin="solstice", direction="equatorial_to_ecliptic"
    )
    assert F(wrong["output_local_accumulation_du_exact"]) == F(50343, 10849)
    assert F(r["unrounded_rate_lane"]["winter_ecliptic_du_exact"][0]) != F(
        wrong["output_local_accumulation_du_exact"]
    )


def test_held_printed_positions_are_not_raw_lane_training_labels(tmp_path, monkeypatch):
    before = module.gujin43_cardinal_example(profile="wikisource")
    data = json.loads(module.DATA.read_text())
    data["printed_winter_ecliptic_du"] = ["4", "3"]
    edited = tmp_path / "deliberately_changed_printed_operands.json"
    edited.write_text(json.dumps(data))
    monkeypatch.setattr(module, "DATA", edited)
    after = module.gujin43_cardinal_example(profile="wikisource")
    assert before["unrounded_rate_lane"] == after["unrounded_rate_lane"]
    assert before["printed_operands_lane"] != after["printed_operands_lane"]
    assert F(
        after["printed_operands_lane"]["positions"][1][
            "unwrapped_from_ji_start_du_exact"
        ]
    ) != F(REFERENCE["printed_unwrapped_ecliptic_positions_du"][1])
    # Closure follows from year + (RA0-RA1) == circle for ANY ecliptic pair.
    # It cannot accept an invented pair or establish a rounding rule.
    assert (
        after["printed_operands_lane"]["next_winter_closure_residual_du_exact"] == "0"
    )


def test_frozen_source_excerpt_and_runtime_inputs_are_fingerprinted():
    for path, key in [
        (FIXTURE / REFERENCE["excerpt_file"], "excerpt_sha256"),
        (module.DATA, "runtime_data_sha256"),
    ]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == REFERENCE[key]
    r = module.gujin43_cardinal_example(profile="nlc166")
    assert r["data_sha256"] == REFERENCE["runtime_data_sha256"]
    assert not REFERENCE["facsimile_newly_collated"]
    for key in [
        "modern_calendar_date_assigned",
        "modern_epoch_calibrated",
        "redated_mansion_widths_reconstructed",
        "life_degree_accepted",
        "used_in_native_birth_chart",
        "real_world_efficacy_tested",
    ]:
        assert r[key] is False


@pytest.mark.parametrize("profile", ["nlc166", "wikisource"])
def test_cli_replays_both_lanes_with_explicit_named_example(profile):
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/audit_guolao_cardinals.py"),
            "--example",
            "gujin43-318",
            "--profile",
            profile,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(proc.stdout)
    assert result == module.gujin43_cardinal_example(profile=profile)


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--profile", "nlc166"],
        ["--example", "gujin43-318"],
        ["--example", "2026-10-22", "--profile", "nlc166"],
        ["--example", "gujin43-318", "--profile", "best_fit"],
    ],
)
def test_cli_does_not_infer_an_example_date_or_best_fitting_table(args):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/audit_guolao_cardinals.py"), *args],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert not proc.stdout


def test_unavailable_source_profile_is_not_silently_replaced():
    with pytest.raises(ValueError):
        module.gujin43_cardinal_example(profile="best_fit")
