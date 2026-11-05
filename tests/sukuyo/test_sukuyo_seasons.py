"""Seasonal relations cannot select ancient clock or leap-month precedence."""

from copy import deepcopy

import pytest

from fatebridge.core import sukuyo_seasons as seasons
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_commentarial_clock import commentarial_boundary_reference
from fatebridge.core.sukuyo_sources import LoadedSource
from scripts.sukuyo.check_sukuyo_seasons import verify_primary


def reference():
    return commentarial_boundary_reference()["standalone_xuanying_reference"][
        "named_rizang_comparison"
    ]["seasonal_time_reference"]


@pytest.mark.parametrize(
    "month,day,night",
    [
        (1, 14, 16),
        (2, 15, 15),
        (3, 16, 14),
        (4, 17, 13),
        (5, 18, 12),
        (6, 17, 13),
        (7, 16, 14),
        (8, 15, 15),
        (9, 14, 16),
        (10, 13, 17),
        (11, 12, 18),
        (12, 13, 17),
    ],
)
def test_each_original_month_count_and_time_label(month, day, night):
    row = reference()["all12_season_rows"][month - 1]
    assert (row["textual_month"], row["day_count"], row["night_count"]) == (
        month,
        day,
        night,
    )
    assert row["time_unit_literal"] == "時"
    assert not row["explicit_equinox_term_in_selected_paragraph"]


def test_eighth_month_narrative_does_not_become_missing_daily_cells():
    value = reference()
    assert not value["all12_season_rows"][7]["explicit_fortnight_table_for_this_month"]
    original = commentarial_boundary_reference()["standalone_xuanying_reference"][
        "named_rizang_comparison"
    ]
    assert len(original["literal_slots"]) == 330
    assert not any(r["textual_month"] == 8 for r in original["literal_slots"])


def test_shadow_repeat_and_half_footprint_are_not_smoothed_or_modern_lengths():
    rows = reference()["all12_season_rows"]
    assert rows[4]["noon_shadow_literal"] == "半脚跡"
    assert (
        rows[10]["noon_shadow_literal"] == rows[11]["noon_shadow_literal"] == "十二脚跡"
    )
    assert not reference()["derived_diagnostics"][
        "latitude_or_gnomon_geometry_inferred"
    ]


def test_same_fifth_label_or_count_does_not_certify_uniform_date_conversion():
    value = reference()
    compared = value["named_month_comparison_scope"]
    assert compared["Rizang_month5_fullmoon_literal"] == "女"
    assert compared["T1299_named_Tang_month"] == 6
    assert (
        compared["literal_Rizang_month5_season_counts"]
        == compared["literal_T1509_fifth_solstice_counts"]
        == [18, 12]
    )
    assert not value["interpretation_scope"][
        "uniform_month_or_year_conversion_established"
    ]
    assert not value["interpretation_scope"][
        "new_intercalation_or_precedence_rule_adopted"
    ]


@pytest.mark.parametrize(
    "file,expected",
    [
        ("sukuyo_t1299_days.json", "T1299"),
        ("sukuyo_comparative_time_units.json", "大智度论"),
    ],
)
def test_substituted_parent_edition_cannot_reuse_seasonal_binding(
    monkeypatch, file, expected
):
    load = seasons.load_source

    def changed(path):
        value = load(path)
        if path.name != file:
            return value
        payload = value.data
        if file == "sukuyo_t1299_days.json":
            payload["source_sha256"] = "changed"
        else:
            payload["witnesses"][0]["source_sha256"] = "changed"
        return LoadedSource(payload, "changed")

    monkeypatch.setattr(seasons, "load_source", changed)
    with pytest.raises(ValueError, match=expected + "具名版本不一致"):
        seasons.seasonal_reference(
            {"source_sha256": reference()["source_files"]["T13n0397.xml"]["sha256"]}
        )


def test_substituted_rizang_edition_is_rejected():
    with pytest.raises(ValueError, match="日藏具名版本不一致"):
        seasons.seasonal_reference({"source_sha256": "changed"})


def test_detached_view_cannot_rewrite_later_shadow_or_clock_flags():
    value = reference()
    value["all12_season_rows"][11]["noon_shadow_literal"] = "十脚跡"
    value["interpretation_scope"]["physical_day_boundary_established"] = True
    assert reference()["all12_season_rows"][11]["noon_shadow_literal"] == "十二脚跡"
    assert not reference()["interpretation_scope"]["physical_day_boundary_established"]


def test_source_counts_do_not_change_actual_calendar_or_pick_half():
    calendar = calendar_mansion(
        "0806-07-23",
        "12:00:00",
        "+09:00",
        calendar_profile="hinoo_t1299_host27",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    before = deepcopy(calendar)
    evidence = day_evidence(calendar)
    assert calendar == before
    assert calendar["calendar_day_part"] is None
    text = evidence["reading_text"]
    assert "五月18／12" in text and "十一月12／18" in text
    assert "八月15／15" in text and "脚迹不是已核定的现代长度" in text
    assert "月段各自标‘时’" in text
    assert not reference()["interpretation_scope"][
        "muhurta_equals48_modern_minutes_accepted"
    ]


@pytest.mark.parametrize("name", ["T13n0397.xml", "T21n1299.xml", "T25n1509.xml"])
def test_wrong_actual_source_capture_is_rejected(tmp_path, name):
    path = tmp_path / "wrong"
    path.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="实际源文件字节指纹不一致"):
        verify_primary({name: path})


def test_offline_primary_check_has_no_claim_of_actual_capture_or_clock():
    result = verify_primary()
    assert result["all_seasonal_month_rows_checked"] == 12
    assert result["actual_source_files_rechecked"] == []
    assert not result["physical_clock_or_uniform_calendar_conversion_certified"]
