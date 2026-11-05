"""Dated source disagreements survive lookup, prose and source replacement."""

import copy
import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import date
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_koya import SOURCE as ARC_SOURCE
from fatebridge.core.sukuyo_koya_preface import (
    SOURCE,
    preface_reading_lines,
    preface_reference,
)
from fatebridge.core.sukuyo_sources import load_source
from fatebridge.services.divination import calculate_sukuyo_compatibility

BASIS = "japanese_naoj_historical_utc09"


def test_unaccepted_marginal_word_span_is_not_filled_from_other_note_layers():
    ref = preface_reference(load_source(ARC_SOURCE).data)
    span = ref["arc_supplement_selected_reference"]["uncertain_marginal_spans"][0]
    assert span["accepted_literal"] is None
    assert "candidate_literals" not in span
    text = "\n".join(preface_reading_lines(ref))
    assert span["location"] in text
    assert "今布" not in text
    assert ref["supplement"]["unresolved_note_glyph"]["accepted_literal"] is None


@pytest.mark.parametrize("surface", ["single", "pair"])
def test_selected_hinoo_original_passages_are_delivered_with_their_locators(surface):
    if surface == "single":
        c = calendar_mansion(
            "2024-08-04",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        )
        text = day_evidence(c)["reading_text"]
    else:
        result = calculate_sukuyo_compatibility(
            person1_date="2024-08-04",
            person2_date="2024-09-05",
            calendar_profile="hinoo_t1299_host27",
            person1_calendar_day_part="first_half",
        )
        c = result["person1"]["calendar"]
        text = result["summary"]
    source = c["profile_calculation"]["hinoo_source"]
    assert source["active_primary_evidence"] == "downloaded_primary_edition"
    windows = source["downloaded_primary_edition"]["downloaded_calendar_windows"]
    assert len(windows) == 2
    for window in windows:
        assert window["locator"] in text
        assert window["text"] in text


@pytest.mark.parametrize(
    "civil,role,ganzhi,weekday",
    [
        ("0808-02-10", "校按拟正月七日", "己丑", "日"),
        ("0808-03-11", "校按对正文二月七日的判断", "己未", "火"),
    ],
)
def test_printed_marginal_proposal_does_not_emend_body_or_confirm_birth_date(
    civil, role, ganzhi, weekday
):
    c = calendar_mansion(civil, zone="+09:00", calendar_basis=BASIS)
    ref = c["calendar_reference"]["early_weekday_editorial_comparison"]
    assert c["calendar_date"] == civil
    assert ref["selected_claim"]["claim_role"] == role
    assert ref["reference_day_ganzhi"] == ganzhi
    assert ref["reference_luminary"] == weekday
    assert ref["weekday_matches_under_same_label"]
    assert ref["ganzhi_matches_under_same_label"]
    assert not ref["birth_date_or_primary_changed"]
    assert not ref["main_text_error_or_corrected_date_certified"]
    text = day_evidence(c)["reading_text"]
    assert "校按" in text and "未按校按更换本次输入" in text
    if civil == "0808-03-11":
        body = c["calendar_reference"]["early_weekday_documentary_comparison"]
        assert not body["weekday_matches_under_same_label"]
        assert body["printed_day_ganzhi"] is None
        assert "不同，保留分歧" in text
    else:
        assert "early_weekday_documentary_comparison" not in c["calendar_reference"]


@pytest.mark.parametrize(
    "civil,weekday,ganzhi,agrees",
    [
        ("0806-01-29", "日", "丁卯", True),
        ("0807-02-18", "日", "壬辰", True),
        ("0808-03-11", "火", None, False),
    ],
)
def test_actual_same_label_source_comparison_keeps_adverse_weekday(
    civil, weekday, ganzhi, agrees
):
    c = calendar_mansion(civil, zone="+09:00", calendar_basis=BASIS)
    ref = c["calendar_reference"]["early_weekday_documentary_comparison"]
    assert ref["reference_luminary"] == weekday
    assert ref["printed_luminary"] == "日"
    assert ref["weekday_matches_under_same_label"] is agrees
    assert ref["printed_day_ganzhi"] == ganzhi
    assert ref["ganzhi_matches_under_same_label"] is (True if ganzhi else None)
    assert not ref["source_date_corrected"] and not ref["source_error_established"]
    assert (
        not ref["historical_daybreak_accepted"]
        and not ref["tang_calendar_conversion_evaluated"]
    )
    text = day_evidence(c)["reading_text"]
    assert ref["source_record"]["literal"] in text
    if agrees:
        assert "相合" in text
    else:
        assert "不同，保留分歧" in text and "不包含原录日曜" in text
        assert "未把参考干支补成原文" in text
        assert not ref["claimed_weekday_in_adjacent_day_control"]
        assert [r["luminary"] for r in ref["adjacent_civil_day_control"]] == [
            "月",
            "火",
            "水",
        ]


