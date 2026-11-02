"""Source positions and emendations cannot silently become calendar corrections."""

from datetime import date

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_calendar_text import render_day_reading
from fatebridge.core.sukuyo_historical_calendar import date_reference
from fatebridge.core.sukuyo_shogonji_daily import daily_annotation_reference
from scripts.check_sukuyo_shogonji_daily import verify_daily_annotations

HISTORICAL = "japanese_naoj_historical_utc09"


def test_four_frozen_headings_do_not_resolve_two_different_relocations():
    report = verify_daily_annotations()
    assert not report["errors"]
    assert report["source_annotations"] == 2
    assert len(report["related_date_headings"]) == 4
    assert report["author_suggested_day_shifts"] == [-1, -2]
    assert not report["single_global_day_shift_supported"]
    assert all(r["date_heading_ganzhi_agrees"] for r in report["related_date_headings"])
    assert not report["acceptance"]["ancient_day_boundary_accepted"]
    assert not report["acceptance"]["leap_short_month_priority_accepted"]


@pytest.mark.parametrize(
    "civil,role,day,ganzhi",
    [
        ("1346-07-18", "original_position", 21, "戊辰"),
        ("1346-07-17", "author_suggested_position", 20, "丁卯"),
        ("1346-08-30", "original_position", 5, "辛亥"),
        ("1346-08-28", "author_suggested_position", 3, "己酉"),
    ],
)
def test_original_and_proposed_positions_retain_their_own_dates(
    civil, role, day, ganzhi
):
    c = calendar_mansion(civil, zone="+09:00", calendar_basis=HISTORICAL)
    r = c["calendar_reference"]["manuscript_daily_annotations"]
    assert c["calendar_date"] == civil and c["lunar_day"] == day
    assert c["calendar_reference"]["day_ganzhi_reference"]["name"] == ganzhi
    assert r["records"][0]["current_date_role"] == role
    assert not r["acceptance"]["author_suggestions_applied_to_input_date"]
    text = render_day_reading(day_evidence(c))
    assert (
        "本参考日是"
        + ("原始旁注所在日" if role == "original_position" else "作者建议移置日")
        in text
    )
    assert f"规范{ganzhi}" in text
    assert "建议位置不是原卷的实录位置" in text
    assert "未移动旁注或修改输入日期" in text
    assert "本日不是初一" in text  # This limit still applies to the month header only.


def test_term_witness_and_birth_year_conditions_survive_native_prose():
    c = calendar_mansion("1346-08-30", zone="+09:00", calendar_basis=HISTORICAL)
    text = render_day_reading(day_evidence(c))
    for phrase in (
        "规范化候选为狼藉",
        "不能当作本次T1299宿曜羅刹",
        "62章另题羅刹",
        "三宝类仪式，余无咎",
        "吉日仍要求支干之吉",
        "未替换现用T1299",
        "首列为生年",
        "未提供生年",
        "月法也未在此核定",
        "天理吉田文庫本",
        "不等于此1811印本",
        "头部2025-01-30不是发行年份",
        "这不证明一切历史传本无此文",
        "两条旁注与四个相关日付",
        "现实预测样本仍为零",
    ):
        assert phrase in text
    r = c["calendar_reference"]["manuscript_daily_annotations"]
    assert not r["term_reference"]["equivalent_to_t1299_rasetsu"]
    assert not r["term_reference"]["rekirin_primary_reference"][
        "applied_to_primary_mansion_or_activity"
    ]


def test_known_cross_zone_time_uses_actual_reference_date_without_relocation():
    c = calendar_mansion(
        "1346-07-17", time_text="23:30:00", zone="+08:00", calendar_basis=HISTORICAL
    )
    assert c["calendar_date"] == "1346-07-18" and c["lunar_day"] == 21
    r = c["calendar_reference"]["manuscript_daily_annotations"]
    assert r["records"][0]["current_date_role"] == "original_position"
    assert not r["acceptance"]["ancient_day_boundary_accepted"]


def test_unknown_time_keeps_both_source_roles_in_separate_date_branches():
    from fatebridge.core.sukuyo_historical_calendar import compatibility_reference_notes

    c = calendar_mansion("1346-07-17", zone="+08:00", calendar_basis=HISTORICAL)
    branches = c["calendar_candidates"]
    assert [r["calendar_date"] for r in branches] == ["1346-07-17", "1346-07-18"]
    assert [
        r["calendar_reference"]["manuscript_daily_annotations"]["records"][0][
            "current_date_role"
        ]
        for r in branches
    ] == ["author_suggested_position", "original_position"]
    text = compatibility_reference_notes([c], ["甲"])
    assert "甲的参考日期1346-07-17：" in text
    assert "甲的参考日期1346-07-18：" in text
    assert "本参考日是作者建议移置日" in text
    assert "本参考日是原始旁注所在日" in text
    assert not c["birth_time_known"]


def test_unread_dates_and_uncovered_leap_months_are_not_claimed_annotation_free():
    assert daily_annotation_reference(1346, 6, False, 22) is None
    assert daily_annotation_reference(1346, 6, True, 21) is None
    assert "manuscript_daily_annotations" not in date_reference(date(1346, 8, 29))
    assert daily_annotation_reference(1347, 8, False, 5) is None
    r = daily_annotation_reference(1346, 8, False, 5)
    assert "not a claim" in r["absence_policy"]
    r["records"][0]["annotation_literal"] = "羅刹"
    r["term_reference"]["rekirin_primary_reference"]["distinct_chapter_titles"].clear()
    later = daily_annotation_reference(1346, 8, False, 5)
    assert later["records"][0]["annotation_literal"] == "らうさく"
    assert (
        len(
            later["term_reference"]["rekirin_primary_reference"][
                "distinct_chapter_titles"
            ]
        )
        == 2
    )


@pytest.mark.parametrize("civil", ["1346-07-18", "1346-08-28"])
def test_daily_evidence_is_preserved_across_rest_native_mcp_and_cli(
    monkeypatch, capsys, civil
):
    from tests.test_sukuyo_transports import (
        test_calendar_and_relations_across_all_real_transports as check,
    )

    check(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": civil,
            "time": "12:00:00",
            "zone": "+09:00",
            "calendar_basis": HISTORICAL,
        },
        [
            "sukuyo.calendar.calendar_reference.manuscript_daily_annotations",
            "sukuyo.reading_text",
        ],
    )
