"""The named historical reference is source-bound, not a consensus calendar."""

import csv
import hashlib
import io
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_historical_calendar as historical
from fatebridge.core.sukuyo import calendar_mansion, day_evidence, lunar_mansion
from fatebridge.services.divination import calculate_sukuyo_compatibility
from fatebridge.validation.sukuyo_historical_sources import gregorian_ordinal, normalize
from scripts.build_sukuyo_historical_calendar import read_fixture
from scripts.check_sukuyo_historical_daily import verify_daily_controls

ROOT = Path(__file__).resolve().parents[1]
BASIS = "japanese_naoj_historical_utc09"


def reference(value, **kwargs):
    return calendar_mansion(value, calendar_basis=BASIS, zone="+09:00", **kwargs)


def test_all_683734_reference_dates_follow_raw_naoj_month_start_records():
    files, manifest = read_fixture(
        ROOT / "tests/fixtures/sukuyo_historical_calendar_v1"
    )
    starts = {}
    for year in range(1873):
        rows = csv.reader(
            io.StringIO(files[f"naoj-{year:04}.response.bin"].decode("cp932"))
        )
        next(rows)
        for row in rows:
            year_civil, month, day = map(int, row[0].strip().split("/"))
            ordinal = gregorian_ordinal(year_civil, month, day)
            lunar = re.search(r"(閏)?(\d{2})月01日$", row[1])
            assert lunar
            fields = (int(row[2]) - 660, int(lunar[2]), bool(lunar[1]))
            assert starts.setdefault(ordinal, fields) == fields
    ordered = sorted(starts)
    index = 0
    checked = 0
    for ordinal in range(1, date(1873, 1, 1).toordinal()):
        while index + 1 < len(ordered) and ordered[index + 1] <= ordinal:
            index += 1
        year, month, leap = starts[ordered[index]]
        assert historical.lunar_fields(date.fromordinal(ordinal)) == (
            year,
            month,
            ordinal - ordered[index] + 1,
            leap,
        )
        checked += 1
    assert checked == 683734
    assert (
        historical.reference_metadata()["source_archive_sha256"]
        == manifest["archive_sha256"]
    )


@pytest.mark.parametrize(
    "value,fields",
    [
        ("0001-01-01", (0, 11, 20, False)),
        ("0806-01-28", (806, 1, 1, False)),
        ("1872-12-30", (1872, 12, 1, False)),
        ("1872-12-31", (1872, 12, 2, False)),
    ],
)
def test_source_edge_dates_and_legal_two_day_month_are_explicit(value, fields):
    result = reference(value)
    assert (
        tuple(
            result[k]
            for k in ["lunar_year", "lunar_month", "lunar_day", "is_leap_month"]
        )
        == fields
    )
    assert result["calendar_backend"] == "frozen_naoj_historical_month_starts"
    source = result["calendar_reference"]
    assert not source["historical_local_time_reconstruction"]
    assert not source["complete_provider_advertised_historical_range"]
    assert source["month_truncated_by_calendar_reform"] == value.startswith("1872-12-3")
    if source["month_truncated_by_calendar_reform"]:
        assert source["source_month_length_days"] == 2
        assert "截为两天" in day_evidence(result)["reading_text"]


def test_all_retained_source_disagreement_dates_have_unapplied_alternative_fields():
    files, manifest = read_fixture(
        ROOT / "tests/fixtures/sukuyo_historical_calendar_v1"
    )
    _, report = normalize(files, manifest)
    checked = 0
    for row in report["cross_source_disagreement_intervals"]:
        start = date.fromisoformat(row["start"])
        for offset in range(row["days"]):
            civil = start + timedelta(days=offset)
            source = historical.date_reference(civil)
            comparison = source["cross_source_comparison"]
            assert comparison is not None
            expected = row["hutime_first_fields"].copy()
            expected[2] += offset
            assert comparison["control_fields"] == expected
            assert not comparison["control_applied_to_primary"]
            assert comparison["partly_shared_historical_source_corpus"]
            checked += 1
    assert checked == 210
    assert historical.date_reference(date(9, 12, 2))["cross_source_comparison"] is None
    assert historical.date_reference(date(10, 1, 2))["cross_source_comparison"] is None


def test_same_mansion_cannot_hide_month_day_and_leap_disagreement():
    result = reference("0820-03-22")
    assert (result["lunar_month"], result["lunar_day"], result["is_leap_month"]) == (
        2,
        1,
        False,
    )
    assert result["natal_su27"] == lunar_mansion(1, 30) == "奎"
    source = result["calendar_reference"]
    assert source["cross_source_comparison"]["control_fields"] == [820, 1, 30, True]
    assert not source["historical_calendar_acceptance"]
    text = day_evidence(result)["reading_text"]
    assert "820年闰1月30日" in text and "与所选NAOJ参考不同" in text


