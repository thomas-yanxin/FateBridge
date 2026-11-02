"""Collated equatorial widths, external source arithmetic and frame mixing."""

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core.guolao_classical import (
    MANSIONS,
    SHOUSHI_1281,
    SHOUSHI_EQUATORIAL_1281,
    HistoricalMansions,
)
from fatebridge.core.guolao_coordinates import NLC166_PALACES
from fatebridge.core.guolao_historical import GUJIN_58_PURPLE
from fatebridge.core.guolao_solar import shoushi_winter_sun

ROOT = Path(__file__).parents[1]
FIXTURE = Path(__file__).parent / "fixtures/guolao-shoushi-equatorial-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


@pytest.mark.parametrize(
    "entry,file_key,hash_key",
    [
        ("primary_scan", "artifact", "artifact_sha256"),
        ("independent_digital_worked_example", "excerpt_file", "excerpt_sha256"),
    ],
)
def test_actual_source_artifacts_match_frozen_provenance(entry, file_key, hash_key):
    source = REFERENCE[entry]
    assert (
        hashlib.sha256((FIXTURE / source[file_key]).read_bytes()).hexdigest()
        == source[hash_key]
    )


def test_all_28_equatorial_widths_and_four_subtotals_against_scan_transcription():
    source = REFERENCE["source_equatorial_table"]
    table = SHOUSHI_EQUATORIAL_1281
    assert "".join(MANSIONS) == source["mansion_names"]
    assert table.widths_du == tuple(map(F, source["widths_du"]))
    assert table.circle_du == F(source["circle_du"])
    assert [sum(table.widths_du[i : i + 7], F()) for i in range(0, 28, 7)] == list(
        map(F, source["quadrant_subtotals_du"])
    )
    assert sum(table.widths_du, F()) == table.circle_du
    assert table.coordinate_frame == "source_equatorial"
    assert table.widths_du[MANSIONS.index("虚")] == F("8.9575")
    assert SHOUSHI_1281.widths_du[MANSIONS.index("虚")] == F("9.0075")
    assert GUJIN_58_PURPLE.widths_du[MANSIONS.index("虚")] == F("9.0064")


@pytest.mark.parametrize("frame", ["source_equatorial", "unspecified"])
def test_same_circle_does_not_authorize_equatorial_widths_in_ecliptic_profile(frame):
    # This constructor succeeded before the repair, then labelled the resulting
    # intervals source_ecliptic regardless of the actual underlying table.
    table = replace(SHOUSHI_EQUATORIAL_1281, coordinate_frame=frame)
    assert table.circle_du == NLC166_PALACES.table.circle_du
    with pytest.raises(ValueError, match="赤道或未指定"):
        replace(NLC166_PALACES, table=table)


def test_unknown_coordinate_frame_is_not_silently_accepted():
    with pytest.raises(ValueError, match="坐标系"):
        replace(SHOUSHI_1281, coordinate_frame="modern_ra_degrees")
    unspecified = HistoricalMansions("synthetic_exact", F(28), (F(1),) * 28)
    assert unspecified.coordinate_frame == "unspecified"
    assert unspecified.locate(F(3, 2)) == ("亢", F(1, 2))
    assert NLC166_PALACES.audit()["coordinate_frame"] == "source_ecliptic"
    assert NLC166_PALACES.locate(F())["coordinate_frame"] == "source_ecliptic"


def test_elapsed_318_complete_chain_against_independent_printed_digital_example():
    expected = REFERENCE["independent_digital_worked_example"]
    result = shoushi_winter_sun(expected["elapsed_years"])
    for actual, source in [
        ("effective_year_days_exact", "effective_year_days"),
        ("zhongji_days_exact", "zhongji_days"),
        ("accumulated_du_exact", "accumulated_du"),
        ("remainder_period_du_exact", "remainder_period_du"),
        ("remainder_from_xu6_du_exact", "remainder_from_xu6_du"),
        ("degree_in_mansion_du_exact", "degree_du"),
    ]:
        assert F(result[actual]) == F(expected[source])
    assert result["mansion"] == expected["mansion"]
    assert result["winter_sexagenary_day"] == "丙午"
    assert F(result["winter_fraction_of_day_exact"]) == F("0.0796")
    assert result["complete_revolutions"] == 318


