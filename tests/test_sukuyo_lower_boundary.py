"""Full timezone support at the historical host's lower representable edge."""

import struct
from datetime import date
from io import BytesIO
from zoneinfo import ZoneInfo

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_date_support import (
    _support,
    _wall_second_support,
    local_date_support,
)
from fatebridge.services.divination import calculate_sukuyo_compatibility
from fatebridge.utils.timezones import parse_timezone_name
from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)

BASIS = "japanese_naoj_historical_utc09"


@pytest.mark.parametrize(
    "zone,offset,dates",
    [
        ("Asia/Tokyo", 33539, ["0000-12-31", "0001-01-01"]),
        ("Europe/London", -75, ["0001-01-01", "0001-01-02"]),
        ("Pacific/Apia", 45184, ["0000-12-31", "0001-01-01"]),
    ],
)
def test_second_precision_offsets_preserve_complete_year_zero_support(
    zone, offset, dates
):
    result = local_date_support("0001-01-01", zone, calendar_offset_hours=9)
    assert result["possible_calendar_dates"] == dates
    assert result["method_id"] == "complete_local_wall_second_fold_preimage_v1"
    assert result["civil_support_seconds"] == 86400
    assert result["complete_under_loaded_timezone_rules"]
    assert not result["birth_time_imputed"]
    assert len(result["timezone_rules"]["tzif_sha256"]) == 64
    rows = result["utc_support_intervals"]
    assert rows[0]["start_utc_epoch_seconds"] == -62135596800 - offset
    assert rows[-1]["end_utc_epoch_seconds"] == -62135510400 - offset
    assert (
        sum(r["end_utc_epoch_seconds"] - r["start_utc_epoch_seconds"] for r in rows)
        == 86400
    )
    assert all(
        a["end_utc_exclusive"] == b["start_utc_inclusive"]
        for a, b in zip(rows, rows[1:])
    )
    result["utc_support_intervals"][0]["calendar_date"] = "mutated"
    assert (
        local_date_support("0001-01-01", zone, calendar_offset_hours=9)[
            "possible_calendar_dates"
        ]
        == dates
    )


