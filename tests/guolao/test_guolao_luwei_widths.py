"""Held primary readings, unresolved marks and non-closing source widths."""

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core.guolao_classical import MANSIONS, HistoricalMansions
from fatebridge.core.guolao_coordinates import NLC166_MANSIONS
from fatebridge.core.guolao_widths import DATA, WidthReading, load_row

ROOT = Path(__file__).parents[2]
FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-luwei-widths-v1"
REF = json.loads((FIXTURE / "reference.json").read_text())


def test_fresh_primary_image_metadata_and_corrected_crops_are_fingerprinted():
    assert (
        hashlib.sha256((FIXTURE / REF["source_image"]).read_bytes()).hexdigest()
        == REF["source_image_sha256"]
    )
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == REF["data_sha256"]
    for item in REF["files"]:
        assert (
            hashlib.sha256((FIXTURE / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )
    fetch = json.loads((FIXTURE / "source-fetch.json").read_text())
    assert fetch["matches_frozen_image"]
    assert fetch["fresh_image_sha256"] == REF["source_image_sha256"]
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    assert manifest["items"][25]["id"] == fetch["canvas_id"]
    assert not REF["independent_second_collator"]


@pytest.mark.parametrize(
    "mansion,value", list(zip(MANSIONS, REF["widths_under_quarter_policy"]))
)
def test_all28_held_readings_including_the_large_stomach_difference(mansion, value):
    r = load_row().audit(quarter_policy="quarter_marks")
    e = next(e for e in r["entries"] if e["mansion"] == mansion)
    assert F(e["literal_width_du_exact"]) == F(value)
    assert not e["comparison"]["reference_used_to_emend_source"]
    assert not e["accepted_modern_width"]


def test_full_sum_and_four_panels_do_not_become_an_independent_source_circle():
    r = load_row().audit(quarter_policy="quarter_marks")
    values = [F(e["literal_width_du_exact"]) for e in r["entries"]]
    assert [sum(values[i : i + 7]) for i in range(0, 28, 7)] == list(
        map(F, REF["panel_sums"])
    )
    assert F(r["all28_width_sum_du_exact"]) == F(REF["all28_sum"])
    assert F(r["sum_minus_named_reference_circle_du_exact"]) == F(
        REF["sum_minus_nlc_reference_circle"]
    )
    assert r["matches_named_reference_circle"] is False
    assert r["source"]["circle_total_printed_on_this_page"] is None
    assert not r["source_circle_accepted"]
    assert not r["normalized_to_reference_circle"]
    with pytest.raises(ValueError):
        HistoricalMansions(
            source_id="not_a_valid_nlc_circle",
            coordinate_frame="source_ecliptic",
            circle_du=NLC166_MANSIONS.circle_du,
            widths_du=tuple(values),
        )


def test_uninterpreted_quarter_marks_block_full_sum_and_later_cumulative_values():
    r = load_row().audit(quarter_policy="uninterpreted_marks")
    assert r["resolved_widths"] == 26
    assert F(r["sum_of_resolved_widths_du_exact"]) == F(
        REF["resolved_sum_when_quarter_marks_uninterpreted"]
    )
    assert r["all28_width_sum_du_exact"] is None
    assert r["matches_named_reference_circle"] is None
    entries = {e["mansion"]: e for e in r["entries"]}
    for mansion in ["毕", "轸"]:
        assert entries[mansion]["literal_width_du_exact"] is None
        assert not entries[mansion]["quarter_mark_interpreted"]
    assert (
        entries["毕"]["comparison"][
            "cumulative_difference_before_this_mansion_du_exact"
        ]
        is not None
    )
    assert (
        entries["觜"]["comparison"][
            "cumulative_difference_before_this_mansion_du_exact"
        ]
        is None
    )
    assert F(entries["觜"]["literal_width_du_exact"]) == F(".25")
    assert not entries["觜"]["whole_degree_unit_printed"]


def test_exact_eight_source_differences_and_their_cumulative_effect_are_retained():
    r = load_row().audit(quarter_policy="quarter_marks")
    differences = {
        e["mansion"]: F(e["comparison"]["literal_difference_du_exact"])
        for e in r["entries"]
        if F(e["comparison"]["literal_difference_du_exact"])
    }
    assert differences == {k: F(v) for k, v in REF["differences_from_nlc166"].items()}
    entries = {e["mansion"]: e for e in r["entries"]}
    # Held hand sums: .08-.0075 before 胃; subtract3.45 after 胃.
    assert F(
        entries["胃"]["comparison"][
            "cumulative_difference_before_this_mansion_du_exact"
        ]
    ) == F(".0725")
    assert F(
        entries["昴"]["comparison"][
            "cumulative_difference_before_this_mansion_du_exact"
        ]
    ) == F("-3.3775")
    assert not r["source_widths_emended"]


@pytest.mark.parametrize(
    "quarter_policy,whole_policy,known",
    [
        ("uninterpreted_marks", "explicit_only", 6),
        ("quarter_marks", "explicit_only", 7),
        ("uninterpreted_marks", "inherit_column_heading", 9),
        ("quarter_marks", "inherit_column_heading", 11),
    ],
)
def test_local_passage_bounds_retain_missingness_and_cannot_accept_a_full_profile(
    quarter_policy, whole_policy, known
):
    r = load_row().audit_passages(
        quarter_policy=quarter_policy, whole_degree_policy=whole_policy
    )
    rows = r["passages"]["entries"]
    assert len(rows) == 12
    assert (
        sum(e["printed_unit_sum_within_source_mansion"] is True for e in rows) == known
    )
    nv = next(e for e in rows if e["passage"]["branch"] == "子")
    assert nv["printed_unit_sum_within_source_mansion"] is None
    assert nv["passage"]["minute"]["text"] == "六一"
    assert not r["complete_luwei_coordinate_profile_built"]
    assert not r["modern_epoch_calibrated"] and not r["life_degree_accepted"]


@pytest.mark.parametrize("value", [True, 0.0, F(0), "0"])
def test_implicit_numerical_components_are_rejected(value):
    with pytest.raises(TypeError):
        WidthReading("角", "零", value, None, None)


def test_invalid_or_incomplete_rows_are_not_silently_reordered_or_backfilled():
    row = load_row()
    with pytest.raises(ValueError):
        replace(row, readings=row.readings[:-1])
    with pytest.raises(ValueError):
        replace(row, readings=tuple(reversed(row.readings)))
    with pytest.raises(TypeError):
        replace(row, readings=(None,) * 28)
    mutable = list(row.readings)
    frozen = replace(row, readings=mutable)
    mutable.pop()
    assert len(frozen.readings) == 28
    with pytest.raises(ValueError):
        WidthReading("角", "空", None, None, None)
    with pytest.raises(ValueError):
        WidthReading("角", "非法混合", 1, 25, "半")
    with pytest.raises(ValueError):
        row.audit(quarter_policy="best_fitting_circle")
    with pytest.raises(ValueError):
        row.audit_passages(quarter_policy="quarter_marks", whole_degree_policy="guess")


def test_local_bounds_detect_an_outside_offset_without_repairing_the_width():
    row = load_row()
    changed = tuple(
        WidthReading("胃", "一度", 1, None, None) if r.mansion == "胃" else r
        for r in row.readings
    )
    result = replace(row, readings=changed).audit_passages(
        quarter_policy="quarter_marks", whole_degree_policy="inherit_column_heading"
    )
    entry = next(
        e for e in result["passages"]["entries"] if e["passage"]["branch"] == "酉"
    )
    assert F(entry["passage"]["literal_unit_sum_du_exact"]) == F("3.7456")
    assert F(entry["width"]["literal_width_du_exact"]) == 1
    assert entry["printed_unit_sum_within_source_mansion"] is False
    assert not result["complete_luwei_coordinate_profile_built"]


def test_research_cli_requires_both_independent_policies_for_passage_comparison():
    command = [sys.executable, str(ROOT / "scripts/guolao/audit_guolao_widths.py")]
    result = subprocess.run(
        command + ["--quarter-policy", "quarter_marks", "--compare-passages"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    result = subprocess.run(
        command
        + [
            "--quarter-policy",
            "quarter_marks",
            "--compare-passages",
            "--whole-degree-policy",
            "inherit_column_heading",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    r = json.loads(result.stdout)
    assert F(r["all28_width_sum_du_exact"]) == F("361.98")
    assert len(r["passages"]["entries"]) == 12