def test_compatibility_native_text_retains_each_unknown_date_branch_disagreement():
    pair = calculate_sukuyo_compatibility(
        person1_date="0820-03-22",
        person1_zone="UTC",
        person2_date="0820-03-22",
        person2_zone="+09:00",
        calendar_basis=BASIS,
    )
    assert "参考日期0820-03-22" in pair["summary"]
    assert "参考日期0820-03-23" in pair["summary"]
    assert "820年闰1月30日" in pair["summary"]
    assert "820年2月1日" in pair["summary"]
    assert "分歧保留且未代入主宿" in pair["summary"]
    assert "不表示该年代已行用本经" in pair["summary"]


def test_hinoo_previous_month_uses_the_same_historical_source():
    first = reference(
        "0806-09-20",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    second = reference(
        "0806-09-20",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="second_half",
    )
    assert (first["natal_su27"], second["natal_su27"]) == ("轸", "角")
    assert (
        first["profile_calculation"]["short_month_assignment"]["previous_lunar"][
            "lunar_day"
        ]
        == 29
    )
    assert (
        reference("0806-09-20", calendar_profile="hinoo_t1299_host27")["natal_su27"]
        is None
    )


def test_known_fixed_clock_and_unknown_lower_boundary_do_not_drop_year_zero():
    known = calendar_mansion("0001-01-01", "00:00:00", "+08:00", calendar_basis=BASIS)
    assert known["calendar_date"] == "0001-01-01"
    unknown = calendar_mansion("0001-01-01", zone="+08:00", calendar_basis=BASIS)
    assert [r["calendar_date"] for r in unknown["calendar_candidates"]] == [
        "0001-01-01",
        "0001-01-02",
    ]
    assert unknown["natal_su27"] is None and not unknown["birth_time_known"]
    assert unknown["calendar_backend"] == "frozen_naoj_historical_month_starts"
    boundary = calendar_mansion("0001-01-01", zone="+15:00", calendar_basis=BASIS)
    assert boundary["out_of_range_calendar_dates"] == ["0000-12-31"]
    assert boundary["natal_su27"] is None
    assert not boundary["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ]


def test_direct_daily_controls_preserve_all_source_disagreements_and_reform():
    report = verify_daily_controls()
    assert report["naoj_inside_host_range_daily_dates"] == 225
    assert report["hutime_direct_disagreement_dates"] == 210
    assert report["naoj_calculation_to_daily_source_mismatches"] == []
    assert report["hutime_daily_to_retained_variant_mismatches"] == []
    assert not report["separate_post_reform_legal_calendar_controls"][0][
        "admitted_as_old_lunisolar_date"
    ]


def test_upper_boundary_remains_incomplete_and_never_switches_to_modern_japan():
    with pytest.raises(ValueError):
        reference("1873-01-01")
    result = calendar_mansion("1872-12-31", zone="UTC", calendar_basis=BASIS)
    assert result["out_of_range_calendar_dates"] == ["1873-01-01"]
    assert not result["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ]
    pair = calculate_sukuyo_compatibility(
        person1_date="1872-12-31",
        person1_zone="UTC",
        person2_date="1872-12-31",
        person2_zone="+09:00",
        calendar_basis=BASIS,
    )
    assert pair["pair"] is None and pair["status"] == "partial"


def test_returned_source_metadata_and_index_fingerprint_stay_coupled(
    monkeypatch, tmp_path
):
    raw = historical.SOURCE.read_bytes()
    path = tmp_path / "historical.json"
    path.write_bytes(raw)
    monkeypatch.setattr(historical, "SOURCE", path)
    first = historical.date_reference(date(820, 3, 22))
    first["cross_source_comparison"]["control_fields"][1] = 99
    first["source_provenance"].clear()
    path.write_text('{"wrong":"new disk version"}')
    later = historical.date_reference(date(820, 3, 22))
    assert later["source_bundle_sha256"] == hashlib.sha256(raw).hexdigest()
    assert later["cross_source_comparison"]["control_fields"] == [820, 1, 30, True]
    assert later["source_provenance"]


def test_default_and_modern_japanese_backends_do_not_load_historical_table(monkeypatch):
    monkeypatch.setattr(historical, "SOURCE", ROOT / "no-historical-table.json")
    assert calendar_mansion("2025-03-04")["natal_su27"] == "毕"
    assert calendar_mansion(
        "2017-06-24", zone="+09:00", calendar_basis="japanese_hutime_1002_1_utc09"
    )["is_leap_month"]
