"""Direct-print readings cannot replace or complete Taisho witnesses."""

import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_special_days import special_day_evidence
from scripts.check_sukuyo_printed_special import verify_printed_special


def evidence(name, weekday):
    return special_day_evidence(
        name, weekday, weekday_basis="modern_utc_plus08_civil_midnight"
    )


def printed(result):
    return result["direct_printed_comparisons"][0]


def test_all_selected_print_cells_and_unaccepted_glyph_match_source_fixture():
    report = verify_printed_special()
    assert report["errors"] == []
    assert report["selected_slots"] == 21
    assert report["recognized_mansion_readings"] == 20
    assert report["mansion_weekday_cells_checked"] == 189
    assert report["unaccepted_glyph_slots"] == [
        {"label": "罗刹", "weekday_index": 4, "candidate_readings": ["巨", "亢"]}
    ]
    assert report["full_image_bytes_checked"] == []
    assert not report["independent_human_transcription_accepted"]
    assert not report["whole_print_and_apparatus_collated"]


@pytest.mark.parametrize("name,weekday", [("尾", 6), ("女", 1)])
def test_print_variants_stay_separate_from_selected_taisho(name, weekday):
    result = evidence(name, weekday)
    assert result["primary"]["matched_labels"] == []
    direct = printed(result)
    assert direct["matched_labels"] == ["金刚峰"]
    assert direct["disagrees_with_primary"]
    assert not direct["applied_to_primary"]
    assert direct["source_reference"]["publication_year"] == 1897
    assert len(result["comparisons"]) == 3


def test_saturday_kang_is_not_silently_replaced_with_printed_tail():
    result = evidence("亢", 6)
    assert result["primary"]["matched_labels"] == ["金刚峰"]
    assert printed(result)["matched_labels"] == []
    assert printed(result)["labels_complete_for_selected_day"]


def test_printed_stomach_does_not_repair_lower_taisho_mao():
    result = evidence("胃", 0)
    assert printed(result)["matched_labels"] == ["罗刹"]
    lower = next(r for r in result["comparisons"] if r["witness"] == "lower_taisho")
    assert lower["unresolved_rows"][0]["literal_mansion"] == "冒"
    assert not lower["labels_complete_for_selected_day"]
    assert lower["matched_labels"] == []


@pytest.mark.parametrize("name", ["氐", "亢", "鬼"])
def test_unaccepted_thursday_glyph_is_not_normalized_or_declared_absent(name):
    direct = printed(evidence(name, 4))
    assert not direct["labels_complete_for_selected_day"]
    assert direct["disagrees_with_primary"] is None
    row = direct["unresolved_rows"][0]
    assert row["literal_mansion"] is None and row["mansion"] is None
    assert not row["source_clause_is_witness_reading"]
    assert row["candidate_readings"] == ["巨", "亢"]
    assert not row["candidate_readings_accepted_as_mansion"]


def test_unknown_mansion_keeps_printed_labels_unapplied():
    direct = printed(evidence(None, 6))
    assert direct["matched_labels"] == []
    assert not direct["labels_complete_for_selected_day"]
    assert not direct["applied_to_primary"]


def test_printed_reference_is_detached_and_has_its_own_fingerprint():
    first = evidence("尾", 6)
    direct = printed(first)
    assert (
        direct["source_reference"]["source_bundle_sha256"]
        != first["source_bundle_sha256"]
    )
    direct["matched_rows"][0]["mansion"] = "牛"
    direct["source_reference"]["images"][0]["sha256"] = "changed"
    again = printed(evidence("尾", 6))
    assert again["matched_rows"][0]["mansion"] == "尾"
    assert again["source_reference"]["images"][0]["sha256"] != "changed"


def test_checker_rejects_changed_captured_image(tmp_path):
    fixture = json.loads(
        (
            Path(__file__).parent / "fixtures/sukuyo-wakita-special-primary.json"
        ).read_bytes()
    )
    for row in fixture["source_reference"]["images"]:
        (tmp_path / row["file"]).write_bytes(b"changed capture")
    with pytest.raises(ValueError, match="fingerprint changed"):
        verify_printed_special(tmp_path)


def test_native_print_description_retains_source_and_partial_transcription():
    day = day_evidence(calendar_mansion("2025-03-06", "12:00:00"))
    assert day["weekday"]["luminary"] == "木"
    text = day["reading_text"]
    assert "1897年脇田文绍缩刷本下卷的直接印本对照" in text
    assert "巨／亢仅为未接纳的字形候选" in text
    assert "20项已识别，1项未核定" in text
    assert "不代入主表或确定事项" in text


@pytest.mark.parametrize(
    "date,expected",
    [
        ("2025-09-27", "金刚峰位亢"),
        ("2025-02-15", "金刚峰位亢"),
        ("2025-10-27", "正文心，校记重建女"),
        ("2025-02-02", "正文冒，校记重建胃"),
        ("2025-07-03", "正文底，校记重建氐"),
    ],
)
def test_native_explicitly_compares_all_four_old_special_day_witnesses(date, expected):
    text = day_evidence(calendar_mansion(date, "12:00:00"))["reading_text"]
    for witness in ["上卷大正", "下卷大正", "上卷明本校记重建", "下卷明本校记重建"]:
        assert f"{witness}本曜表项：" in text
    assert expected in text
    if date in {"2025-09-27", "2025-02-15"}:
        assert "金刚峰位尾" in text
    assert "不代入主表或确定事项" in text


def test_native_unresolved_mansion_preserves_old_witness_agreement_without_labels():
    text = day_evidence(calendar_mansion("2025-07-25", "12:00:00"))["reading_text"]
    assert text.count("本曜表项：甘露位房、金刚峰位張、罗刹位奎") == 4
    assert text.count("本次日宿未定，候选不代入确定标签；标签集合未定") == 4
    assert "金刚峰位張" in text
