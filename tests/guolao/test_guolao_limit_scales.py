"""Source-oracle checks for local scales; not an end-to-end birth schedule."""

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.guolao_limits import LIMIT_SCALES, limit_scale, limit_scale_audit

ROOT = Path(__file__).parents[2]
FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-limit-scale-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


@pytest.mark.parametrize("entry", REFERENCE["images"])
def test_facsimiles_used_for_new_readings_keep_original_attribution_and_bytes(entry):
    assert (
        hashlib.sha256((FIXTURE / entry["path"]).read_bytes()).hexdigest()
        == entry["sha256"]
    )
    assert "東北大学附属図書館所蔵" in REFERENCE["credit"]


@pytest.mark.parametrize("entry", REFERENCE["image76"]["duration_transcriptions"])
def test_duration_from_facsimile_not_a_generic_twelve_palace_default(entry):
    for palace in entry["palaces"]:
        assert limit_scale(palace).years == Fraction(entry["years_exact"])
        assert limit_scale(palace).palaces == tuple(entry["palaces"])


@pytest.mark.parametrize("entry", REFERENCE["image77"]["selected_first_cell_intervals"])
def test_selected_printed_inclusive_dates_agree_with_nominal_ruler(entry):
    # Source dates have a one-based ordinal year/month/day. A printed end date
    # includes that entire nominal day. This check does not convert to UTC.
    def ordinal(parts):
        year, month, day = parts
        return (year - 1) * 360 + (month - 1) * 30 + day

    start, end = limit_scale(entry["palace"]).cell_interval(entry["cell"])
    assert start * 360 == ordinal(entry["start"]) - 1
    assert end * 360 == ordinal(entry["end_inclusive"])


def test_known_printed_rate_discrepancies_are_visible_and_not_normalized():
    scales = {s["palaces"][0]: s for s in limit_scale_audit()["scales"]}
    assert scales["福德"]["printed_full_span_scale_degrees_exact"] == "299277/10000"
    assert scales["福德"]["printed_full_span_minus_30_exact"] == "-723/10000"
    assert scales["奴仆"]["printed_full_span_scale_degrees_exact"] == "297027/10000"
    assert scales["奴仆"]["printed_full_span_minus_30_exact"] == "-2973/10000"
    assert scales["福德"]["reconstructed_scale_degrees_per_year_exact"] == "30/11"
    assert scales["奴仆"]["reconstructed_scale_degrees_per_year_exact"] == "20/3"
    assert scales["疾厄"]["printed_scale_degrees_per_year_exact"] is None
    assert scales["疾厄"]["printed_rate_text"].endswith("五十分")
    position = limit_scale("福德").position(Fraction(11))
    assert position["limit_scale_degrees_exact"] == "30"
    assert position["printed_rate_scale_degrees_exact"] == "299277/10000"


def test_fifteenth_cell_disagreement_remains_in_source_oracle():
    observed = REFERENCE["image77"]["suspect_cell_preserved"]
    start, end = limit_scale("福德").cell_interval(15)
    assert start == Fraction(77, 15)
    assert end == Fraction(11, 2)
    ordinal = int(start * 360) + 1
    month, day = divmod((ordinal - 1) % 360, 30)
    assert [month + 1, day + 1] == [2, 19]
    assert observed["start_month_day_reading"] == [2, 15]
    assert not REFERENCE["image77"]["full_210_cells_collated"]


@pytest.mark.parametrize("scale", LIMIT_SCALES, ids=lambda s: s.palaces[0])
def test_exact_fractional_boundaries_no_wrap_and_no_fabricated_next_palace(scale):
    tick = scale.years_per_degree
    epsilon = Fraction(1, 10**80)
    assert scale.position(tick - epsilon)["cell"] == 1
    assert scale.position(tick)["cell"] == 2
    assert scale.position(tick + epsilon)["cell"] == 2
    assert scale.position(scale.years - epsilon)["cell"] == 30
    result = scale.position(scale.years)
    assert result["status"] == "local_limit_complete"
    assert result["cell"] is None
    assert result["next_palace"] is None
    for key in ("calendar_date", "birth_age", "mansion"):
        assert result[key] is None
    with pytest.raises(ValueError):
        scale.position(scale.years + epsilon)


