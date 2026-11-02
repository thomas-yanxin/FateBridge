"""Source seeds, unrounded reconstruction and retained contradictory cells."""

import csv
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_solar_generation as subject
from fatebridge.core.guolao_conjunctions import GUJIN_COMPONENTS, solar_correction
from fatebridge.core.guolao_daily_solar import POLICIES
from fatebridge.validation.guolao_solar_generation import audit_solar_generation

FIXTURE = Path(__file__).parent / "fixtures/guolao-solar-generation-v1"


def test_primary_images_plans_and_transcription_frozen_before_generator_output():
    reference = json.loads((FIXTURE / "reference.json").read_text())
    assert (
        hashlib.sha256(subject.DATA.read_bytes()).hexdigest()
        == reference["data_sha256"]
    )
    for item in reference["artifacts"]:
        blob = (FIXTURE / item["path"]).read_bytes()
        assert len(blob) == item["bytes"]
        assert hashlib.sha256(blob).hexdigest() == item["sha256"]
    assert reference["single_unblinded_collator"]
    assert not reference["independent_expert"]
    assert not reference["complete_Gujin40_transcription_claimed"]


def test_selected_checkpoint_fields_keep_literal_precision_and_blanks():
    raw = json.loads(subject.DATA.read_bytes())
    total = blank = 0
    for origin in ("winter", "summer"):
        rows = list(
            csv.DictReader(
                (FIXTURE / f"{origin}-source-generation-checkpoints.csv").open()
            )
        )
        for expected, actual in zip(
            rows, raw["literal_checkpoints"][origin], strict=True
        ):
            assert int(expected["index"]) == actual["index"]
            for field in (
                "combined_difference_fen",
                "correction_increment_fen",
                "cumulative_correction_fen",
            ):
                assert (expected[field] or None) == actual[field]
                total += actual[field] is not None
                blank += actual[field] is None
    assert (total, blank) == (81, 6)
    assert (
        raw["literal_checkpoints"]["winter"][8]["correction_increment_fen"] == "470.273"
    )


@pytest.mark.parametrize(
    "origin,motion,difference,increment",
    [
        ("winter", "1.05108569", "4.9386", "510.8569"),
        ("summer", "0.95151527", "4.4362", "484.8473"),
    ],
)
def test_initial_seed_units_are_ten_thousand_source_fen_per_ancient_du(
    origin, motion, difference, increment
):
    row = subject.load_generator(subject.GENERATOR_PROFILE).row(origin, 0)
    assert F(row["generated_motion_ancient_du_exact"]) == F(motion)
    assert F(row["generated_combined_difference_fen_exact"]) == F(difference)
    assert F(row["generated_correction_increment_fen_exact"]) == F(increment)
    assert row["column_fen_per_ancient_du"] == "10000"
    assert not row["rounding_applied"]


def test_source_disagreements_are_retained_instead_of_tuning_recurrence():
    audit = audit_solar_generation()
    rows = {
        (q["origin"], q["index"], q["field"]): q for q in audit["all_checkpoint_fields"]
    }
    summer1 = rows["summer", 1, "correction_increment_fen"]
    assert summer1["literal_source_string"] == "480.4211"
    assert F(summer1["generated_fen_exact"]) == F("480.4111")
    assert F(summer1["generated_minus_literal_fen_exact"]) == -F(".01")
    winter8 = rows["winter", 8, "correction_increment_fen"]
    assert F(winter8["generated_fen_exact"]) == F("470.8273")
    assert winter8["literal_source_string"] == "470.273"
    assert F(winter8["generated_minus_literal_fen_exact"]) == F(".5543")
    assert audit["fitted_source_cell_emendation"] is None
    assert not audit["rounding_or_quantum_chosen_using_match_count"]


def test_origin_and_terminal_blanks_are_not_fabricated_as_literal_zeros_or_rates():
    generator = subject.load_generator(subject.GENERATOR_PROFILE)
    origin = generator.row("winter", 0)
    assert origin["generated_cumulative_correction_fen_exact"] == "0"
    assert origin["origin_cumulative_is_empty_sum_not_a_transcribed_zero"]
    for name, terminal in [("winter", 89), ("summer", 94)]:
        row = generator.row(name, terminal)
        assert row["generated_motion_ancient_du_exact"] is None
        assert row["generated_correction_increment_fen_exact"] is None
        assert row["generated_combined_difference_fen_exact"] is None
        assert row["next_day_motion_outside_selected_table"]
    assert F(
        generator.row("winter", 89)["generated_cumulative_correction_fen_exact"]
    ) == F("24014.4161")
    assert F(
        generator.row("summer", 94)["generated_cumulative_correction_fen_exact"]
    ) == F("24013.5032")


def test_all185_integer_positions_obey_cubic_identity_without_an_accuracy_score():
    audit = audit_solar_generation()
    rows = audit["all185_recurrence_polynomial_identities"]
    assert len(rows) == 185
    assert all(q["recurrence_minus_polynomial_ancient_du_exact"] == "0" for q in rows)
    assert all(q["identity_is_not_independent_accuracy_acceptance"] for q in rows)
    assert not audit["cell_counts_or_polynomial_identity_used_as_accuracy_score"]
    assert audit["modern_astronomical_reference_comparison"] is None


def test_generated_values_compare_all366_literal_rates_without_rewriting_them():
    model = subject.load_generated_daily_solar(subject.DAILY_PROFILE)
    assert model.literal.segments[1].rates[2] == F(".498519")
    assert model.trajectory.segments[1].rates[2] == F(".99851859")
    assert model.literal.segments[0].rates[38] == F("1.031411")
    assert model.trajectory.segments[0].rates[38] == F("1.03101143")
    audit = audit_solar_generation()
    assert len(audit["all366_literal_motion_cell_comparisons"]) == 366
    assert audit["literal_terminal_motion_blanks_retained"] == 4
    assert all(
        not q["literal_motion_cell_replaced"]
        for q in audit["all366_literal_motion_cell_comparisons"]
    )


