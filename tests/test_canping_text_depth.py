"""Actual numbered columns, correction provenance and local missing-text facts."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.canping import (
    _lookup,
    _tiaowen,
    _verses,
    build_snapshot_text,
    calculate,
    compute_number,
    liunian_series,
    nayin_element,
)
from fatebridge.core.canping_texts import (
    COLLATION_PATH,
    _loaded,
    collation_summary,
    lookup_record,
)
from fatebridge.core.requests.divination import CanpingRequest

ROOT = Path(__file__).parent / "fixtures/canping_texts_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
CASES = [
    (row, kind, text)
    for row in REFERENCE["literal_reference"]
    for kind, text in row["cells"].items()
]
ARGS = dict(
    year_gz="甲子",
    month_branch="寅",
    day_branch="子",
    hour_branch="子",
    include_luck=False,
)


@pytest.mark.parametrize("row,kind,text", CASES)
def test_thirteen_literal_source_cells_use_the_actual_number_and_column(
    row, kind, text
):
    record = lookup_record(row["element"], row["number"], kind)
    assert record["text"] == text
    selected = record["selection"]
    assert selected["number"] == row["number"] and selected["kind"] == kind
    assert selected["source_pdf_page"] == row["pdf_page"]
    assert selected["cell_status"] == (
        "source_printed_blank"
        if kind == "female" and row["number"] == 2335
        else "source_cell_visually_collated"
    )
    assert _lookup(row["element"], row["number"], kind) == text


def test_original_thirteen_witnesses_remain_with_expanded_global_scope():
    summary = collation_summary()
    assert summary["sha256"] == hashlib.sha256(COLLATION_PATH.read_bytes()).hexdigest()
    assert summary["source_pdf_sha256"] == REFERENCE["source_pdf_sha256"]
    assert summary["total_cells"] == 1170 and summary["collated_cells"] == 1123
    assert summary["pending_cells"] == 47
    assert summary["unresolved_reading_cells"] == 47
    assert len(REFERENCE["images"]) == 7
    for row in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / row["file"]).read_bytes()).hexdigest()
            == row["sha256"]
        )
    assert REFERENCE["new_original_birth_examples"] == 0
    assert REFERENCE["new_independent_calendar_instants"] == 0
    assert "independent_second_review_pending" in summary["review_status"]


def test_two_wrong_keys_are_corrected_without_editing_the_inherited_corpus():
    for element, wrong, right in (("火", 3838, 2838), ("土", 3372, 3373)):
        raw = _tiaowen()["parts"][element]
        assert str(wrong) in raw and str(right) not in raw
        selected = lookup_record(element, right, "male")
        assert selected["selection"]["inherited_number"] == wrong
        assert selected["selection"]["inherited_text"] == raw[str(wrong)]["male"]
        retired = lookup_record(element, wrong, "male")
        assert retired["text"] == ""
        assert retired["selection"]["row_status"] == "retired_inherited_number"
        assert retired["selection"]["corrected_number"] == right
    earth = _verses("土", compute_number("申", "申", "土"), "male")
    assert earth["numShun"] == earth["numNi"] == 3373
    assert earth["textShun"] == earth["textNi"] == "象取斗中氣，天邊柳絮飛。"
    assert earth["pair_resolution"]["same_number"]
    assert earth["pair_resolution"]["distinct_numbers"] == 1


def test_both_direction_numbers_can_have_only_one_local_row_as_the_source_allows():
    forward = _verses("水", compute_number("子", "丑", "水"), "luck")
    reverse = _verses("水", compute_number("丑", "子", "水"), "luck")
    assert (forward["numShun"], forward["numNi"]) == (2231, 3231)
    assert forward["textShun"] == reverse["textNi"] == "酒醒何處去，柳岸臨風輕。"
    assert forward["textNi"] == reverse["textShun"] == ""
    assert forward["pair_resolution"]["local_text_availability"] == "shun_only"
    assert reverse["pair_resolution"]["local_text_availability"] == "ni_only"
    assert forward["selectionNi"]["cell_status"] == "row_absent_in_local_corpus"


def test_printed_blank_missing_and_reviewed_rows_stay_distinct():
    verses = _verses("火", compute_number("丑", "卯", "火"), "female")
    assert (verses["numShun"], verses["numNi"]) == (2335, 3135)
    assert verses["selectionShun"]["cell_status"] == "source_printed_blank"
    assert verses["statusShun"] == "source_printed_blank"
    assert verses["selectionShun"]["source_pdf_page"] == 74
    assert verses["selectionNi"]["cell_status"] == "row_absent_in_local_corpus"
    for kind in ("male", "luck"):
        other = lookup_record("火", 2335, kind)["selection"]
        assert other["cell_status"] == "source_cell_visually_collated"
        assert other["source_pdf_page"] == 74
    reviewed = lookup_record("土", 3357, "male")["selection"]
    assert reviewed["cell_status"] == "source_cell_visually_collated"
    assert reviewed["source_pdf_page"] == 97


def test_partial_overlay_simulation_keeps_unreviewed_fallback_explicit(monkeypatch):
    from fatebridge.core import canping_texts

    partial = copy.deepcopy(canping_texts._collation())
    partial["entries"] = [
        e for e in partial["entries"] if (e["element"], e["number"]) != ("土", 3357)
    ]
    monkeypatch.setattr(canping_texts, "_collation", lambda: partial)
    unreviewed = lookup_record("土", 3357, "male")["selection"]
    assert unreviewed["cell_status"] == "inherited_transcription_unverified"
    assert "source_pdf_page" not in unreviewed
    # The production table is fully examined; this is a deliberately partial overlay.
    summary = collation_summary()
    assert summary["unexamined_cells"] == 3
    assert summary["numbered_table_visual_review_complete"] is False
    assert summary["numbered_table_clear_readings_complete"] is False


@pytest.mark.parametrize("element", list("水火木金土"))
def test_unreachable_special_verse_is_not_a_cross_column_fallback(element):
    for kind in ("male", "female", "luck"):
        row = lookup_record(element, 2869, kind)
        assert row["text"] == ""
        assert row["selection"]["unapplied_note"]["applied_to_lookup"] is False
    reachable = {
        compute_number(d, h, element)[k]
        for d in "子丑寅卯辰巳午未申酉戌亥"
        for h in "子丑寅卯辰巳午未申酉戌亥"
        for k in ("numShun", "numNi")
    }
    assert 2869 not in reachable
    assert _tiaowen()["special"]["2869"]["text"]  # retained archival input


def test_unspecified_raw_gender_keeps_numbers_without_selecting_male_text():
    r = calculate(**ARGS)
    assert r["gender"] is None and r["kindMain"] is None
    assert r["benming"]["numShun"] == r["benming"]["numNi"] == 3306
    assert r["benming"]["verses"]["textShun"] == r["benming"]["verses"]["textNi"] == ""
    assert r["benming"]["verses"]["statusShun"] == "not_selected_missing_gender"
    assert r["benming"]["verses"]["selectionShun"]["corpus_key"] is None
    assert "本命未选择男／女栏目" in build_snapshot_text(r)
    with pytest.raises(ValidationError):
        CanpingRequest(date="2000-05-15", time="09:33:00", use_true_solar_time=False)


@pytest.mark.parametrize("alias", ["女", "female", "FEMALE", "F", " f "])
def test_raw_gender_aliases_share_the_female_column(alias):
    r = calculate(**ARGS, gender=alias)
    assert r == calculate(**ARGS, gender="女")
    assert r["kindMain"] == "female" and r["gender"] == "女"
    assert r["benming"]["verses"]["selectionShun"]["column"] == "middle_female"


@pytest.mark.parametrize("bad", [True, False, 0, 1, "", "未知", "typo", [], {}])
def test_invalid_gender_cannot_select_any_column(bad):
    with pytest.raises(ValueError):
        calculate(**ARGS, gender=bad)


@pytest.mark.parametrize("bad", [None, True, 0, "", "甲", "甲丑", "庚午extra"])
def test_nayin_does_not_trim_invalid_year_inputs_to_a_valid_pair(bad):
    assert nayin_element(bad) == ""


def test_shared_luck_column_does_not_depend_on_unselected_natal_gender():
    series = liunian_series(
        year_gz="甲子",
        month_branch="寅",
        day_branch="子",
        hour_branch="子",
        birth_year=1984,
        start_age=1,
        end_age=1,
    )
    assert series["rows"][0]["verses"]["selectionShun"]["kind"] == "luck"


def test_selection_and_summary_cannot_mutate_loaded_source_data():
    before = copy.deepcopy(_tiaowen())
    selected = lookup_record("火", 2838, "male")
    selected["selection"]["reading_notes"].append("污染")
    selected["text"] = "污染"
    summary = collation_summary()
    summary["column_rule_pdf_pages"].append(999)
    assert 999 not in collation_summary()["column_rule_pdf_pages"]
    assert "污染" not in str(lookup_record("火", 2838, "male"))
    assert _tiaowen() == before


def test_loaded_hash_identifies_cached_content_after_a_file_replacement(tmp_path):
    p = tmp_path / "source.json"
    p.write_text('{"text":"first"}')
    first = _loaded(p)
    p.write_text('{"text":"second"}')
    again = _loaded(p)
    assert again == first and again["data"]["text"] == "first"
    assert again["sha256"] != hashlib.sha256(p.read_bytes()).hexdigest()
