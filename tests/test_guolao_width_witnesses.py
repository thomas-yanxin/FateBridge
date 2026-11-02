"""Held whole-row readings and explicit provenance across three width witnesses."""

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core.guolao_classical import MANSIONS
from fatebridge.core.guolao_widths import SOURCES, WidthWitness, load_row

ROOT = Path(__file__).parents[1]
FIXTURE = Path(__file__).parent / "fixtures/guolao-width-witnesses-v1"
REF = json.loads((FIXTURE / "reference.json").read_text())


def test_primary_files_reading_regions_and_runtime_data_are_fingerprinted():
    for item in REF["files"] + [REF["existing_nijl_original"]]:
        assert (
            hashlib.sha256((FIXTURE / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )
    for source, sha in REF["data_sha256"].items():
        assert hashlib.sha256(SOURCES[source].read_bytes()).hexdigest() == sha
    for region in REF["nijl_reading_regions"]:
        assert f'/{region["region"]}/full/0/' in region["url"]
        assert (
            hashlib.sha256((FIXTURE / region["file"]).read_bytes()).hexdigest()
            == region["sha256"]
        )
    pdf = (FIXTURE / "nlc3149.pdf").read_bytes()
    meta = json.loads((FIXTURE / "nlc3149-imageinfo.json").read_text())
    item = meta["query"]["pages"]["124188681"]["imageinfo"][0]
    assert len(pdf) == item["size"] == REF["nlc_original"]["bytes"]
    assert hashlib.sha1(pdf).hexdigest() == item["sha1"] == REF["nlc_original"]["sha1"]
    assert item["pagecount"] == REF["nlc_original"]["pages"] == 71
    assert not REF["independent_second_collator"]
    assert not REF["textual_genealogy_established"]


@pytest.mark.parametrize(
    "source,mansion,held",
    [
        (source, mansion, held)
        for source, held_values in REF["held_widths"].items()
        for mansion, held in zip(MANSIONS, held_values)
    ],
)
def test_all28_cells_in_each_new_witness_have_their_own_held_reading(
    source, mansion, held
):
    row = load_row(source)
    entry = next(
        e
        for e in row.audit(quarter_policy="quarter_marks")["entries"]
        if e["mansion"] == mansion
    )
    assert F(entry["literal_width_du_exact"]) == F(held)
    assert not entry["accepted_modern_width"]
    assert not entry["comparison"]["reference_used_to_emend_source"]


@pytest.mark.parametrize("source", ["nijl", "nlc3149"])
def test_complete_named_rows_retain_exact_differences_and_do_not_close_the_circle(
    source,
):
    row = load_row(source)
    result = row.audit(quarter_policy="quarter_marks")
    original = load_row().audit(quarter_policy="quarter_marks")
    differences = {
        a["mansion"]: F(a["literal_width_du_exact"]) - F(b["literal_width_du_exact"])
        for a, b in zip(result["entries"], original["entries"])
        if a["literal_width_du_exact"] != b["literal_width_du_exact"]
    }
    assert differences == {
        m: F(d) for m, d in REF["held_differences_from_ma591"][source].items()
    }
    assert result["resolved_widths"] == 28
    assert F(result["all28_width_sum_du_exact"]) == F(REF["held_sums"][source])
    assert result["source"]["circle_total_printed_on_this_page"] is None
    for flag in (
        "matches_named_reference_circle",
        "source_circle_accepted",
        "normalized_to_reference_circle",
        "source_widths_emended",
        "complete_luwei_coordinate_profile_built",
        "modern_epoch_calibrated",
        "life_degree_accepted",
    ):
        assert result[flag] is False
    unresolved = row.audit(quarter_policy="uninterpreted_marks")
    assert unresolved["resolved_widths"] == 26
    assert unresolved["all28_width_sum_du_exact"] is None


def test_three_distinct_totals_do_not_choose_a_best_fitting_source():
    assert [
        F(load_row(s).audit(quarter_policy="quarter_marks")["all28_width_sum_du_exact"])
        for s in SOURCES
    ] == list(map(F, ("361.98", "361.96", "361.99")))
    with pytest.raises(ValueError, match="不按周天"):
        load_row("best_fitting_circle")
    assert load_row().source_id == load_row("tohoku").source_id


@pytest.mark.parametrize("source", list(SOURCES))
def test_output_preserves_credit_and_distinguishes_pdf_from_jpeg(source):
    row = load_row(source)
    metadata = row.audit(quarter_policy="quarter_marks")["source"]
    assert metadata["locator"] == row.witness.locator
    assert metadata["credit"] == row.witness.credit
    assert metadata["witness_id"] == row.witness.witness_id
    assert metadata["primary_artifact"]["sha256"] == row.witness.primary_sha256
    if source == "nlc3149":
        assert metadata["image_sha256"] is None
        assert metadata["primary_artifact"]["kind"] == "pdf"
        assert "35" in metadata["locator"] and "36" in metadata["locator"]
    else:
        assert metadata["primary_artifact"]["kind"] == "jpeg"
        assert metadata["image_sha256"] == metadata["primary_artifact"]["sha256"]


@pytest.mark.parametrize("source", list(SOURCES))
def test_passage_bounds_explicitly_identify_cross_witness_comparison(source):
    result = load_row(source).audit_passages(
        quarter_policy="quarter_marks", whole_degree_policy="inherit_column_heading"
    )
    assert result["passages"]["same_witness"] == (source == "tohoku")
    if source != "tohoku":
        assert result["passages"]["comparison_scope"] == "cross_witness_literal_bounds"
        assert (
            result["passages"]["source"]["source_id"] != result["source"]["source_id"]
        )
        assert all(
            e["check_scope"]
            == "cross_witness_literal_bounds_only_not_source_consistency"
            for e in result["passages"]["entries"]
        )
    assert result["passages"]["bounds_passed_is_not_full_profile_acceptance"]
    assert not result["life_degree_accepted"]


@pytest.mark.parametrize(
    "changes",
    [
        {"primary_kind": "pdf_as_image"},
        {"primary_sha256": "x" * 64},
        {"primary_sha256": "1234"},
        {"credit": " "},
        {"locator": ""},
    ],
)
def test_provenance_cannot_hide_missing_attribution_or_an_invalid_hash(changes):
    with pytest.raises(ValueError):
        replace(load_row("nijl").witness, **changes)


def test_pdf_hash_cannot_be_reported_as_an_original_jpeg_hash():
    row = load_row("nlc3149")
    assert isinstance(row.witness, WidthWitness)
    with pytest.raises(ValueError):
        replace(row, image_sha256=row.witness.primary_sha256)
    with pytest.raises(ValueError):
        replace(load_row("nijl"), image_sha256=None)


@pytest.mark.parametrize("source", list(SOURCES))
def test_research_cli_selects_explicit_source_without_changing_the_policy(source):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/audit_guolao_widths.py"),
            "--source",
            source,
            "--quarter-policy",
            "quarter_marks",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == load_row(source).audit(
        quarter_policy="quarter_marks"
    )
