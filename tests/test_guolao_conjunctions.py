"""Primary angular arithmetic and full, deliberately unamended paper audit."""

import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_conjunctions as c
from fatebridge.core.guolao_historical import shoushi_winter_cycle

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/guolao-conjunctions-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
G = c.GUJIN_COMPONENTS
L = c.LI_1996


def test_named_constants_and_primary_scan_bytes_are_pinned():
    for row in REFERENCE["artifacts"]:
        assert (
            hashlib.sha256((FIXTURE / row["path"]).read_bytes()).hexdigest()
            == row["sha256"]
        )
    assert (
        json.loads(c.DATA.read_bytes())["profiles"] == REFERENCE["profiles_transcribed"]
    )
    assert REFERENCE["source_images_collated"]
    assert not REFERENCE["second_independent_collator"]
    assert not REFERENCE["paper"]["pdf_bundled"]
    assert not any(REFERENCE["acceptance"].values())


@pytest.mark.parametrize("profile", [G, L])
@pytest.mark.parametrize("phase", [F(), F("182.62125"), F("365.2425"), F("-365.2425")])
def test_two_solstices_and_full_cycles_have_zero_solar_correction(profile, phase):
    value = c.solar_correction(phase, profile_id=profile)
    assert F(value["signed_correction_ancient_du_exact"]) == 0
    assert value["modern_degrees"] is None


@pytest.mark.parametrize(
    "phase,expected_phase,limit,coeff",
    [
        ("20", "盈", "初", "24600"),
        ("100", "盈", "末", "22100"),
        ("200", "縮", "初", "22100"),
        ("350", "縮", "末", "24600"),
    ],
)
def test_all_four_primary_solar_branches(phase, expected_phase, limit, coeff):
    value = c.solar_correction(F(phase), profile_id=G)
    assert (value["phase"], value["limit"]) == (expected_phase, limit)
    assert value["polynomial_coefficients"][1] == coeff
    assert (F(value["signed_correction_ancient_du_exact"]) > 0) == (
        expected_phase == "盈"
    )


@pytest.mark.parametrize("cut", [F("88.909225"), F("276.333275")])
def test_printed_initial_solar_endpoint_and_both_sides(cut):
    epsilon = F(1, 10**12)
    assert c.solar_correction(cut - epsilon, profile_id=G)["limit"] == "初"
    assert c.solar_correction(cut, profile_id=G)["limit"] == "初"
    assert c.solar_correction(cut + epsilon, profile_id=G)["limit"] == "末"


def test_paper_coefficient_is_not_silently_changed_to_fit_table():
    phase = F("97.9993")
    g = c.solar_correction(phase, profile_id=G)
    p = c.solar_correction(phase, profile_id=L)
    assert g["polynomial_coefficients"][1] == "22100"
    assert p["polynomial_coefficients"][1] == "21000"
    # Independent difference identity: coefficient difference * argument squared.
    expected = F(1100, 100_000_000) * F("84.62195") ** 2
    assert (
        F(p["signed_correction_ancient_du_exact"])
        - F(g["signed_correction_ancient_du_exact"])
        == expected
    )
    assert abs(F(g["signed_correction_ancient_du_exact"]) - F("2.3754")) < F(".0001")
    assert abs(F(p["signed_correction_ancient_du_exact"]) - F("2.3754")) > F(".07")


def test_primary_lunar_polynomial_at_one_limit_is_exact_signed_ancient_du():
    fast = c.lunar_correction(F(5, 61), profile_id=G)  # 1/12.2 day
    slow = c.lunar_correction(F("13.7773") + F(5, 61), profile_id=G)
    assert F(fast["polynomial_argument_limits_exact"]) == 1
    assert F(fast["signed_correction_ancient_du_exact"]) == -F(".11081575")
    assert F(slow["signed_correction_ancient_du_exact"]) == F(".11081575")


def test_primary_12_point_2_and_168_do_not_close_and_are_not_normalized():
    at = c.lunar_correction(F("13.7773"), profile_id=G)
    assert at["phase"] == "疾"  # literal 轉中已下
    assert F(at["half_month_limit_closure_residual_exact"]) == F(".08306")
    assert F(at["polynomial_argument_limits_exact"]) == -F(".08306")
    assert not at["argument_within_printed_limits"]
    assert at["signed_correction_ancient_du_exact"] is None
    assert not at["limit_clipped_or_rescaled"]
    after = c.lunar_correction(F("13.7773") + F(1, 10**12), profile_id=G)
    assert after["phase"] == "遲"
    assert after["argument_within_printed_limits"]


