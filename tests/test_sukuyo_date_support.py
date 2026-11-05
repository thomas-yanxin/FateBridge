"""Primary IANA preimages, boundary bins and unguessed calendar candidates."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_date_support import local_date_support
from fatebridge.core.sukuyo_padas import palace_reference
from fatebridge.services.divination import calculate_sukuyo_compatibility

ROOT = Path(__file__).parent / "data/sukuyo_date_support_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
CHINA = timezone(timedelta(hours=8))


def moment(text):
    return datetime.fromisoformat(text)


def test_primary_iana_excerpts_are_frozen():
    for ref in REFERENCE["sources"]:
        assert (
            hashlib.sha256((ROOT / ref["excerpt_file"]).read_bytes()).hexdigest()
            == ref["excerpt_sha256"]
        )


def test_live_catalog_names_date_support_and_relation_date_provenance_in_schema():
    from fatebridge.services.tool_catalog import CATALOG

    spec = next(s for s in CATALOG if s.key == "sukuyo_compatibility")
    defs = spec.output_model.model_json_schema()["$defs"]
    assert "utc_support_intervals" in defs["SukuyoDateSupport"]["properties"]
    assert "birth_time_imputed" in defs["SukuyoDateSupport"]["properties"]
    assert "person1_calendar_dates" in defs["SukuyoCandidateRelation"]["properties"]
    assert (
        "calendar_date_uncertainty_remains"
        in defs["SukuyoCandidateAnalysis"]["properties"]
    )


@pytest.mark.parametrize(
    "ref", REFERENCE["cases"], ids=lambda c: c["local_date"] + c["zone"]
)
def test_complete_preimages_against_manually_derived_primary_iana_intervals(ref):
    result = local_date_support(ref["local_date"], ref["zone"])
    assert result["possible_calendar_dates"] == ref["calendar_dates"]
    rows = result["utc_support_intervals"]
    assert rows[0]["start_utc_inclusive"] == ref["start_utc_inclusive"]
    assert rows[-1]["end_utc_exclusive"] == ref["end_utc_exclusive"]
    assert (
        result["civil_support_seconds"]
        == (
            moment(ref["end_utc_exclusive"]) - moment(ref["start_utc_inclusive"])
        ).total_seconds()
    )
    for row in rows:
        start, end = moment(row["start_utc_inclusive"]), moment(
            row["end_utc_exclusive"]
        )
        assert start < end
        assert start.astimezone(CHINA).date().isoformat() == row["calendar_date"]
        assert (end - timedelta(microseconds=1)).astimezone(
            CHINA
        ).date().isoformat() == row["calendar_date"]
    assert all(
        a["end_utc_exclusive"] == b["start_utc_inclusive"]
        for a, b in zip(rows, rows[1:])
    )
    assert (
        result["complete_under_loaded_timezone_rules"]
        and not result["birth_time_imputed"]
    )
    if result["timezone_rules"]["database"] == "pytz":
        assert result["timezone_rules"]["iana_version"] == REFERENCE["iana_version"]
        assert len(result["timezone_rules"]["tzif_sha256"]) == 64


@pytest.mark.parametrize("ref", REFERENCE["nonexistent_dates"])
def test_whole_skipped_local_date_is_invalid_not_silently_moved(ref):
    with pytest.raises(ValueError, match="日期.*不存在"):
        calendar_mansion(ref["local_date"], zone=ref["zone"])


@pytest.mark.parametrize(
    "zone,needle_date",
    [("8.0002777777778", "2025-01-28"), ("7.9997222222222", "2025-01-30")],
)
def test_one_second_calendar_candidate_cannot_be_lost_to_hourly_or_noon_sampling(
    zone, needle_date
):
    support = local_date_support("2025-01-29", zone)
    needle = next(
        r for r in support["utc_support_intervals"] if r["calendar_date"] == needle_date
    )
    assert (
        moment(needle["end_utc_exclusive"]) - moment(needle["start_utc_inclusive"])
    ).total_seconds() == 1
    assert len(support["possible_calendar_dates"]) == 2


def test_unknown_foreign_date_returns_both_hko_calendar_branches_and_relations():
    result = calculate_sukuyo_compatibility(
        person1_date="2025-01-29", person1_zone="UTC", person2_date="2025-03-04"
    )
    assert result["status"] == "partial" and result["pair"] is None
    assert result["person1_to_person2"] is None and result["person2_to_person1"] is None
    calendar = result["person1"]["calendar"]
    assert calendar["calendar_date"] is None and calendar["input_datetime"] is None
    assert not calendar["birth_time_known"] and calendar["natal_su27"] is None
    assert [
        (c["calendar_date"], c["lunar_month"], c["lunar_day"], c["natal_su27"])
        for c in calendar["calendar_candidates"]
    ] == [("2025-01-29", 1, 1, "室"), ("2025-01-30", 1, 2, "壁")]
    assert all(
        c["input_datetime"] is None
        and c["input_origin"]
        == "derived_calendar_date_candidate_not_observed_birth_date"
        for c in calendar["calendar_candidates"]
    )
    rows = result["candidate_relation_analysis"]["rows"]
    assert [
        (r["person1_su27"], r["pair"], r["person1_calendar_dates"]) for r in rows
    ] == [("室", "安壊", ["2025-01-29"]), ("壁", "危成", ["2025-01-30"])]
    assert all(not r["applied_to_primary"] for r in rows)
    assert result["person2"]["natal_su27"] == "毕"
    assert "多个可能中国历日" in result["summary"]


def test_dst_start_can_still_determine_one_chinese_date_without_a_birth_hour():
    result = calendar_mansion("1986-05-04", zone="Asia/Shanghai")
    assert result["status"] == "computed" and result["calendar_date"] == "1986-05-04"
    assert result["input_datetime"] is None and not result["birth_time_known"]
    assert result["date_support"]["civil_support_seconds"] == 23 * 3600


def test_complete_different_dates_with_same_mansion_can_resolve_relation_only():
    # HKO2024: Feb9 is lunar12/30; Feb10 is1/1. Both selected T1299 cells are室.
    result = calculate_sukuyo_compatibility(
        person1_date="2024-02-09", person1_zone="UTC", person2_date="2025-03-04"
    )
    c = result["person1"]["calendar"]
    assert [
        (r["lunar_month"], r["lunar_day"], r["natal_su27"])
        for r in c["calendar_candidates"]
    ] == [(12, 30, "室"), (1, 1, "室")]
    assert c["calendar_date"] is None and c["status"] == "partial"
    assert c["natal_su27"] == "室" and result["status"] == "computed"
    assert result["candidate_relation_analysis"]["calendar_date_uncertainty_remains"]
    assert "未确定出生时刻或唯一历日" in result["summary"]


def test_repeated_47_hour_date_preserves_three_chinese_dates():
    result = calendar_mansion("1969-09-30", zone="Pacific/Kwajalein")
    assert result["date_support"]["civil_support_seconds"] == 47 * 3600
    assert [c["calendar_date"] for c in result["calendar_candidates"]] == [
        "1969-09-29",
        "1969-09-30",
        "1969-10-01",
    ]
    assert result["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ]


def test_date_and_hinoo_half_uncertainty_are_both_preserved():
    c = calendar_mansion(
        "2024-08-04", zone="Asia/Tokyo", calendar_profile="hinoo_t1299_host27"
    )
    assert c["candidate_su27s"] == ["柳", "星", "张"]
    assert (
        c["calendar_candidates"][1]["resolution_reason"]
        == "hinoo_short_month_day_part_unresolved"
    )
    assert c["natal_su27"] is None


def test_out_of_range_possible_date_cannot_make_surviving_mansion_or_palace_certain():
    c = calendar_mansion("1900-12-31", zone="UTC")
    assert c["out_of_range_calendar_dates"] == ["1900-12-31"]
    assert c["calendar_candidates"][0]["calendar_date"] == "1901-01-01"
    assert c["natal_su27"] is None
    assert not c["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ]
    assert palace_reference(c)["selected_palace"] is None


def test_conditional_day_reading_keeps_whole_branches_without_picking_a_weekday():
    result = day_evidence(
        calendar_mansion("2025-01-29", zone="UTC"), activity="marriage"
    )
    assert result["weekday"] is None and result["calendar_day"] is None
    assert result["activity_assessment"] is None
    assert len(result["candidate_days"]) == 2
    for alternative in result["candidate_days"]:
        assert alternative["reading_text"] in result["reading_text"]


def test_known_clock_still_rejects_dst_gap_or_fold_and_utc08_does_not_enumerate(
    monkeypatch,
):
    import fatebridge.core.sukuyo_date_support as module

    for day, clock in [("2024-03-10", "02:30:00"), ("2024-11-03", "01:30:00")]:
        with pytest.raises(ValueError):
            calendar_mansion(day, clock, "America/New_York")
    monkeypatch.setattr(
        module,
        "local_date_support",
        lambda *args: pytest.fail("ExplicitUTC+08 needs no uncertainty enumeration"),
    )
    assert calendar_mansion("2025-01-29")["natal_su27"] == "室"


def test_returned_support_mutation_does_not_corrupt_cached_intervals_or_fingerprint():
    first = local_date_support("2025-01-29", "UTC")
    first["utc_support_intervals"][0]["calendar_date"] = "tampered"
    first["possible_calendar_dates"].clear()
    first["timezone_rules"]["provider"] = "tampered"
    second = local_date_support("2025-01-29", "UTC")
    assert second["possible_calendar_dates"] == ["2025-01-29", "2025-01-30"]
    assert second["timezone_rules"]["provider"] == "datetime.timezone"


@pytest.mark.parametrize("day,zone", [("9999-12-31", "UTC")])
def test_unenumerable_upper_extreme_date_raises_a_clear_value_error(day, zone):
    with pytest.raises(ValueError):
        local_date_support(day, zone)


def test_fixed_offset_lower_boundary_uses_exact_intervals_instead_of_datetime_underflow():
    result = local_date_support("0001-01-01", "+08:00", calendar_offset_hours=9)
    assert result["method_id"] == "complete_fixed_offset_lower_boundary_preimage_v1"
    assert result["possible_calendar_dates"] == ["0001-01-01", "0001-01-02"]
    assert result["utc_support_intervals"] == [
        {
            "calendar_date": "0001-01-01",
            "start_utc_inclusive": "0000-12-31T16:00:00+00:00",
            "end_utc_exclusive": "0001-01-01T15:00:00+00:00",
            "start_utc_epoch_seconds": -62135625600,
            "end_utc_epoch_seconds": -62135542800,
        },
        {
            "calendar_date": "0001-01-02",
            "start_utc_inclusive": "0001-01-01T15:00:00+00:00",
            "end_utc_exclusive": "0001-01-01T16:00:00+00:00",
            "start_utc_epoch_seconds": -62135542800,
            "end_utc_epoch_seconds": -62135539200,
        },
    ]
    assert result["civil_support_seconds"] == 86400
    assert result["complete_under_loaded_timezone_rules"]
    assert not result["birth_time_imputed"]
    assert result["enumeration_resolution_seconds"] is None
    assert (
        sum(
            row["end_utc_epoch_seconds"] - row["start_utc_epoch_seconds"]
            for row in result["utc_support_intervals"]
        )
        == 86400
    )


def test_year_zero_reference_branch_is_retained_and_support_is_detached():
    first = local_date_support("0001-01-01", "+15:00", calendar_offset_hours=9)
    assert first["possible_calendar_dates"] == ["0000-12-31", "0001-01-01"]
    first["utc_support_intervals"][0]["calendar_date"] = "changed"
    second = local_date_support("0001-01-01", "+15:00", calendar_offset_hours=9)
    assert second["utc_support_intervals"][0]["calendar_date"] == "0000-12-31"
    sole = local_date_support("0001-01-01", "-15:00", calendar_offset_hours=9)
    assert sole["possible_calendar_dates"] == ["0001-01-02"]
