"""Named full computational table, literal rates, domain tails and source gaps."""

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core.guolao_classical import SHOUSHI_EQUATORIAL_1281
from fatebridge.core.guolao_huangchi import DATA, load_table, project_reference_mansions

ROOT = Path(__file__).parents[1]
FIXTURE = Path(__file__).parent / "fixtures/guolao-huangchi-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


def test_source_image_container_and_runtime_transcription_have_frozen_fingerprints():
    scan = REFERENCE["primary_scan"]
    assert (
        hashlib.sha256((FIXTURE / scan["extracted_file"]).read_bytes()).hexdigest()
        == scan["extracted_sha256"]
    )
    assert (
        hashlib.sha256(DATA.read_bytes()).hexdigest()
        == REFERENCE["transcription"]["data_sha256"]
    )
    assert all(r["pixels_equal"] for r in scan["render_checks"])
    assert not REFERENCE["transcription"]["secondary_columns_jicha_chalv_collated"]


def test_five_printed_numeric_variants_remain_separate_from_corrected_text():
    a, b = load_table("nlc166"), load_table("wikisource")
    diffs = []
    for i, (x, y) in enumerate(zip(a.rows, b.rows)):
        for field in ["first", "second", "first_rate", "second_rate"]:
            if getattr(x, field) != getattr(y, field):
                diffs.append((i, field))
    assert diffs == [
        (29, "second"),
        (31, "second_rate"),
        (40, "second_rate"),
        (62, "second_rate"),
        (63, "second"),
    ]
    assert a.rows[29].second == F("31.0063") and b.rows[29].second == F("31.0036")
    assert a.rows[62].second_rate == F("0.9527") and b.rows[62].second_rate == F(
        "0.9572"
    )
    assert a.terminal_marker == "九十二"
    assert a.audit()["terminal_first_axis_is_interpretation"]
    assert a.audit()["terminal_literal_marker_conflicts_with_rate_endpoint"]
    assert a.profile_id != b.profile_id and a.rows != b.rows


def test_all_six_printed_rate_discontinuities_are_reported_without_repair():
    result = load_table("nlc166").audit()
    assert {
        str(r["row_index"]): F(r["second_residual_du_exact"])
        for r in result["anchor_rate_residuals"]
    } == {k: F(v) for k, v in REFERENCE["expected_nlc_residuals"].items()}
    assert load_table("wikisource").residuals() == []
    assert result["rows"] == 93 and result["segments"] == 92
    assert not result["rates_replaced_by_anchor_differences"]


@pytest.mark.parametrize(
    "origin,direction,input_degree,output_degree",
    [
        ("solstice", "ecliptic_to_equatorial", "4.5", "4.88695"),
        ("solstice", "equatorial_to_ecliptic", "4.88695", "4.5"),
        ("equinox", "equatorial_to_ecliptic", "4.5", "4.88695"),
        ("equinox", "ecliptic_to_equatorial", "4.88695", "4.5"),
    ],
)
def test_four_direction_roles_against_hand_arithmetic(
    origin, direction, input_degree, output_degree
):
    result = load_table("nlc166").convert(
        F(input_degree), origin=origin, direction=direction
    )
    assert F(result["output_local_accumulation_du_exact"]) == F(output_degree)
    assert result["row_index"] == 4
    assert result["modern_coordinate"] is None
    assert len(result["table_anchor_rate_residuals"]) == 6


def test_rate_is_literal_even_when_the_next_anchor_disagrees():
    r = load_table("nlc166").convert(
        F("62.5"), origin="equinox", direction="equatorial_to_ecliptic"
    )
    # Published row62 has 63.9362 and .9527, not the endpoint-derived .9581.
    assert F(r["output_local_accumulation_du_exact"]) == F("64.41255")
    assert r["status"] == "source_inconsistent_segment"
    assert F(r["target_rate_du_exact"]) == F("0.9527")
    assert F(r["local_anchor_rate_residual"]["second_residual_du_exact"]) == F(
        "-0.0054"
    )


@pytest.mark.parametrize(
    "direction,value,expected",
    [
        ("ecliptic_to_equatorial", "91.155", "91.16865"),
        ("equatorial_to_ecliptic", "91.16865", "91.155"),
    ],
)
def test_fractional_last_interval_uses_both_printed_rates(direction, value, expected):
    result = load_table("nlc166").convert(
        F(value), origin="solstice", direction=direction
    )
    assert result["row_index"] == 91
    assert F(result["output_local_accumulation_du_exact"]) == F(expected)


def test_independent_gujin43_projection_operands_reproduce_raw_quotient_not_forced_text():
    result = load_table("wikisource").convert(
        F("5.3608"), origin="solstice", direction="equatorial_to_ecliptic"
    )
    assert F(result["output_local_accumulation_du_exact"]) == F(53559, 10849)
    assert F(result["output_local_accumulation_du_exact"]) != F("4.9367")
    assert int(F(result["output_local_accumulation_du_exact"]) * 10000) == 49367


@pytest.mark.parametrize("profile", ["nlc166", "wikisource"])
@pytest.mark.parametrize(
    "origin,direction,endpoint",
    [
        ("solstice", "equatorial_to_ecliptic", "91.3125"),
        ("solstice", "ecliptic_to_equatorial", "91.31"),
        ("equinox", "equatorial_to_ecliptic", "91.31"),
        ("equinox", "ecliptic_to_equatorial", "91.3125"),
    ],
)
def test_short_final_segment_and_uncovered_quadrant_are_not_extended(
    profile, origin, direction, endpoint
):
    table = load_table(profile)
    last = table.convert(F(endpoint), origin=origin, direction=direction)
    assert last["row_index"] == 91
    expected = "91.31" if endpoint == "91.3125" else "91.3125"
    assert F(last["output_local_accumulation_du_exact"]) == F(expected)
    for degree in [
        F(endpoint) + F(1, 10**60),
        SHOUSHI_EQUATORIAL_1281.circle_du / 4,
        F(92),
        F(-1, 10**60),
    ]:
        with pytest.raises(ValueError, match="范围"):
            table.convert(degree, origin=origin, direction=direction)
    assert not table.audit()["full_theoretical_quadrant_covered"]


