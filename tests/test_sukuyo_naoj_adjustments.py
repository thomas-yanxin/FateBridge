"""All published monthly adjustments remain distinct from selected host facts."""

import gzip
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_naoj_adjustments as module
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_historical_calendar import date_reference

FIXTURE = (
    Path(__file__).parent / "fixtures/sukuyo-naoj-adjustments-before-code-v1.json.gz"
)


def frozen():
    return json.loads(gzip.decompress(FIXTURE.read_bytes()))


def test_all303_source_table_rows_retained_in_their_original_categories():
    fixture = frozen()
    data = json.loads(module.SOURCE.read_bytes())
    assert (
        hashlib.sha256(module.SOURCE.read_bytes()).hexdigest()
        == fixture["source_literal_facts_sha256"]
    )
    actual = [
        *data["monthly_rows"],
        *data["solar_term_rows"],
        *data["early_comparison_rows"],
    ]
    expected = [
        row
        for table in fixture["all_literal_tables"]["tables"]
        for row in table["rows"][1:]
    ]
    assert len(actual) == len(expected) == 303
    for row, original in zip(actual, expected, strict=True):
        assert row["literal_cells"] == [cell["text"] for cell in original]
    assert data["counts"] == {
        "monthly_adjustment_rows": 276,
        "solar_adjustment_rows": 9,
        "early_two_calendar_comparison_rows": 18,
        "all_nonheader_published_table_rows": 303,
    }
    assert sum(row["kind"] == "month_label_adjustment" for row in actual) == 67
    assert sum(row["kind"] == "month_start_adjustment" for row in actual) == 209


def test_all276_adjustments_match_before_code_dates_cycles_and_literal_facts():
    fixture = frozen()
    data = json.loads(module.SOURCE.read_bytes())
    facts = {row["id"]: row for row in data["monthly_rows"]}
    rows = fixture["before_production_binding"]["rows"]
    assert len(rows) == 276
    for expected in rows:
        result = date_reference(date.fromordinal(expected["host_start_ordinal"]))
        reference = result["published_calendar_adjustment_reference"]
        actual = next(
            row
            for row in reference["selected_month_records"]
            if row["id"] == expected["id"]
        )
        assert all(actual[key] == value for key, value in facts[actual["id"]].items())
        assert (
            reference["selected_post_adjustment_month_key"]
            == expected["after_month_key"]
        )
        assert actual["selected_host_start_ordinal"] == expected["host_start_ordinal"]
        assert actual["selected_host_start_ganzhi"] == expected["host_start_ganzhi"]
        assert (
            actual["published_after_date_matches_selected_host"]
            == expected["checks"]["published_after_date_equal_host_start"]
        )
        assert (
            actual["published_after_cycle_matches_selected_host"]
            == expected["checks"]["published_after_cycle_equal_host_start"]
        )
        assert not reference["scope"]["published_corrections_applied_again"]
        assert not reference["scope"]["host_fields_changed"]


def test_all23155_host_months_bind_complete_post_adjustment_keys_without_leakage():
    fixture = frozen()
    expected = {}
    for row in fixture["before_production_binding"]["rows"]:
        expected.setdefault(tuple(row["after_month_key"]), set()).add(row["id"])
    host = json.loads(
        (module.SOURCE.parent / "sukuyo_japanese_historical_v1.json").read_bytes()
    )
    seen = set()
    for ordinal, year, month, leap, length in host["months"]:
        result = module.month_adjustment_reference(year, month, leap, ordinal, "甲子")
        actual = {row["id"] for row in result["selected_month_records"]}
        assert actual == expected.get((year, month, leap), set())
        assert result["selected_month_is_listed"] == bool(actual)
        seen.update(actual)
    assert len(host["months"]) == 23155
    assert len(seen) == 276