def test_manual_nonuniform_local_speed_examples_and_exact_inverse():
    assert (
        limit_scale("官禄").position(Fraction(3, 2))["limit_scale_degrees_exact"] == "3"
    )
    assert (
        limit_scale("相貌").position(Fraction(3, 2))["limit_scale_degrees_exact"]
        == "9/2"
    )
    assert limit_scale("福德").elapsed_years(Fraction(15)) == Fraction(11, 2)
    assert limit_scale("奴仆").elapsed_years(Fraction(15)) == Fraction(9, 4)


@pytest.mark.parametrize("value", [0, 1.0, True, "1", None])
def test_float_and_implicit_input_units_rejected(value):
    scale = limit_scale("官禄")
    with pytest.raises(TypeError):
        scale.position(value)
    with pytest.raises(TypeError):
        scale.elapsed_years(value)


@pytest.mark.parametrize("cell", [0, 31, -1, True, 1.0, "1"])
def test_invalid_table_cells_rejected(cell):
    with pytest.raises((ValueError, TypeError)):
        limit_scale("官禄").cell_interval(cell)


def test_invalid_custom_scale_and_unresolved_life_limit_not_filled():
    with pytest.raises(ValueError):
        limit_scale("命")
    with pytest.raises(TypeError):
        replace(LIMIT_SCALES[0], years=10.0)
    with pytest.raises(ValueError):
        replace(LIMIT_SCALES[0], years=Fraction())
    with pytest.raises(ValueError):
        limit_scale("官禄").position(Fraction(-1))
    with pytest.raises(ValueError):
        limit_scale("官禄").elapsed_years(Fraction(31))


def test_source_six_palace_correction_does_not_become_global_modern_offset():
    note = REFERENCE["image86"]
    assert note["short_palaces"] == ["亥", "戌", "酉", "申", "未", "卯"]
    assert note["rejected_old_examples"] == ["氐二過卯", "畢七過申"]
    audit = limit_scale_audit()
    assert not audit["modern_sky_mapping_accepted"]
    assert not audit["full_limit_schedule_accepted"]
    assert not audit["source_table_fully_collated"]


def test_research_cli_has_no_calendar_or_birth_age_default():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/guolao/audit_guolao_limits.py",
            "--palace",
            "官禄",
            "--elapsed-source-years",
            "1.5",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data["calculation"]["limit_scale_degrees_exact"] == "3"
    assert data["calculation"]["calendar_date"] is None
    assert data["calculation"]["birth_age"] is None
    assert not data["real_world_efficacy_tested"]
    invalid = subprocess.run(
        [
            sys.executable,
            "scripts/guolao/audit_guolao_limits.py",
            "--palace",
            "命",
            "--elapsed-source-years",
            "1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode == 2
    assert not invalid.stdout


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--palace", "福德", "--cell", "15"],
        ["--palace", "福德", "--scale-degrees", "15"],
    ],
)
def test_cli_audit_and_other_input_modes_preserve_ambiguity(args):
    run = subprocess.run(
        [sys.executable, "scripts/guolao/audit_guolao_limits.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(run.stdout)
    assert (
        result["table_discrepancies"][0]["printed_start_month_day_reading"]
        == "二月十五"
    )
    if not args:
        assert result["calculation"] is None
        assert len(result["scales"]) == 7
    elif "--cell" in args:
        assert result["calculation"]["interval_start_source_years_exact"] == "77/15"
        assert result["calculation"]["interval_end_source_years_exact"] == "11/2"
    else:
        assert result["calculation"]["elapsed_source_years_exact"] == "11/2"
        assert result["calculation"]["limit_scale_degrees_exact"] == "15"


@pytest.mark.parametrize(
    "args",
    [
        ["--palace", "官禄"],
        ["--elapsed-source-years", "1"],
        ["--palace", "官禄", "--elapsed-source-years", "1/0"],
        ["--palace", "官禄", "--scale-degrees", "-1"],
    ],
)
def test_cli_rejects_incomplete_or_invalid_local_units(args):
    run = subprocess.run(
        [sys.executable, "scripts/guolao/audit_guolao_limits.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 2
    assert not run.stdout