def test_all_corrected_anchors_and_both_sides_preserve_half_open_interval_selection():
    table = load_table("wikisource")
    eps = F(1, 10**60)
    for i, row in enumerate(table.rows):
        at = table.convert(
            row.first, origin="equinox", direction="equatorial_to_ecliptic"
        )
        assert F(at["output_local_accumulation_du_exact"]) == row.second
        assert at["row_index"] == min(i, 91)
        if 0 < i < 92:
            before = table.convert(
                row.first - eps, origin="equinox", direction="equatorial_to_ecliptic"
            )
            after = table.convert(
                row.first + eps, origin="equinox", direction="equatorial_to_ecliptic"
            )
            assert before["row_index"] == i - 1 and after["row_index"] == i
            assert (
                F(before["output_local_accumulation_du_exact"])
                < row.second
                < F(after["output_local_accumulation_du_exact"])
            )


@pytest.mark.parametrize("profile", ["nlc166", "wikisource"])
def test_full_28_mansion_projection_retains_all_four_source_mismatches(profile):
    result = project_reference_mansions(
        profile=profile, winter_mansion="箕", winter_degree_du=F(10)
    )
    assert len(result["boundaries"]) == len(result["widths"]) == 28
    assert result["all_28_boundaries_returned"]
    assert result["rounded_match_count"] == 24
    assert [
        w["mansion"] for w in result["widths"] if not w["rounded_equals_printed"]
    ] == ["氐", "虚", "娄", "毕"]
    assert F(result["raw_width_sum_du_exact"]) == F("365.2575")
    assert not result["printed_ecliptic_table_reproduced"]
    assert not result["life_degree_accepted"] and not result["modern_epoch_calibrated"]


def test_a_mansion_boundary_in_the_table_tail_gap_is_left_unavailable():
    result = project_reference_mansions(
        profile="wikisource", winter_mansion="角", winter_degree_du=F("0.001")
    )
    assert result["boundaries"][0]["ecliptic_relative_du_exact"] is None
    assert result["boundaries"][0]["unavailable_reason"]
    assert result["widths"][0]["raw_width_du_exact"] is None
    assert result["widths"][-1]["raw_width_du_exact"] is None
    assert (
        result["raw_width_sum_du_exact"] is None
        and not result["all_28_boundaries_returned"]
    )


@pytest.mark.parametrize("value", [1.0, True, 1, "1", None])
def test_untyped_local_degrees_are_rejected(value):
    with pytest.raises(TypeError):
        load_table("nlc166").convert(
            value, origin="solstice", direction="equatorial_to_ecliptic"
        )


def test_invalid_frame_name_missing_rate_and_mutable_collection_are_not_silent():
    table = load_table("nlc166")
    with pytest.raises(ValueError):
        load_table("best_fit")
    with pytest.raises(ValueError):
        table.convert(F(1), origin="winter", direction="equatorial_to_ecliptic")
    with pytest.raises(TypeError):
        replace(table, rows=(replace(table.rows[0], second_rate=1.0), *table.rows[1:]))
    with pytest.raises(ValueError):
        replace(table, rows=table.rows[:-1])
    rows = list(table.rows)
    frozen = replace(table, rows=rows)
    rows.pop()
    assert len(frozen.rows) == 93


@pytest.mark.parametrize(
    "args,kind",
    [
        (["--profile", "nlc166"], "audit"),
        (
            [
                "--profile",
                "wikisource",
                "--degree",
                "5.3608",
                "--origin",
                "solstice",
                "--direction",
                "equatorial_to_ecliptic",
            ],
            "local",
        ),
        (
            ["--profile", "nlc166", "--winter-mansion", "箕", "--winter-degree", "10"],
            "projection",
        ),
        (["--profile", "wikisource", "--elapsed-years", "318"], "chain"),
    ],
)
def test_research_command_preserves_selected_source_and_chain(args, kind):
    r = subprocess.run(
        [sys.executable, "scripts/audit_guolao_huangchi.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    value = json.loads(r.stdout)
    assert value["audit"]["segments"] == 92
    if kind == "local":
        assert F(value["calculation"]["output_local_accumulation_du_exact"]) == F(
            53559, 10849
        )
    if kind == "projection":
        assert not value["projection"]["printed_ecliptic_table_reproduced"]
    if kind == "chain":
        assert F(value["source_winter_sun"]["degree_in_mansion_du_exact"]) == F(
            "5.0392"
        )


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--profile", "nlc166", "--degree", "1"],
        ["--profile", "nlc166", "--origin", "solstice"],
        ["--profile", "nlc166", "--winter-degree", "10"],
        ["--profile", "nlc166", "--elapsed-years", "-1"],
        [
            "--profile",
            "nlc166",
            "--degree",
            "NaN",
            "--origin",
            "solstice",
            "--direction",
            "equatorial_to_ecliptic",
        ],
    ],
)
def test_cli_rejects_ambiguous_origins_or_fabricated_defaults(args):
    r = subprocess.run(
        [sys.executable, "scripts/audit_guolao_huangchi.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert r.returncode == 2 and not r.stdout