def test_julian_printed_dates_and_month_renaming_are_not_double_applied():
    ref = date_reference(date(768, 7, 23))["published_calendar_adjustment_reference"]
    label, start = ref["selected_month_records"]
    assert label["before_month_key"] == [768, 6, False]
    assert label["after_month_key"] == [768, 6, True]
    assert label["after_start"] is None
    assert label["binding_state"] == "published_label_only_no_civil_start_in_row"
    assert start["after_start"]["printed_civil_fields"] == [768, 7, 19]
    assert start["after_start"]["calendar_convention"] == "julian"
    assert start["after_start"]["proleptic_gregorian_date"] == "0768-07-23"
    assert start["binding_state"] == "same_published_post_adjustment_date_and_cycle"
    changed = module.month_adjustment_reference(
        768, 6, True, date(768, 7, 24).toordinal(), "甲辰"
    )
    assert (
        changed["selected_month_records"][1]["binding_state"]
        == "published_post_adjustment_disagrees_with_selected_host"
    )
    assert (
        changed["selected_month_records"][1]["after_start"]["proleptic_gregorian_date"]
        == "0768-07-23"
    )


def test_catalogue_absence_and_detached_output_do_not_rewrite_history():
    calendar = calendar_mansion(
        "0820-03-22",
        "00:15:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
    )
    ref = calendar["calendar_reference"]["published_calendar_adjustment_reference"]
    assert not ref["selected_month_is_listed"]
    assert not ref["scope"]["catalogue_absence_proves_no_adjustment"]
    assert calendar["calendar_reference"]["cross_source_comparison"] is not None
    text = day_evidence(calendar)["reading_text"]
    assert "目录未列也不证明本月从未校订" in text
    ref["complete_published_table_counts"]["monthly_adjustment_rows"] = 0
    ref["source"]["url"] = "changed"
    fresh = date_reference(date(820, 3, 22))["published_calendar_adjustment_reference"]
    assert fresh["complete_published_table_counts"]["monthly_adjustment_rows"] == 276
    assert fresh["source"]["url"].startswith("https://eco.mtk.nao.ac.jp/")


@pytest.mark.parametrize("part", [None, "first_half", "second_half"])
def test_complete_current_leap_month_conditions_are_still_delivered(part):
    args = {"calendar_day_part": part} if part else {}
    calendar = calendar_mansion(
        "0768-07-23",
        "05:45:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        **args,
    )
    assert (
        calendar["lunar_month"] == 6
        and calendar["is_leap_month"]
        and calendar["lunar_day"] == 1
    )
    assert calendar["calendar_day_part"] == part
    assert calendar["natal_su27"] == "鬼"
    text = day_evidence(calendar)["reading_text"]
    for needle in [
        "匹配2条",
        "276条为月校订",
        "9条为节气校订",
        "18条为早期两历比较",
        "儒略历768/7/19",
        "0768-07-23",
        "没有再平移一次历日或配宿",
        "古代平明",
        "闰小月补配优先",
    ]:
        assert needle in text


@pytest.mark.parametrize(
    "field",
    [
        "monthly_rows",
        "solar_term_rows",
        "early_comparison_rows",
        "date_convention_source",
    ],
)
def test_dropping_any_source_category_or_changing_date_convention_requires_revalidation(
    monkeypatch, tmp_path, field
):
    data = json.loads(module.SOURCE.read_bytes())
    if field == "date_convention_source":
        data[field]["declared"] = "Treat all literal dates as Gregorian"
    else:
        data[field].pop()
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(module, "SOURCE", path)
    with pytest.raises(ValueError, match="完整来源与月键"):
        module.month_adjustment_reference(
            768, 6, True, date(768, 7, 23).toordinal(), "癸卯"
        )


def test_unlisted_post1582_month_still_explains_the_requested_date_convention():
    calendar = calendar_mansion(
        "1697-01-23",
        "05:45:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
    )
    reference = calendar["calendar_reference"][
        "published_calendar_adjustment_reference"
    ]
    assert not reference["selected_month_is_listed"]
    text = day_evidence(calendar)["reading_text"]
    assert "1582年10月15日含当日起用格里历，之前用儒略历" in text
    assert "提供方数据库声明默认西历" in text
    assert "目录表本身未另写这项历制声明" in text