def test_conjectured_tang_day_four_is_not_replaced_by_japanese_day_four():
    c = calendar_mansion("0807-02-18", zone="+09:00", calendar_basis=BASIS)
    ref = c["calendar_reference"]["early_weekday_documentary_comparison"]
    assert ref["reference_lunar_fields"] == [807, 1, 3, False]
    alternative = ref["source_record"]["tang_alternative"]
    assert (
        alternative["lunar_day"] == 4
        and not alternative["tang_calendar_backend_computed"]
    )
    other = calendar_mansion("0807-02-19", zone="+09:00", calendar_basis=BASIS)
    assert "early_weekday_documentary_comparison" not in other["calendar_reference"]
    assert day_evidence(other)["weekday"]["luminary"] == "月"
    assert "未用日本同名正月四日替代唐历四日" in day_evidence(c)["reading_text"]


def test_unknown_clock_keeps_documentary_mismatch_in_its_actual_date_branch():
    c = calendar_mansion("0808-03-10", zone="+08:00", calendar_basis=BASIS)
    assert c["status"] == "partial"
    branches = c["calendar_candidates"]
    assert [b["calendar_date"] for b in branches] == ["0808-03-10", "0808-03-11"]
    assert (
        "early_weekday_documentary_comparison" not in branches[0]["calendar_reference"]
    )
    assert not branches[1]["calendar_reference"][
        "early_weekday_documentary_comparison"
    ]["weekday_matches_under_same_label"]
    assert "不同，保留分歧" in day_evidence(c)["reading_text"]


def test_pair_native_does_not_drop_early_date_disagreement_or_ascribe_autograph():
    r = calculate_sukuyo_compatibility(
        person1_date="0808-03-11",
        person1_zone="+09:00",
        person2_date="0806-01-29",
        person2_zone="+09:00",
        calendar_basis=BASIS,
    )
    text = r["summary"]
    assert "不同，保留分歧" in text and "丁卯" in text
    assert "又大同三年二月七日又是蜜日也" in text
    assert "未把它们归给2013年编者" in text


def test_modern_transcription_is_bound_to_preface_images_and_keeps_new_uncertainties():
    old = load_source(ARC_SOURCE).data
    ref = preface_reference(old)
    assert ref["modern_publication_date"] == "2013-03"
    assert ref["entry_number"] == "095" and ref["pdf_pages_one_based"] == [83, 84]
    assert ref["catalogue_witness"]["call_number_literal"] is None
    assert len(ref["catalogue_witness"]["call_number_model_readings"]) == 2
    assert "重直兩日" in ref["preface_selected"]["literal"]
    assert not ref["leap_short_month_priority_established"]
    assert ref["supplement"]["unresolved_note_glyph"]["accepted_literal"] is None
    changed = copy.deepcopy(old)
    changed["preface_selected_reference"]["images"][0]["image_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="身份不符"):
        preface_reference(changed)
    ref["dated_records"][0]["weekday_literal"] = "changed"
    assert preface_reference(old)["dated_records"][0]["weekday_literal"] == "密日"


def test_raw_naoj_month_starts_independently_locate_all_three_named_labels():
    base = Path(__file__).parents[1] / "data/sukuyo_historical_calendar_v1"
    manifest = json.loads((base / "manifest.json").read_bytes())
    expected = [
        (806, 1, 2, "0806-01-29"),
        (807, 1, 3, "0807-02-18"),
        (808, 2, 7, "0808-03-11"),
        (808, 1, 7, "0808-02-10"),
    ]
    with zipfile.ZipFile(base / "captures.zip") as z:
        for year, month, day, civil in expected:
            name = f"naoj-{year:04}.response.bin"
            raw = z.read(name)
            assert hashlib.sha256(raw).hexdigest() == manifest["files_sha256"][name]
            matches = [
                row
                for row in csv.reader(io.StringIO(raw.decode("cp932")))
                if len(row) >= 3
                and re.search(rf"(?<!閏){month:02}月01日$", row[1])
                and int(row[2]) - 660 == year
            ]
            assert len(matches) == 1
            y, m, d = map(int, matches[0][0].split("/"))
            assert (
                date.fromordinal(date(y, m, d).toordinal() + day - 1).isoformat()
                == civil
            )