def test_following_winter_matches_source_without_refitting_an_offset():
    expected = REFERENCE["independent_digital_worked_example"]
    result = shoushi_winter_sun(expected["next_elapsed_years"])
    assert result["mansion"] == expected["next_mansion"]
    assert F(result["degree_in_mansion_du_exact"]) == F(expected["next_degree_du"])


def test_wrong_circle_and_wrong_frame_have_material_source_degree_errors():
    table = SHOUSHI_EQUATORIAL_1281
    xu_origin = sum(table.widths_du[: MANSIONS.index("虚")], F()) + 6
    at_epoch = shoushi_winter_sun(0)
    assert at_epoch["mansion"] == "箕"
    assert F(at_epoch["degree_in_mansion_du_exact"]) == F("10")
    other_origin = sum(SHOUSHI_1281.widths_du[: MANSIONS.index("虚")], F()) + 6
    assert SHOUSHI_1281.locate(other_origin + F("315.1075")) == ("箕", F("6.93"))
    result = shoushi_winter_sun(318)
    wrong_phase = F(result["accumulated_du_exact"]) % table.circle_du
    assert table.locate(xu_origin + wrong_phase) == ("箕", F("5.1346"))
    assert F("5.1346") - F(result["degree_in_mansion_du_exact"]) == F("0.0954")


def test_reference_circle_and_annual_period_are_not_normalized_to_hide_difference():
    result = shoushi_winter_sun(318)
    assert result["coordinate_frame"] == "source_equatorial"
    assert F(result["mansion_reference_circle_du_exact"]) == F("365.2575")
    assert F(result["period_minus_reference_circle_du_exact"]) == F("0.0003")
    assert result["mansion_widths_redated"] is False
    assert not result["modern_epoch_calibrated"]
    assert not result["modern_calendar_date_assigned"]
    assert not result["used_in_native_birth_chart"]
    assert (
        result["modern_right_ascension"] is None and result["modern_longitude"] is None
    )
    assert not result["life_degree_accepted"]
    assert REFERENCE["independent_digital_worked_example"][
        "redated_table_internal_difference_not_resolved"
    ]


def test_generic_mansion_reduction_does_not_assume_all_winters_stay_in_ji():
    result = shoushi_winter_sun(745)
    # Independent subtraction of the fixed printed arc to 箕初:
    # 302.8895 - 305.1075 = -2.2180; 尾19.10 - 2.2180 = 16.8820.
    assert result["mansion"] == "尾"
    assert F(result["degree_in_mansion_du_exact"]) == F("16.882")


@pytest.mark.parametrize("value", [True, False, 318.0, F(318), "318", None])
def test_source_elapsed_count_requires_explicit_integer_years(value):
    with pytest.raises(TypeError):
        shoushi_winter_sun(value)


@pytest.mark.parametrize("value", [-1, 365242500])
def test_out_of_scope_upward_reckoning_or_nonpositive_year_length_is_rejected(value):
    with pytest.raises(ValueError):
        shoushi_winter_sun(value)


@pytest.mark.parametrize("elapsed", [0, 318, 319])
def test_research_cli_replays_the_same_domain_chain(elapsed):
    run = subprocess.run(
        [
            sys.executable,
            "scripts/audit_guolao_solar.py",
            "--elapsed-years",
            str(elapsed),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(run.stdout) == shoushi_winter_sun(elapsed)


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--elapsed-years", "-1"],
        ["--elapsed-years", "318.5"],
        ["--elapsed-years", "NaN"],
    ],
)
def test_research_cli_rejects_unprovided_fractional_or_invalid_elapsed_input(arguments):
    run = subprocess.run(
        [sys.executable, "scripts/audit_guolao_solar.py", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 2 and not run.stdout
