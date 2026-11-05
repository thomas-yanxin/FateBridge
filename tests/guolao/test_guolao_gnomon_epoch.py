"""All75 literal rows stay visible alongside the separately sourced reading."""

import hashlib
import json
from decimal import Decimal, localcontext
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_gnomon_epoch as g
from fatebridge.validation.guolao_gnomon_epoch import audit_gnomon_epoch

ROOT = Path(__file__).parents[2]
FIXTURES = Path(__file__).parents[1] / "fixtures/guolao-gnomon-epoch-v1"
SOURCE = json.loads(g.DATA.read_bytes())
LITERAL = g.load_gnomon_epoch(g.PROFILE)
READING = g.load_gnomon_epoch(g.READING_PROFILE)


@pytest.mark.parametrize("row", SOURCE["triads"])
def test_every_published_triad_preserved_in_literal_profile_including_77_conflict(row):
    result = LITERAL.triad(row["season"], int(row["case_id"]))
    assert result["published_row"] == row
    conflict = row["season"] == "winter1279" and row["case_id"] == "25"
    assert result["within_published_half_unit"] is not conflict
    assert result["span_matches_published"] is not conflict
    if conflict:
        assert result["arithmetic"]["span_days"] == 75
        assert row["span_days"] == "99"
        assert result["observations"][0]["observation_id"] == "77"
    assert result["physical_julian_day"] is None
    assert result["timezone"] is None
    assert not result["source_clock_to_modern_epoch_calibrated"]


@pytest.mark.parametrize("row", SOURCE["triads"])
def test_explicit_primary_reading_is_separate_with_only_one_referenced_row_change(row):
    result = READING.triad(row["season"], int(row["case_id"]))
    assert result["within_published_half_unit"]
    assert result["span_matches_published"]
    assert result["published_row"] == row
    declared = result["declared_reading"]
    assert declared["observed_after_first_domain_comparison"]
    assert not declared["published_row_changed"]
    if row["season"] == "winter1279" and row["case_id"] == "25":
        assert declared["applied_row"]["A"] == "71"
        assert result["observations"][0]["shadow_zhang"] == "5.64925"
    else:
        assert declared["applied_row"] == row


@pytest.mark.parametrize("season", g.SEASONS)
def test_season_means_keep_all_rows_and_exact_clock_interval_membership(season):
    literal = LITERAL.season_mean(season)
    reading = READING.season_mean(season)
    assert reading["mean_within_published_half_unit"]
    assert reading["mean_inside_printed_clock_bin"] is (season != "summer1279")
    assert literal["mean_within_published_half_unit"] is (season != "winter1279")
    assert literal["triad_count"] == reading["triad_count"]
    assert reading["all_rows_retained_no_error_based_selection"]
    assert reading["profile_id"] == g.READING_PROFILE
    assert not reading["physical_epoch_calibrated"]
    assert not reading["triads_are_independent_observations_of_season_time"]


@pytest.mark.parametrize(
    "mode,days,shadows",
    [
        (g.MODES[0], (0, 7, 8), (F("7.94855"), F("7.95410"), F("7.94550"))),
        (g.MODES[1], (0, 1, 30), (F("1.23695"), F("1.22935"), F("1.22640"))),
    ],
)
def test_fraction_formula_against_separate_decimal_equations_and_unit_scaling(
    mode, days, shadows
):
    result = g.three_shadow_elapsed(days, shadows, mode=mode, noon_basis=g.NOON_BASIS)
    with localcontext() as ctx:
        ctx.prec = 70
        a, b, c = (Decimal(v.numerator) / Decimal(v.denominator) for v in shadows)
        ratio = (a - c) / (c - b) if mode == g.MODES[0] else (c - a) / (b - a)
        expected = Decimal("0.5") + (Decimal(days[-1] - days[0]) + ratio) / 2
        exact = F(result["elapsed_from_A_midnight_source_days_exact"])
        assert abs(
            Decimal(exact.numerator) / Decimal(exact.denominator) - expected
        ) < Decimal("1e-60")
        # Omitting noon-to-midnight transfer would be a systematic half-day error.
        assert abs(
            expected
            - (Decimal(exact.numerator) / Decimal(exact.denominator) - Decimal("0.5"))
        ) > Decimal("0.499")
    scaled = g.three_shadow_elapsed(
        days, tuple(v * 10000 for v in shadows), mode=mode, noon_basis=g.NOON_BASIS
    )
    assert (
        scaled["elapsed_from_A_midnight_source_days_exact"]
        == result["elapsed_from_A_midnight_source_days_exact"]
    )


def test_clock_midpoint_is_a_comparison_value_and_zi_chu_is_not_modulo_wrapped():
    value = g.source_clock_bin("辰", "初", 3, clock_policy=g.CLOCK_POLICY)
    assert F(value["start_source_day_fraction_exact"]) == F(7, 24) + F(3, 100)
    assert F(value["end_source_day_fraction_exact"]) == F(7, 24) + F(4, 100)
    assert F(value["comparison_midpoint_source_day_fraction_exact"]) == F(49, 150)
    assert not value["midpoint_is_exact_observed_instant"]
    zi = g.source_clock_bin("子", "初", 0, clock_policy=g.CLOCK_POLICY)
    assert F(zi["start_source_day_fraction_exact"]) == F(-1, 24)
    assert F(zi["end_source_day_fraction_exact"]) < 0
    assert value["physical_julian_day"] is None and value["timezone"] is None


