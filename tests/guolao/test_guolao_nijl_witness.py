"""Separate primary digital witnesses without filling ambiguous source values."""

import hashlib
import json
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_passages as g

ROOT = Path(__file__).parents[2]
FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-nijl-witness-v1"
REF = json.loads((FIXTURE / "reference.json").read_text())


def test_primary_originals_manifest_attribution_and_reading_aids_are_fingerprinted():
    assert hashlib.sha256(g.NIJL_DATA.read_bytes()).hexdigest() == REF["data_sha256"]
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == REF["manifest_sha256"]
    )
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    canvases = manifest["sequences"][0]["canvases"]
    for entry in REF["images"]:
        assert (
            hashlib.sha256((FIXTURE / entry["file"]).read_bytes()).hexdigest()
            == entry["sha256"]
        )
        canvas = canvases[entry["image"] - 1]
        assert canvas["label"] == entry["canvas_label"]
        assert canvas["@id"] == entry["canvas_id"]
        assert canvas["images"][0]["resource"]["@id"] == entry["url"]
        assert canvas["width"] == 5856 and canvas["height"] == 4032
    for entry in REF["reading_aids"]:
        assert (
            hashlib.sha256((FIXTURE / entry["file"]).read_bytes()).hexdigest()
            == entry["sha256"]
        )
    assert "東北大学附属図書館所蔵" in REF["credit"]
    assert not REF["universal_page_offset_accepted"]
    assert not REF["independent_edition_established"]


@pytest.mark.parametrize("case", REF["held_cases"])
def test_held_cross_witness_arithmetic_never_fills_one_from_the_other(case):
    r = g.compare_nijl_shoushi(whole_degree_policy=case["policy"])
    e = next(e for e in r["entries"] if e["nijl"]["branch"] == case["branch"])
    for actual, expected in [
        (e["nijl"]["literal_unit_sum_du_exact"], case["nijl_literal_sum"]),
        (
            e["earlier_witness"]["literal_unit_sum_du_exact"],
            case["earlier_literal_sum"],
        ),
        (e["literal_difference_du_exact"], case["difference"]),
    ]:
        assert (F(actual) if actual is not None else None) == (
            F(expected) if expected is not None else None
        )
    assert not e["witness_used_to_fill_or_emend_other"]
    assert not e["difference_interpreted_as_modern_coordinate_error"]
    assert not r["earlier_source_rewritten"]
    assert not r["complete_luwei_coordinate_profile_built"]


@pytest.mark.parametrize(
    "policy,resolved", [("explicit_only", 5), ("inherit_column_heading", 11)]
)
def test_all12_cells_and_native_missingness_are_retained(policy, resolved):
    r = g.compare_nijl_shoushi(whole_degree_policy=policy)
    assert len(r["entries"]) == 12
    assert (
        sum(e["nijl"]["literal_unit_sum_du_exact"] is not None for e in r["entries"])
        == resolved
    )
    entries = {e["nijl"]["branch"]: e for e in r["entries"]}
    assert entries["午"]["nijl"]["minute"]["status"] == "unresolved"
    assert entries["午"]["nijl"]["literal_unit_sum_du_exact"] is None
    assert entries["子"]["earlier_witness"]["minute"]["text"] == "六一"
    assert entries["未"]["nijl"]["printed_degree"] is None
    assert entries["未"]["earlier_witness"]["printed_degree"] == 8
    assert all(e["nijl_printed_small_unit"] == "秒" for e in r["entries"])
    assert (
        not r["independent_edition_established"]
        and not r["second_independent_collator"]
    )
    assert not r["modern_epoch_calibrated"] and not r["life_degree_accepted"]
    assert (
        r["old_ruler_example_comparison_reference"]["witness_source_id"]
        == g.load_registry().source_id
    )


def test_small_unit_name_is_preserved_for_missing_and_unresolved_units():
    cell = g.load_registry().cells[0]
    different_unit = replace(
        cell, second=g.FractionalTerm(None, "unresolved", None), second_unit="秒"
    )
    r = different_unit.resolve(whole_degree_policy="inherit_column_heading")
    assert r["unresolved_fractional_units"] == ["秒"]
    assert r["literal_unit_sum_du_exact"] is None
    with pytest.raises(ValueError):
        replace(cell, second_unit="微")


def test_official_catalogue_identifiers_distinguish_holdings_without_certifying_editions():
    identity = REF["catalogue_identity"]
    earlier, nijl = identity["earlier"], identity["nijl"]
    assert (
        hashlib.sha256((FIXTURE / earlier["file"]).read_bytes()).hexdigest()
        == earlier["sha256"]
    )
    assert (
        hashlib.sha256((FIXTURE / nijl["row_file"]).read_bytes()).hexdigest()
        == nijl["row_file_sha256"]
    )
    assert earlier["call_number"] == "MA/591"
    assert earlier["call_number"] in (FIXTURE / earlier["file"]).read_text()
    row = (FIXTURE / nijl["row_file"]).read_text()
    assert "100238879" in row and "藤原文庫４２３２" in row
    assert identity["distinct_holding_records_established"]
    r = g.compare_nijl_shoushi(whole_degree_policy="explicit_only")
    assert r["witness"]["distinct_holding_records_established"]
    assert not r["independent_edition_established"]


@pytest.mark.parametrize("corruption", ["headers", "cells", "calendar", "label"])
def test_incomplete_and_relabelled_witnesses_are_rejected(
    tmp_path, monkeypatch, corruption
):
    data = json.loads(g.NIJL_DATA.read_text())
    if corruption in {"headers", "cells"}:
        data[corruption].pop()
    elif corruption == "calendar":
        data["calendar"] = "tongtian"
    else:
        data["printed_calendar_label"] = "統天"
    path = tmp_path / "corrupt.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(g, "NIJL_DATA", path)
    with pytest.raises(ValueError):
        g.compare_nijl_shoushi(whole_degree_policy="explicit_only")
