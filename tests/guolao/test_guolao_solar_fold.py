"""Original witnesses, exact fold branches and retained short-table gaps."""

import csv
import hashlib
import json
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_solar_fold as subject
from fatebridge.validation.guolao_solar_fold import audit_source_solar_fold

FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-solar-fold-v1"
ORIGIN = "explicit arithmetic case, not a verified date"


def test_original_images_official_html_and_constants_keep_source_fingerprints():
    ref = json.loads((FIXTURE / "reference.json").read_text())
    assert hashlib.sha256(subject.DATA.read_bytes()).hexdigest() == ref["data_sha256"]
    for item in ref["artifacts"]:
        blob = (FIXTURE / item["path"]).read_bytes()
        assert len(blob) == item["bytes"]
        assert hashlib.sha256(blob).hexdigest() == item["sha256"]
    assert ref["official_image_ids_observed_in_viewer_not_guessed"]
    assert not ref["independent_expert"]
    assert not ref["Qizheng_full_night_table_transcribed"]
    with (FIXTURE / "constants-transcription.csv").open() as f:
        rows = {q["constant"]: q for q in csv.DictReader(f)}
    assert rows["half_year"]["source_unit"] == "source_day"
    assert rows["sui_quadrant"]["source_unit"] == "historical_du"
    assert rows["sui_quadrant"]["numeric_string"] == "91.310625"
    assert "在歲象限" in (FIXTURE / "sillok-fold-official.html").read_text()


def test_source_year_and_celestial_quadrants_are_distinct_without_half_period_repair():
    early = subject.load_source_fold(subject.PROFILES[0]).audit()
    candidate = subject.load_source_fold(subject.PROFILES[1]).audit()
    assert (
        early["source_half_year_days_exact"] == candidate["source_half_year_days_exact"]
    )
    assert F(early["quadrant_threshold_du_exact"]) == F("91.310625")
    assert F(candidate["quadrant_threshold_du_exact"]) == F("91.314375")
    assert early["threshold_right_minus_left_du_exact"] == "0"
    assert F(candidate["threshold_right_minus_left_du_exact"]) == -F(".0075")
    assert F(early["half_circle_minus_half_year_numeric_exact"]) == F(".0075")
    assert early["source_explicitly_says_sui_quadrant"]
    assert candidate["unqualified_Gujin_quadrant_reading_is_hypothesis"]
    assert not candidate["half_year_replaced_by_half_circle_to_force_symmetry"]
    assert not early["source_numeric_rule_is_physical_day_degree_equivalence"]


@pytest.mark.parametrize("profile", subject.PROFILES)
def test_threshold_equality_and_right_limit_follow_the_declared_reading(profile):
    model = subject.load_source_fold(profile)
    epsilon = F(1, 100000000)
    at = model.fold(model.threshold, origin_reference=ORIGIN)
    after = model.fold(model.threshold + epsilon, origin_reference=ORIGIN)
    assert at["initial_or_final_limit"] == "initial"
    assert after["initial_or_final_limit"] == "final"
    assert F(at["folded_table_argument_du_exact"]) == model.threshold
    assert (
        F(after["folded_table_argument_du_exact"])
        == model.half_year - model.threshold - epsilon
    )
    assert not at["origin_reference_independently_verified"]
    assert not at["solar_side_inferred_from_fold"]


@pytest.mark.parametrize("profile", subject.PROFILES)
def test_exact_half_periods_and_one_source_cycle_are_not_modern_angle_modulo(profile):
    model = subject.load_source_fold(profile)
    for value, reductions in [(F(), 0), (model.half_year, 1), (2 * model.half_year, 2)]:
        row = model.fold(value, origin_reference=ORIGIN)
        assert row["half_period_reductions"] == reductions
        assert row["folded_table_argument_du_exact"] == "0"
    for delta in (-F(1, 10000), F(1, 10000)):
        assert F(
            model.fold(model.half_year + delta, origin_reference=ORIGIN)[
                "folded_table_argument_du_exact"
            ]
        ) == abs(delta)
    assert F(
        model.fold(F(100), origin_reference=ORIGIN)["folded_table_argument_du_exact"]
    ) == F("82.62125")


def test_short_table_gap_retains_requested_origin_side_basis_and_unavailable_result():
    model = subject.load_source_fold(subject.PROFILES[0])
    result = model.sunrise(
        model.threshold,
        origin_reference=ORIGIN,
        table_profile="yuanshi55_digital",
        solar_side="outside",
        basis="dadu_source_table",
    )
    assert result["status"] == "folded_argument_outside_printed_table"
    assert F(result["folded_minus_table_terminal_du_exact"]) == F(".000625")
    assert result["table_result"] is None
    assert result["usable_source_sunrise_fraction_exact"] is None
    assert result["solar_side"] == "outside"
    assert result["basis"] == "dadu_source_table"
    assert result["fold"]["origin_reference"] == ORIGIN
    assert not result["table_gap_filled_or_fold_clamped"]


