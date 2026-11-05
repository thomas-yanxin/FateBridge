"""Source weekday corrections and comparative time units retain their scope."""

import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_calendar_text import calendar_day_evidence, source_bundle
from scripts.sukuyo.check_sukuyo_time_units import verify_time_primary


@pytest.mark.parametrize(
    "date,mansion,primary,ming,origin",
    [
        ("2025-01-07", "昴", [], ["金刚峰"], "正文水曜，校记重建火曜"),
        ("2025-04-22", "壁", ["金刚峰"], [], "正文水曜，校记重建火曜"),
        ("2025-02-26", "壁", [], ["金刚峰"], "正文火曜，校记重建水曜"),
        ("2025-10-08", "昴", ["金刚峰"], [], "正文火曜，校记重建水曜"),
    ],
)
def test_weekday_reconstruction_is_distinguished_from_mansion_glyph_change(
    date, mansion, primary, ming, origin
):
    day = day_evidence(calendar_mansion(date, "12:00:00"))
    assert day["day_mansion"] == mansion
    special = day["special_day_evidence"]
    upper = next(
        row
        for row in special["comparisons"]
        if row["witness"] == "upper_ming_apparatus"
    )
    assert special["primary"]["matched_labels"] == primary
    assert upper["matched_labels"] == ming and not upper["applied_to_primary"]
    assert origin in day["reading_text"]
    assert "不代入主表或确定事项" in day["reading_text"]


def test_three_time_counts_are_not_sixteen_or_modern_clock_hours():
    report = verify_time_primary()
    assert report["errors"] == []
    assert report["selected_witnesses"] == 2 and report["inline_notes"] == 2
    assert report["full_source_files_checked"] == []
    result = calendar_day_evidence(8)
    original = source_bundle()["clock_doctrine"]
    doctrine = result["clock_doctrine"]
    assert {key: doctrine[key] for key in original} == original
    one, two = doctrine["comparative_time_systems"]["witnesses"]
    assert one["daily_time_units"] == 30
    assert [(r["day"], r["night"]) for r in one["seasonal_time_unit_counts"]] == [
        (15, 15),
        (18, 12),
        (12, 18),
    ]
    assert two["structural_day_parts"] == two["structural_night_parts"] == 3
    assert two["lay_day_parts"] == two["lay_night_parts"] == 4
    assert not one["units_are_modern_hours"] and not two["units_are_modern_hours"]
    assert doctrine["day_parts"] == doctrine["night_parts"] == 8
    assert doctrine["starting_boundary_literal"] == "平明"
    assert result["clock_evaluation_status"] == "not_computed"


def test_comparative_time_evidence_is_detached_and_not_a_clock_solution():
    first = calendar_day_evidence(1)["clock_doctrine"]["comparative_time_systems"]
    first["witnesses"][0]["daily_time_units"] = 24
    second = calendar_day_evidence(1)["clock_doctrine"]["comparative_time_systems"]
    assert second["witnesses"][0]["daily_time_units"] == 30
    assert second["solar_altitude_degrees"] is None
    assert not second["applied_to_runtime_clock"]
    assert not second["modern_clock_conversion_established"]
    assert not second["hinoo_half_mapping_established"]
    assert len(second["source_bundle_sha256"]) == 64


def test_changed_primary_file_is_rejected(tmp_path):
    fixture = json.loads(
        (
            Path(__file__).parents[1] / "data/sukuyo-comparative-time-primary.json"
        ).read_bytes()
    )
    for name in fixture["source_files"]:
        (tmp_path / name).write_bytes(b"changed source")
    with pytest.raises(ValueError, match="source bytes changed"):
        verify_time_primary(tmp_path)


def test_native_preserves_comparative_texts_without_certifying_daybreak():
    text = day_evidence(calendar_mansion("2025-01-07", "12:00:00"))["reading_text"]
    assert "一日夜三十时" in text
    assert "行内注为昼三夜三" in text and "行内注为昼四夜四" in text
    assert "未证明旦等于平明" in text
    assert "未代入本次计算" in text


@pytest.mark.parametrize("date", ["2025-04-22", "2025-02-26"])
def test_native_direction_reference_keeps_opposing_chapter_even_for_study(date):
    day = day_evidence(
        calendar_mansion(date, "12:00:00"),
        activity="study",
        activity_details=["religious_learning"],
    )
    assert day["day_mansion"] == "壁"
    assert day["activity_assessment"]["evidence_status"] == "conditional_only"
    assert day["activity_assessment"]["matched_rules"] == []
    text = day["reading_text"]
    assert "向南出行列为宜条" in text
    assert "不宜南行" in text and "T21n1299_p0396b21" in text
    assert "同向出行证言相反" in text
    assert "未据此改变本次事项匹配状态" in text


def test_native_direction_conflict_does_not_replace_declared_travel_assessment():
    day = day_evidence(
        calendar_mansion("2025-04-22", "12:00:00"),
        activity="travel",
        activity_details=["southbound_journey"],
    )
    assert day["activity_assessment"]["evidence_status"] == "conflicted"
    assert "同向出行证言相反" in day["reading_text"]
    matched = day["activity_assessment"]["matched_rules"]
    assert any(r["rule_id"] == "t1299_lower_mansion_37" for r in matched)
    assert any(r["rule_id"] == "t1299_direction_10" for r in matched)


def test_native_does_not_invent_direction_conflict_for_other_mansion():
    day = day_evidence(calendar_mansion("2025-01-07", "12:00:00"))
    assert day["day_mansion"] == "昴"
    assert "同向出行证言相反" not in day["reading_text"]