@pytest.mark.parametrize("day", ["0001-01-01", "0001-01-02"])
def test_unknown_early_tokyo_never_drops_the_previous_host_day(day):
    r = calendar_mansion(day, zone="Asia/Tokyo", calendar_basis=BASIS)
    assert r["status"] == "partial" and r["natal_su27"] is None
    assert not r["birth_time_known"]
    assert r["calendar_date"] is None
    expected = ["0000-12-31"] if day.endswith("01") else []
    assert r["out_of_range_calendar_dates"] == expected
    assert r["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ] == (not expected)
    assert [c["calendar_date"] for c in r["calendar_candidates"]] == (
        ["0001-01-01"] if expected else ["0001-01-01", "0001-01-02"]
    )
    text = day_evidence(r)["reading_text"]
    assert "未补造出生时刻" in text
    assert "当地日期的UTC原像已完整枚举" in text
    assert "本次加载的Asia/Tokyo时区规则和固定UTC+09:00参考日界" in text
    assert "不穷尽所有古代时制" in text
    pair = calculate_sukuyo_compatibility(
        person1_date=day,
        person1_zone="Asia/Tokyo",
        person2_date=day,
        person2_zone="+09:00",
        calendar_basis=BASIS,
    )
    assert "当地日期的UTC原像已完整枚举" in pair["summary"]
    assert "不穷尽所有古代时制" in pair["summary"]
    if expected:
        assert "0000-12-31" in text
        assert "仍有范围外参考日，已算出的宿候选不穷尽" in text
    else:
        assert "没有范围外参考日，已列参考日期及宿候选在本次声明档案内完整" in text


@pytest.mark.parametrize(
    "zone,clock", [("Asia/Tokyo", "00:19:00"), ("Pacific/Apia", "12:00:00")]
)
def test_known_clock_can_have_unrepresentable_utc_but_valid_reference_date(zone, clock):
    r = calendar_mansion("0001-01-01", clock, zone, calendar_basis=BASIS)
    assert r["calendar_date"] == "0001-01-01"
    assert (r["lunar_year"], r["lunar_month"], r["lunar_day"]) == (0, 11, 20)
    assert r["natal_su27"] == "轸"
    assert r["birth_time_known"]
    assert not r["calendar_reference"]["historical_local_time_reconstruction"]


def test_known_clock_really_before_the_supported_host_date_remains_rejected():
    with pytest.raises(ValueError, match="超出可表示"):
        calendar_mansion("0001-01-01", "00:18:58", "Asia/Tokyo", calendar_basis=BASIS)


@pytest.mark.parametrize(
    "day,zone",
    [
        ("2025-03-09", "America/New_York"),
        ("2025-11-02", "America/New_York"),
        ("1969-09-30", "Pacific/Kwajalein"),
        ("1901-01-01", "Asia/Tokyo"),
        ("2025-10-05", "Australia/Lord_Howe"),
    ],
)
def test_local_enumeration_agrees_with_independent_utc_enumeration(day, zone):
    # These two directions use distinct algorithms. Include 23/25-hour days,
    # a 47-hour repeated date, a 30-minute jump and a second-resolution offset.
    expected, count, _ = _support(day, zone, 9)
    actual, actual_count = _wall_second_support(
        date.fromisoformat(day), parse_timezone_name(zone), 9
    )
    epoch = (date(1970, 1, 1).toordinal() - 1) * 86400
    assert actual_count == count
    assert actual == tuple(
        (d, int(a.timestamp()) + epoch, int(b.timestamp()) + epoch)
        for d, a, b in expected
    )


def test_local_enumeration_rejects_a_wholly_skipped_date():
    with pytest.raises(ValueError, match="不存在"):
        _wall_second_support(date(2011, 12, 30), parse_timezone_name("Pacific/Apia"), 9)


def _synthetic_zone(before, after):
    # A genuine 64-bit TZif transition at 0001-01-01 12:00 UT, independent of
    # platform time_t. The first compatibility block has no transitions.
    def header(times, types):
        return b"TZif2" + b"\0" * 15 + struct.pack(">6I", 0, 0, 0, times, types, 4)

    initial = struct.pack(">iBB", before, 0, 0) + b"OLD\0"
    transition = -62135553600
    later = struct.pack(">qB", transition, 1)
    later += struct.pack(">iBBiBB", before, 0, 0, after, 0, 0) + b"NEW\0"
    return ZoneInfo.from_file(
        BytesIO(header(0, 1) + initial + header(1, 2) + later + b"\n\n")
    )


@pytest.mark.parametrize(
    "before,after,begin,end", [(0, 3600, 0, 82800), (3600, 0, -3600, 86400)]
)
def test_lower_boundary_does_not_assume_the_midnight_offset_is_constant(
    before, after, begin, end
):
    intervals, count = _wall_second_support(
        date(1, 1, 1), _synthetic_zone(before, after), 9
    )
    assert count == end - begin
    assert intervals == (("0001-01-01", begin, 54000), ("0001-01-02", 54000, end))


@pytest.mark.parametrize("clock", [None, "00:19:00"])
def test_early_boundary_across_actual_rest_native_mcp_cli(monkeypatch, capsys, clock):
    payload = {
        "person1_date": "0001-01-01",
        "person1_zone": "Asia/Tokyo",
        "person2_date": "0001-01-01",
        "person2_zone": "+09:00",
        "calendar_basis": BASIS,
    }
    if clock:
        payload["person1_time"] = clock
    run_transport_check(
        monkeypatch,
        capsys,
        "sukuyo_compatibility",
        payload,
        [
            "person1",
            "person2",
            "status",
            "pair",
            "candidate_relation_analysis",
            "summary",
        ],
    )