@pytest.mark.parametrize("ke", [-1, 4, 5, True, 2.0, "2"])
def test_little_ke_and_implicit_casts_not_fabricated(ke):
    with pytest.raises((TypeError, ValueError)):
        g.source_clock_bin("辰", "初", ke, clock_policy=g.CLOCK_POLICY)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "best_fit", "noon_basis": g.NOON_BASIS},
        {"mode": g.MODES[0], "noon_basis": "UTC_noon"},
    ],
)
def test_no_automatic_mode_or_universal_time_basis(kwargs):
    with pytest.raises(ValueError):
        g.three_shadow_elapsed((0, 7, 8), (F(10), F(11), F(9)), **kwargs)


@pytest.mark.parametrize(
    "days,shadows,mode",
    [
        ((0, 6, 8), (F(10), F(11), F(9)), g.MODES[0]),
        ((0, 2, 30), (F(10), F(11), F(9)), g.MODES[1]),
        ((0, 7, 8), (F(10), F(9), F(9)), g.MODES[0]),
        ((0, 1, 8), (F(10), F(10), F(9)), g.MODES[1]),
        ((0, 0, 8), (F(10), F(11), F(9)), g.MODES[0]),
        ((0, 7, 8), (F(-1), F(11), F(9)), g.MODES[0]),
    ],
)
def test_invalid_measurements_not_sorted_filled_or_silently_interpolated(
    days, shadows, mode
):
    with pytest.raises(ValueError):
        g.three_shadow_elapsed(days, shadows, mode=mode, noon_basis=g.NOON_BASIS)


def test_extrapolation_is_visible_and_does_not_become_bracketed_observation():
    row = g.three_shadow_elapsed(
        (0, 7, 8), (F(20), F(11), F(9)), mode=g.MODES[0], noon_basis=g.NOON_BASIS
    )
    assert not row["equal_shadow_point_inside_adjacent_pair"]
    assert not row["linear_shadow_symmetry_is_exact_solar_motion"]


def test_frozen_references_and_postcomparison_adjudication_are_distinct():
    initial = json.loads((FIXTURES / "reference.json").read_bytes())
    later = json.loads(
        (FIXTURES / "postcomparison-reading-reference.json").read_bytes()
    )
    assert initial["data_sha256"] == hashlib.sha256(g.DATA.read_bytes()).hexdigest()
    assert (
        later["collation_data_sha256"]
        == hashlib.sha256(g.COLLATION_DATA.read_bytes()).hexdigest()
    )
    for reference in [initial, later]:
        for artifact in reference["artifacts"]:
            blob = (FIXTURES / artifact["path"]).read_bytes()
            assert len(blob) == artifact["bytes"]
            assert hashlib.sha256(blob).hexdigest() == artifact["sha256"]
    assert not initial["plan"]["independent_expert_or_blind_holdout"]
    assert later["reading"]["observed_after_first_domain_comparison"]
    assert later["reading"]["initial_literal_matches"] == 74
    assert not later["reading"]["published_half_unit_changed"]
    assert not later["reading"]["source_55_06_constant_replaced"]


def test_initial_failure_and_1279_summer_bin_conflict_survive_full_audit():
    report = audit_gnomon_epoch()
    assert report["matches_within_predeclared_printed_half_unit"] == 74
    assert not report["all_declared_spans_match"]
    corrected = report["declared_postcomparison_NLC_reading"]
    assert corrected["matches_within_predeclared_printed_half_unit"] == 75
    epoch = corrected["derived1280_epoch"]
    assert epoch["mean_within_published_half_unit"]
    assert F(epoch["fixed_original_qiying_source_cycle_day_exact"]) == F("55.06")
    assert F(epoch["derived_cycle_day_exact"]) != F("55.06")
    assert F(epoch["paper_modern_minus_original_nominal_minutes_exact"]) == F("16.272")
    assert not corrected["five_season_means"][3]["mean_inside_printed_clock_bin"]
    assert not report["original_literal_failure_overwritten_or_hidden"]
    assert not report["historical_local_apparent_clock_calibrated_to_TT_or_UT1"]
    assert not report["four_axis_perfect_scores_established"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("declared_A", 72),
        ("printed_A", 71),
        ("observed_after_first_domain_comparison", False),
        ("base_data_sha256", "changed"),
    ],
)
def test_altered_reading_cannot_hide_postcomparison_choice(
    tmp_path, monkeypatch, key, value
):
    source = json.loads(g.COLLATION_DATA.read_bytes())
    source[key] = value
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(source))
    monkeypatch.setattr(g, "COLLATION_DATA", target)
    with pytest.raises(ValueError, match="校读"):
        g.load_gnomon_epoch(g.READING_PROFILE)


def test_collation_provenance_is_loaded_snapshot_not_later_file_hash(
    tmp_path, monkeypatch
):
    target = tmp_path / "reading.json"
    target.write_bytes(g.COLLATION_DATA.read_bytes())
    monkeypatch.setattr(g, "COLLATION_DATA", target)
    model = g.load_gnomon_epoch(g.READING_PROFILE)
    wanted = hashlib.sha256(target.read_bytes()).hexdigest()
    target.write_text("{}")
    assert (
        model.triad("winter1279", 25)["declared_reading"][
            "collation_source_data_sha256"
        ]
        == wanted
    )
