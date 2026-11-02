"""Complete daily source conformance and explicit host-calendar boundaries."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from zipfile import ZipFile

import pytest

from fatebridge.core import sukuyo_japanese_calendar as japanese
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_calendar_basis import JAPANESE_CALENDAR_BASIS as BASIS
from fatebridge.services.divination import (
    calculate_sukuyo_compatibility,
    calculate_suzhan_analysis,
)
from fatebridge.services.tool_catalog import CATALOG
from scripts.build_sukuyo_japanese_calendar import normalize, parse_day, read_fixture

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/sukuyo_hutime_daily_v1"


def reference(civil, **kwargs):
    return calendar_mansion(civil, zone="+09:00", calendar_basis=BASIS, **kwargs)


def raw_day(value):
    index = (date.fromisoformat(value) - date(1872, 2, 9)).days
    with ZipFile(FIXTURE / "captures.zip") as archive:
        return json.loads(archive.read(f"{index // 100:03}.response.json"))[index % 100]


def test_complete_daily_capture_rebuilds_exact_shipped_data_without_trimmed_nulls():
    files, manifest = read_fixture(FIXTURE)
    data, report = normalize(files, manifest)
    assert data == json.loads(japanese.SOURCE.read_bytes())
    assert report["daily_rows_checked"] == 58057
    assert report["source_months"] == 1966
    assert report["complete_in_lod_domain"] is True
    assert report["complete_methodology_advertised_range"] is False
    assert len(report["null_dates_outside_lod_domain"]) == 739
    assert report["independent_control"]["dates"] == 327
    assert not report["independent_whole_range_verification"]
    assert report["earlier_monthly_source_admission_still_rejected"]
    assert report["reconciled_monthly_discrepancies"][0]["month_start"] == "1989-01-08"


def test_runtime_lunar_fields_match_every_frozen_daily_printed_date():
    first = date(1872, 2, 9)
    count = 0
    with ZipFile(FIXTURE / "captures.zip") as archive:
        for index in range(588):
            rows = json.loads(archive.read(f"{index:03}.response.json"))
            for offset, row in enumerate(rows):
                if row is None:
                    continue
                civil = first + timedelta(days=index * 100 + offset)
                year, month, day, leap = japanese.lunar_fields(civil)
                assert f"{year}|{'閏' if leap else ''}{month}|{day}" == row["text"]
                count += 1
    assert count == 58057


def test_day_period_false_is_not_an_enclosing_month_false():
    row = raw_day("2017-06-24")
    assert row["isLeap"] == "False" and row["ofMonth.isLeap"] == "True"
    assert parse_day(row, date(2017, 6, 24)) == (2017, 5, 1, True)
    row["ofMonth.isLeap"] = "False"
    with pytest.raises(ValueError, match="enclosing-month"):
        parse_day(row, date(2017, 6, 24))


@pytest.mark.parametrize(
    "civil,expected",
    [
        ("1872-02-09", (1872, 1, 1, False)),
        ("1947-03-23", (1947, 3, 1, False)),
        ("1947-04-21", (1947, 3, 1, True)),
        ("1969-08-13", (1969, 7, 1, False)),
        ("1989-01-08", (1988, 12, 1, False)),
        ("1989-02-05", (1988, 12, 29, False)),
        ("1989-02-06", (1989, 1, 1, False)),
        ("2017-06-24", (2017, 5, 1, True)),
        ("2031-01-22", (2030, 12, 29, False)),
    ],
)
def test_calendar_pipeline_preserves_published_exceptions_and_lunar_year(
    civil, expected
):
    actual = reference(civil)
    assert (
        tuple(
            actual[k]
            for k in ["lunar_year", "lunar_month", "lunar_day", "is_leap_month"]
        )
        == expected
    )
    assert actual["calendar_timezone"] == "UTC+09:00"
    assert (
        actual["calendar_reference"]["source_bundle_sha256"]
        == hashlib.sha256(japanese.SOURCE.read_bytes()).hexdigest()
    )
    assert not actual["calendar_reference"]["historical_local_time_reconstruction"]


def test_birth_zone_host_calendar_and_mansion_profile_are_independent_choices():
    chinese = calendar_mansion("2017-06-24", "12:00:00", "Asia/Tokyo")
    selected = calendar_mansion(
        "2017-06-24", "12:00:00", "Asia/Tokyo", calendar_basis=BASIS
    )
    assert (
        chinese["lunar_month"],
        chinese["is_leap_month"],
        chinese["natal_su27"],
    ) == (6, False, "鬼")
    assert (
        selected["lunar_month"],
        selected["is_leap_month"],
        selected["natal_su27"],
    ) == (5, True, None)
    assert selected["candidate_su27s"] == ["参"]
    assert (
        reference("2017-06-24", leap_month_policy="repeat_month")["natal_su27"] == "参"
    )
    default_zone = calendar_mansion("2017-06-24", "12:00:00", calendar_basis=BASIS)
    assert default_zone["input_timezone"] == "+08:00"


def test_hinoo_uses_japanese_adjacent_months_without_invented_halves_or_precedence():
    unknown = reference("2024-08-04", calendar_profile="hinoo_t1299_host27")
    assert unknown["natal_su27"] is None and unknown["candidate_su27s"] == ["星", "张"]
    assert (
        reference(
            "2024-08-04",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        )["natal_su27"]
        == "星"
    )
    leap = reference(
        "2017-06-24",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    assert leap["natal_su27"] is None and leap["candidate_su27s"] == ["鬼", "参"]
    assert leap["resolution_reason"] == "hinoo_leap_short_month_precedence_unresolved"
    assert (
        leap["profile_calculation"]["short_month_assignment"]["previous_lunar"][
            "lunar_month"
        ]
        == 5
    )
    assert (
        reference(
            "2017-06-24",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="second_half",
        )["natal_su27"]
        == "参"
    )
    first = reference("1872-02-09", calendar_profile="hinoo_t1299_host27")
    assert first["resolution_reason"] == "hinoo_previous_lunar_context_unavailable"
    assert not first["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ]


def test_unknown_time_retains_complete_utc09_dates_and_repeated_civil_date():
    china = calendar_mansion("2017-06-23", zone="UTC")
    assert (
        china["date_support"]["utc_support_intervals"][1]["start_utc_inclusive"]
        == "2017-06-23T16:00:00+00:00"
    )
    result = calendar_mansion("2017-06-23", zone="UTC", calendar_basis=BASIS)
    assert result["date_support"]["possible_calendar_dates"] == [
        "2017-06-23",
        "2017-06-24",
    ]
    assert (
        result["date_support"]["utc_support_intervals"][1]["start_utc_inclusive"]
        == "2017-06-23T15:00:00+00:00"
    )
    assert result["input_datetime"] is None
    assert all(
        c["calendar_basis"] == BASIS and not c["birth_time_known"]
        for c in result["calendar_candidates"]
    )
    text = day_evidence(result)["reading_text"]
    assert "多个可能日本旧历参考历日" in text and "UTC+09" in text
    repeated = calendar_mansion(
        "1969-09-30", zone="Pacific/Kwajalein", calendar_basis=BASIS
    )
    assert repeated["date_support"]["civil_support_seconds"] == 47 * 3600
    assert repeated["date_support"]["possible_calendar_dates"] == [
        "1969-09-29",
        "1969-09-30",
        "1969-10-01",
    ]


def test_utc09_boundary_preserves_microseconds_without_rounding():
    before = calendar_mansion(
        "2017-06-23", "14:59:59.999999", "UTC", calendar_basis=BASIS
    )
    after = calendar_mansion("2017-06-23", "15:00:00", "UTC", calendar_basis=BASIS)
    assert before["calendar_date"] == "2017-06-23"
    assert after["calendar_date"] == "2017-06-24"
    assert before["is_leap_month"] is False and after["is_leap_month"] is True


def test_out_of_range_candidate_cannot_be_dropped_to_make_a_definite_result():
    result = calendar_mansion("2031-01-22", zone="UTC", calendar_basis=BASIS)
    assert result["out_of_range_calendar_dates"] == ["2031-01-23"]
    assert result["natal_su27"] is None
    assert not result["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ]
    with pytest.raises(ValueError, match="范围外"):
        reference("2031-01-23")
    with pytest.raises(ValueError, match="calendar_basis"):
        calendar_mansion("2025-03-04", calendar_basis="guess_from_country")


def test_compatibility_uses_one_declared_basis_for_both_people():
    result = calculate_sukuyo_compatibility(
        person1_date="2017-06-24",
        person1_zone="+09:00",
        person2_date="2017-07-23",
        person2_zone="+09:00",
        calendar_basis=BASIS,
    )
    assert result["status"] == "partial" and result["pair"] is None
    assert all(
        result[p]["calendar"]["calendar_basis"] == BASIS for p in ["person1", "person2"]
    )
    assert result["person1"]["calendar"]["lunar_month"] == 5
    assert result["person2"]["calendar"]["lunar_month"] == 6
    assert "calendar_reference" in result["rulesets"]


def test_host_basis_never_moves_the_physical_sky_and_native_text_keeps_provenance():
    payload = dict(date="2017-06-24", time="12:00:00", zone="+09:00", szchart=1)
    china = calculate_suzhan_analysis(**payload)
    japan = calculate_suzhan_analysis(**payload, calendar_basis=BASIS)
    assert "error" not in china and "error" not in japan, (china, japan)
    assert china["chart"] == japan["chart"] and china["astronomy"] == japan["astronomy"]
    assert china["params"] == japan["params"]
    assert japan["sukuyo"]["weekday"]["basis"] == "modern_utc_plus09_civil_midnight"
    assert (
        japan["sukuyo"]["lower_methods"]["weekday"]["basis"]
        == "modern_utc_plus09_civil_midnight"
    )
    assert "未核定为逐年神宫原刊" in japan["sukuyo"]["reading_text"]
    assert "所选日本旧历参考" in japan["sukuyo"]["calendar_day"]["scope"]
    assert "中国历日2017-06-24" not in japan["sukuyo"]["reading_text"]


def test_source_index_metadata_cannot_be_poisoned_or_given_a_replaced_file_hash(
    monkeypatch, tmp_path
):
    raw = japanese.SOURCE.read_bytes()
    path = tmp_path / "japanese.json"
    path.write_bytes(raw)
    monkeypatch.setattr(japanese, "SOURCE", path)
    original = reference("2017-06-24")
    original["calendar_reference"]["source_provenance"][0]["basis"] = "fabricated"
    path.write_text('{"not":"the captured source"}')
    later = reference("2017-06-24")
    assert later["lunar_month"] == 5 and later["is_leap_month"]
    assert (
        later["calendar_reference"]["source_bundle_sha256"]
        == hashlib.sha256(raw).hexdigest()
    )
    assert later["calendar_reference"]["source_provenance"][0]["basis"] != "fabricated"


def test_default_chinese_path_never_loads_the_optional_japanese_table(monkeypatch):
    monkeypatch.setattr(japanese, "SOURCE", ROOT / "missing-japanese-reference.json")
    assert calendar_mansion("2025-03-04") == calendar_mansion(
        "2025-03-04", calendar_basis="chinese_hko_utc08"
    )
    for key in ["suzhan", "sukuyo_compatibility"]:
        spec = next(s for s in CATALOG if s.key == key)
        assert (
            spec.request_model.model_fields["calendar_basis"].default
            == "chinese_hko_utc08"
        )
        props = spec.output_model.model_json_schema()["$defs"][
            "SukuyoCalendarReference"
        ]["properties"]
        assert "source_bundle_sha256" in props and "date_provenance" in props