def test_paper_terminal_model_also_reports_its_small_overlap_without_clipping():
    value = c.lunar_correction(F("6.8881"), profile_id=L)
    assert F(value["polynomial_argument_limits_exact"]) > 84
    assert value["signed_correction_ancient_du_exact"] is None
    assert not value["limit_clipped_or_rescaled"]


@pytest.mark.parametrize(
    "boundary,at,after",
    [
        ("6.6420", 22, 23),
        ("7.0520", 23, 24),
        ("20.4193", 24, 25),
        ("20.8293", 25, 26),
    ],
)
def test_all_published_velocity_piece_boundaries_and_either_side(boundary, at, after):
    point = F(boundary)
    epsilon = F(1, 10**12)
    assert c.li_1996_lunar_velocity(point - epsilon)["equation_number"] == at
    assert c.li_1996_lunar_velocity(point)["equation_number"] == at
    assert c.li_1996_lunar_velocity(point + epsilon)["equation_number"] == after


def test_published_velocity_units_and_constant_bands_are_not_modern_daily_speed():
    assert F(c.li_1996_lunar_velocity(F())["velocity_ancient_du_per_limit_exact"]) == F(
        "1.20701575"
    )
    for phase in [F(7), F("20.5")]:
        v = c.li_1996_lunar_velocity(phase)
        assert F(v["velocity_ancient_du_per_limit_exact"]) == F("1.0962")
        assert F(v["limit_duration_days_exact"]) == F(".082")
        assert not v["original_gujin_discrete_table_reconstructed"]
    assert F("13.36875") * F(".082") != F("1.0962")


def test_complete_published_first_conjunction_and_820_unit_conversion():
    middle = shoushi_winter_cycle(19).zhongji_days
    value = c.source_conjunction(middle, 0, profile_id=L)
    assert F(value["runyu_days_exact"]) == F("20.123145")
    assert F(value["mean_conjunction_day_cycle_exact"]) == F("14.544355")
    assert F(value["lunar"]["anomaly_phase_days_exact"]) == F("16.300255")
    total_du = F(value["solar"]["signed_correction_ancient_du_exact"]) + F(
        value["lunar"]["signed_correction_ancient_du_exact"]
    )
    velocity = F(value["lunar_velocity"]["velocity_ancient_du_per_limit_exact"])
    assert F(value["time_correction_days_exact"]) == 820 * total_du / (
        10_000 * velocity
    )
    assert abs(F(value["research_conjunction_day_cycle_exact"]) - F("14.7167")) < F(
        ".0001"
    )
    assert not value["sunrise_shift_applied_to_new_moon"]


def test_primary_components_never_borrow_paper_velocity_or_emit_a_calendar_date():
    middle = shoushi_winter_cycle(318).zhongji_days
    for index in [0, 2, 4, 12, 24]:
        g = c.source_conjunction(middle, index, profile_id=G)
        assert g["lunar_velocity"] is None
        assert g["time_correction_days_exact"] is None
        assert g["research_conjunction_day_cycle_exact"] is None
        assert g["lunar_date"] is None
        assert not g["true_new_moon_calibrated"]
        assert not g["intercalation_reconstructed"]
        assert not g["modern_epoch_calibrated"]
        assert not g["used_in_native_birth_chart"]


@pytest.mark.parametrize("index,shift,day", [(2, 1, "戊寅"), (9, -1, "癸卯")])
def test_true_correction_crossing_midnight_uses_unwrapped_day_total(index, shift, day):
    value = c.source_conjunction(
        shoushi_winter_cycle(19).zhongji_days, index, profile_id=L
    )
    assert value["midnight_displacement_from_mean_days"] == shift
    assert value["research_conjunction_sexagenary_day"] == day
    assert value["lunar_date"] is None
    assert not value["true_new_moon_calibrated"]


def _command(monkeypatch, capsys, args):
    script = ROOT / "scripts/audit_guolao_conjunctions.py"
    monkeypatch.setattr(sys, "argv", [str(script), *args])
    assert runpy.run_path(str(script))["main"]() == 0
    return json.loads(capsys.readouterr().out)