def test_audit_does_not_present_generated_rate_sums_as_printed_source_values():
    model = subject.load_generated_daily_solar(subject.DAILY_PROFILE)
    report = model.audit()
    for record, generated, literal in zip(
        report["segments"],
        model.trajectory.segments,
        model.literal.segments,
        strict=True,
    ):
        assert "printed_rates_used" not in record
        assert "literal_rate_sum_du_exact" not in record
        assert "rate_sum_minus_printed_worked_cumulative_du_exact" not in record
        assert record["generated_rates_used"] == generated.days
        assert F(record["generated_rate_sum_du_exact"]) == generated.cumulative(
            generated.days
        )
        assert generated.cumulative(generated.days) != literal.cumulative(literal.days)
        assert F(record["separately_printed_worked_cumulative_du_exact"]) == (
            literal.printed_cumulative
        )
        assert (
            F(record["generated_rate_sum_minus_printed_worked_cumulative_du_exact"])
            == generated.cumulative(generated.days) - literal.printed_cumulative
        )


@pytest.mark.parametrize("policy", POLICIES)
def test_named_year_midnight_and_noon_grid_preserves_all_inputs_and_boundaries(policy):
    model = subject.load_generated_daily_solar(subject.DAILY_PROFILE)
    for n in range(366):
        row = model.day(n, policy=policy)
        assert row["profile_id"] == subject.DAILY_PROFILE
        assert row["anchor_source_profile_id"] == model.literal.profile_id
        assert not row["motion_values_from_literal_Gujin41_42_cells"]
        assert not row["cardinal_anchors_recomputed_from_generated_rates"]
        assert not row["generated_model_automatically_selected_as_best"]
        assert not row["physical_solar_position_validated"]
        assert not row["modern_calendar_date_assigned"]
        assert row["folded_sunrise_argument"] is None
        assert not row["used_in_native_birth_chart"]
        if n < 365:
            assert (
                F(row["noon_unwrapped_from_ji_start_du_exact"])
                - F(row["midnight_unwrapped_from_ji_start_du_exact"])
                == F(row["following_corrected_daily_motion_du_exact"]) / 2
            )
        else:
            assert row["noon_unwrapped_from_ji_start_du_exact"] is None
    for n in model.trajectory.offsets[1:]:
        boundary = model.day(n, policy=policy)["cardinal_boundary_left_limit"]
        if policy == POLICIES[0]:
            assert boundary["left_minus_right_du_exact"] == "0"
        else:
            assert F(boundary["left_minus_right_du_exact"]) != 0


def test_old_Gujin36_piecewise_correction_agrees_with_generated_interior_branches():
    generator = subject.load_generator(subject.GENERATOR_PROFILE)
    for n in range(89):
        source = solar_correction(F(n), profile_id=GUJIN_COMPONENTS)
        assert F(source["signed_correction_ancient_du_exact"]) == generator.branch(
            "winter"
        ).polynomial_correction(n)
    for n in range(94):
        source = solar_correction(F("182.62125") + n, profile_id=GUJIN_COMPONENTS)
        assert -F(source["signed_correction_ancient_du_exact"]) == generator.branch(
            "summer"
        ).polynomial_correction(n)


@pytest.mark.parametrize("value", [True, 1.0, F(1), "1"])
def test_source_indices_do_not_coerce_floats_or_boolean_values(value):
    with pytest.raises(TypeError):
        subject.load_generator(subject.GENERATOR_PROFILE).row("winter", value)


@pytest.mark.parametrize(
    "origin,index", [("winter", -1), ("winter", 90), ("summer", -1), ("summer", 95)]
)
def test_generation_does_not_extend_past_selected_source_domain(origin, index):
    with pytest.raises(ValueError):
        subject.load_generator(subject.GENERATOR_PROFILE).row(origin, index)


def test_no_implicit_generator_profile_origin_or_daily_policy():
    with pytest.raises(ValueError):
        subject.load_generator("best_fit")
    with pytest.raises(ValueError):
        subject.load_generated_daily_solar(subject.GENERATOR_PROFILE)
    with pytest.raises(ValueError):
        subject.load_generator(subject.GENERATOR_PROFILE).row("default", 0)
    with pytest.raises(TypeError):
        subject.load_generated_daily_solar(subject.DAILY_PROFILE).day(0)


@pytest.mark.parametrize(
    "mutation", ["units", "seed", "float", "endpoint", "sign", "coefficients"]
)
def test_invalid_source_parameters_reject_instead_of_falling_back(
    monkeypatch, tmp_path, mutation
):
    raw = json.loads(subject.DATA.read_bytes())
    branch = raw["branches"]["winter"]
    if mutation == "units":
        raw["column_fen_per_ancient_du"] = "100"
    elif mutation == "seed":
        branch["volume40_initial_correction_increment_fen"] = "510.8568"
    elif mutation == "float":
        branch["volume40_initial_combined_difference_fen"] = 4.9386
    elif mutation == "endpoint":
        branch["terminal_cumulative_index"] = True
    elif mutation == "sign":
        branch["motion_sign"] = -1
    else:
        branch["volume36_polynomial_coefficients"].pop()
    file = tmp_path / "source.json"
    file.write_text(json.dumps(raw))
    monkeypatch.setattr(subject, "DATA", file)
    with pytest.raises(ValueError):
        subject.load_generator(subject.GENERATOR_PROFILE)