def test_cross_witness_sunrise_is_labeled_and_keeps_the_Dadu_table_values():
    model = subject.load_source_fold(subject.PROFILES[0])
    result = model.sunrise(
        model.threshold,
        origin_reference=ORIGIN,
        table_profile="gujin37_siku",
        solar_side="outside",
        basis="dadu_source_table",
    )
    assert result["status"] == "calculated"
    assert not result["fold_and_table_from_same_work"]
    assert not result["Qizheng_full_night_table_transcribed_or_used"]
    assert result["cross_witness_or_hypothesis_comparison_not_full_original_replay"]
    # Independent decimal calculation from the literal row91 values.
    night = Decimal("2502.79") - Decimal(".310625") * Decimal("8.95")
    assert night == Decimal("2500.00990625")
    clock = result["table_result"]["source_clock"]
    assert F(clock["source_half_night_fen_exact"]) == F(night)
    assert not result["source_day_origin_location_and_clock_relation_accepted"]
    assert not result["physical_sunrise_validated"]
    assert not result["phase_day_or_birth_chart_backfilled"]


def test_celestial_quadrant_candidate_keeps_its_gap_and_branch_jump():
    model = subject.load_source_fold(subject.PROFILES[1])
    at = model.sunrise(
        model.threshold,
        origin_reference=ORIGIN,
        table_profile="gujin37_siku",
        solar_side="outside",
        basis="dadu_source_table",
    )
    assert not at["table_argument_covered"]
    assert F(at["folded_minus_table_terminal_du_exact"]) == F(".001875")
    after = model.sunrise(
        model.threshold + F(1, 100000000),
        origin_reference=ORIGIN,
        table_profile="gujin37_siku",
        solar_side="outside",
        basis="dadu_source_table",
    )
    assert after["table_argument_covered"]
    assert after["fold_and_table_from_same_work"]
    assert after["fold"]["unqualified_Gujin_quadrant_reading_is_hypothesis"]


def test_all104_directed_probe_records_include_failures_without_source_acceptance():
    audit = audit_source_solar_fold()
    rows = [
        q
        for profile in audit["profiles"].values()
        for q in profile["all_directed_probes"]
    ]
    assert len(rows) == 104
    assert any(not q["table_argument_covered"] for q in rows)
    assert all(q["solar_side"] in ("inside", "outside") for q in rows)
    assert not audit["best_profile_selected_by_table_coverage_or_continuity"]
    assert not audit["Qizheng_witness_used_to_emend_Gujin_text"]
    assert not audit["four_axis_perfect_scores_established"]


@pytest.mark.parametrize("value", [0, True, 1.0, "1", Decimal(1)])
def test_input_accumulation_requires_an_explicit_fraction(value):
    with pytest.raises(TypeError):
        subject.load_source_fold(subject.PROFILES[0]).fold(
            value, origin_reference=ORIGIN
        )


@pytest.mark.parametrize(
    "value", [F(-1, 10000), F("365.24250001"), F("365.25"), F(2451545)]
)
def test_previous_cycle_and_modern_JD_are_not_silently_reduced(value):
    with pytest.raises(ValueError):
        subject.load_source_fold(subject.PROFILES[0]).fold(
            value, origin_reference=ORIGIN
        )


@pytest.mark.parametrize("reference", [None, "", "  ", False])
def test_origin_is_required_even_when_the_fold_number_can_be_computed(reference):
    with pytest.raises(ValueError):
        subject.load_source_fold(subject.PROFILES[0]).fold(
            F(1), origin_reference=reference
        )


@pytest.mark.parametrize("mutation", ["float", "quarter", "half_circle", "night_hash"])
def test_changed_source_parameters_do_not_fall_back_or_repair(
    monkeypatch, tmp_path, mutation
):
    raw = json.loads(subject.DATA.read_bytes())
    if mutation == "float":
        raw["source_half_year_days"] = 182.62125
    elif mutation == "quarter":
        raw["source_sui_quadrant_du"] = "91.314375"
    elif mutation == "half_circle":
        raw["source_half_circle_du"] = "182.62125"
    else:
        raw["source_night_table_data_sha256"] = "0" * 64
    file = tmp_path / "source.json"
    file.write_text(json.dumps(raw))
    monkeypatch.setattr(subject, "DATA", file)
    with pytest.raises(ValueError):
        subject.load_source_fold(subject.PROFILES[0]).sunrise(
            F(1),
            origin_reference=ORIGIN,
            table_profile="gujin37_siku",
            solar_side="outside",
            basis="dadu_source_table",
        )


def test_no_implicit_profile_solar_side_or_location():
    with pytest.raises(ValueError):
        subject.load_source_fold("best")
    model = subject.load_source_fold(subject.PROFILES[0])
    with pytest.raises(TypeError):
        model.fold(F(1))
    for profile, side, basis in [
        ("Qizheng_table", "outside", "dadu_source_table"),
        ("gujin37_siku", "auto", "dadu_source_table"),
        ("gujin37_siku", "outside", "birthplace"),
    ]:
        with pytest.raises(ValueError):
            model.sunrise(
                F(1),
                origin_reference=ORIGIN,
                table_profile=profile,
                solar_side=side,
                basis=basis,
            )