def test_all_28_paper_rows_are_audited_including_formula_and_identity_failures(
    monkeypatch, capsys
):
    report = _command(
        monkeypatch,
        capsys,
        ["--paper-table", str(FIXTURE / "li-zhang-1996-table1.csv")],
    )
    assert len(report["rows"]) == 28
    assert report["rows_exceeding_display_screen"] == [
        4,
        5,
        6,
        8,
        9,
        10,
        13,
        14,
        17,
        18,
        19,
        20,
        21,
        22,
    ]
    assert report["printed_identity_residual_rows_over_screen"] == [13, 14]
    assert F(
        report["rows"][13]["printed_mean_plus_correction_identity_residual_days_exact"]
    ) == F(".1316")
    assert F(
        report["rows"][14]["printed_mean_plus_correction_identity_residual_days_exact"]
    ) == F(".0100")
    assert not report["all_published_values_exact"]
    assert not report["all_published_values_within_display_screen"]
    assert not report["screen_is_scientific_accuracy_threshold"]
    assert all(
        not r["comparison_substituted_into_paper_formula"] for r in report["rows"]
    )
    assert not report["modern_calendar_calibrated"]
    assert not report["real_world_predictive_validity_tested"]


def test_the_38_old_complete_stdout_values_remain_byte_identical(monkeypatch, capsys):
    expected = json.loads((FIXTURE / "before-38-cli-stdout.json").read_text())
    assert len(expected) == 38
    for key, stdout in expected.items():
        script, params = key.split(":", 1)
        args = params.split() if " " in params else params.split(":")
        path = ROOT / "scripts" / script
        monkeypatch.setattr(sys, "argv", [str(path), *args])
        assert runpy.run_path(str(path))["main"]() == 0
        assert capsys.readouterr().out == stdout


@pytest.mark.parametrize(
    "args",
    [
        ["--elapsed-years", "19"],
        ["--source-year", "1300"],
        ["--winter-year", "1299"],
        ["--zhongji-days", "6939.6075"],
    ],
)
def test_real_cli_year_paths_preserve_named_profile_and_index(
    monkeypatch, capsys, args
):
    result = _command(
        monkeypatch, capsys, [*args, "--profile", L, "--lunation-index", "0"]
    )
    assert F(result["zhongji_days_exact"]) == F("6939.6075")
    assert result["profile_id"] == L
    assert result["lunation_index"] == 0
    assert result["lunar_date"] is None


@pytest.mark.parametrize("bad", [0, True, "1", 2451545.0, None])
def test_fraction_units_required(bad):
    for fn in [c.solar_correction, c.lunar_correction]:
        with pytest.raises(TypeError, match="Fraction"):
            fn(bad, profile_id=G)
    with pytest.raises(TypeError, match="Fraction"):
        c.li_1996_lunar_velocity(bad)
    with pytest.raises(TypeError, match="Fraction"):
        c.source_conjunction(bad, 0, profile_id=G)


@pytest.mark.parametrize("bad", [None, "auto", "shoushi", 1, []])
def test_profile_cannot_be_guessed(bad):
    with pytest.raises(ValueError, match="具名"):
        c.source_conjunction(F(), 0, profile_id=bad)


@pytest.mark.parametrize("bad", [True, "1", F(1), 1.0, None])
def test_index_is_an_explicit_integer(bad):
    with pytest.raises(TypeError, match="整数"):
        c.source_conjunction(F(), bad, profile_id=G)


@pytest.mark.parametrize("middle,index", [(F(-1), 0), (F(), -1)])
def test_negative_lower_reckoning_is_not_inferred(middle, index):
    with pytest.raises(ValueError, match="非负"):
        c.source_conjunction(middle, index, profile_id=G)


@pytest.mark.parametrize(
    "field,value", [("runying_days", "20.1850"), ("terminal_limit_method", "guess")]
)
def test_parameter_mixing_or_unknown_limit_algorithm_fails_closed(
    tmp_path, monkeypatch, field, value
):
    data = json.loads(c.DATA.read_bytes())
    data["profiles"][G][field] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(c, "DATA", path)
    with pytest.raises(ValueError):
        c.source_conjunction(F(), 0, profile_id=G)


@pytest.mark.parametrize(
    "args",
    [
        ["--elapsed-years", "19"],
        ["--elapsed-years", "19", "--profile", L],
        ["--elapsed-years", "19", "--lunation-index", "0"],
        ["--elapsed-years", "19", "--profile", L, "--lunation-index", "-1"],
        ["--zhongji-days", "nan", "--profile", L, "--lunation-index", "0"],
        ["--paper-table", "missing.csv", "--profile", G],
    ],
)
def test_cli_requires_explicit_mode_profile_and_index(monkeypatch, capsys, args):
    with pytest.raises(SystemExit) as error:
        _command(monkeypatch, capsys, args)
    assert error.value.code == 2
    assert not capsys.readouterr().out
