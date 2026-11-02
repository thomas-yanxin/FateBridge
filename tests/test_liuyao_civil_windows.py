"""Independent TZif references for actual UTC components of the local day."""

import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fatebridge.core.liuyao_judgment import timing_candidates
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from fatebridge.utils.civil_intervals import local_interval_preimages
from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata

REFERENCE = Path(__file__).parent / "fixtures/liuyao_civil_windows_v26"
CASES = [
    (corpus, case)
    for corpus, file in [
        ("system", "cases.json"),
        ("runtime_pytz", "cases-runtime.json"),
    ]
    for case in json.loads((REFERENCE / file).read_text())["cases"]
]
PUBLIC = json.loads((REFERENCE / "public-inputs.json").read_text())
ROOT = "liuyao_evidence.conditional_analysis.timing_candidates"
UTC = timezone.utc


def intervals(case):
    return [
        tuple(datetime.fromisoformat(value) for value in pair)
        for pair in case["expected_utc_intervals"]
    ]


def assert_public_windows(result, case):
    timing = result["liuyao_evidence"]["conditional_analysis"]["timing_candidates"]
    windows = timing["windows"]
    starts = [datetime.fromisoformat(w["start_at"]).astimezone(UTC) for w in windows]
    assert starts == sorted(starts)
    for expected in PUBLIC["reference"]:
        if expected["zone"] != case["input"]["zone"]:
            continue
        rows = [w for w in windows if w["effective_date"] == expected["effective_date"]]
        assert [
            (
                datetime.fromisoformat(w["start_at"]).astimezone(UTC),
                datetime.fromisoformat(w["end_at"]).astimezone(UTC),
            )
            for w in rows
        ] == intervals(expected)
        assert len(rows) == len(expected["expected_utc_intervals"])
        for index, row in enumerate(rows, start=1):
            civil = row["civil_interval"]
            assert civil["interval_index"] == index
            assert civil["interval_count"] == len(rows)
            low, high = intervals(expected)[index - 1]
            assert datetime.fromisoformat(civil["start_utc"]) == low
            assert datetime.fromisoformat(civil["end_utc"]) == high
            assert civil["duration_seconds"] == (high - low).total_seconds()
            assert "日柱标签" in civil["scope"]


def test_reference_bytes_and_source_provider_are_exact():
    for name in ["freeze.json", "runtime-freeze.json", "public-freeze.json"]:
        frozen = json.loads((REFERENCE / name).read_text())
        for key in ["files_sha256", "source_files_sha256"]:
            for file, digest in frozen.get(key, {}).items():
                # The original system receipt keys source names relative to
                # sources/, while the provider supplement includes that prefix.
                if key == "source_files_sha256" and name == "freeze.json":
                    file = "sources/" + file
                assert (
                    hashlib.sha256((REFERENCE / file).read_bytes()).hexdigest()
                    == digest
                )
    manifest = json.loads((REFERENCE / "pytz-manifest.json").read_text())
    # The project reads pytz bytes through ZoneInfo; OS TZPATH is a separate corpus.
    for name in {x["input"]["zone"] for x in PUBLIC["cases"]}:
        metadata = timezone_rules_metadata(name)
        assert metadata["database"] == "pytz"
        assert metadata["tzif_sha256"] == manifest["zones"][name]["sha256"]


@pytest.mark.parametrize(
    "corpus,case",
    CASES,
    ids=[f"{corpus}:{x['zone']}:{x['effective_date']}" for corpus, x in CASES],
)
def test_exact_preimages_match_independent_constant_offset_intersections(corpus, case):
    raw = (REFERENCE / "sources" / (case["tzif_sha256"] + ".tzif")).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == case["tzif_sha256"]
    zone = ZoneInfo.from_file(io.BytesIO(raw), key=case["zone"])
    day = datetime.fromisoformat(case["effective_date"])
    start, end = day - timedelta(hours=1), day + timedelta(hours=23)
    actual = local_interval_preimages(start, end, zone)
    assert actual == intervals(case)
    assert [(b - a).total_seconds() for a, b in actual] == case[
        "expected_durations_seconds"
    ]
    for low, high in actual:
        for instant in [low, low + (high - low) // 2, high - timedelta(microseconds=1)]:
            assert start <= instant.astimezone(zone).replace(tzinfo=None) < end
        for instant in [low - timedelta(microseconds=1), high]:
            assert not start <= instant.astimezone(zone).replace(tzinfo=None) < end


def test_wholly_missing_local_interval_has_no_guessed_instant():
    zone = parse_timezone_name("Pacific/Apia")
    assert (
        local_interval_preimages(
            datetime(2011, 12, 30), datetime(2011, 12, 30, 23), zone
        )
        == []
    )


@pytest.mark.parametrize("hours", [0, 5.5, -12])
def test_fixed_offset_day_retains_ordinary_continuous_interval(hours):
    zone = timezone(timedelta(hours=hours))
    start, end = datetime(2000, 1, 6, 23), datetime(2000, 1, 7, 23)
    assert local_interval_preimages(start, end, zone) == [
        (
            start.replace(tzinfo=zone).astimezone(UTC),
            end.replace(tzinfo=zone).astimezone(UTC),
        )
    ]


@pytest.mark.parametrize(
    "start,end",
    [
        (datetime(2000, 1, 1), datetime(2000, 1, 1)),
        (datetime(2000, 1, 2), datetime(2000, 1, 1)),
        (datetime(2000, 1, 1, tzinfo=UTC), datetime(2000, 1, 2)),
        (datetime(2000, 1, 1), datetime(2000, 1, 2, tzinfo=UTC)),
    ],
)
def test_invalid_interval_bounds_are_rejected(start, end):
    with pytest.raises(ValueError, match="ordered naive"):
        local_interval_preimages(start, end, UTC)


@pytest.mark.parametrize("case", PUBLIC["cases"], ids=lambda x: x["input"]["zone"])
def test_public_day_windows_keep_true_components_and_snapshot_labels(case):
    result = build_sixyao_result(**case["input"])
    assert_public_windows(result, case)
    windows = result["liuyao_evidence"]["conditional_analysis"]["timing_candidates"][
        "windows"
    ]
    for row in windows:
        if civil := row.get("civil_interval"):
            assert (
                f"日柱标签{row['effective_date']}（{row['day_ganzhi']}）"
                in result["snapshot_text"]
            )
            assert (
                f"实际UTC分段{civil['interval_index']}/{civil['interval_count']}"
                in result["snapshot_text"]
            )
            assert civil["start_utc"] in result["snapshot_text"]
            assert civil["end_utc"] in result["snapshot_text"]


@pytest.mark.parametrize("days", [0, 12])
def test_original_valid_public_reproducer_no_longer_blames_the_cast_clock(days):
    result = build_sixyao_result(
        date="2011-12-26",
        time="12:00:00",
        zone="Pacific/Apia",
        gua_code="111111",
        changed_code="111111",
        focus_line=6,
        timing_days=days,
    )
    timing = result["liuyao_evidence"]["conditional_analysis"]["timing_candidates"]
    assert timing["status"] == (
        "not_requested" if days == 0 else "condition_windows_only"
    )


@pytest.mark.parametrize(
    "zone,day,clock,error",
    [
        ("Pacific/Apia", "2011-12-30", "12:00:00", "nonexistent local time"),
        ("America/Goose_Bay", "1988-10-29", "23:30:00", "ambiguous local time"),
    ],
)
def test_invalid_user_clock_validation_is_unchanged(zone, day, clock, error):
    with pytest.raises(ValueError, match=error):
        build_sixyao_result(
            date=day,
            time=clock,
            zone=zone,
            gua_code="111111",
            focus_line=1,
            timing_days=12,
        )


def test_clipping_compares_actual_instants_in_the_second_fold():
    zone = parse_timezone_name("America/Goose_Bay")
    moment = datetime(1988, 10, 30, 3, 30, tzinfo=UTC).astimezone(zone)
    assert moment.fold == 1
    timing = timing_candidates(
        moment=moment,
        days=1,
        selected={"location": "visible", "branch": "午"},
        month="戌",
        original_ganzhi="戊午",
        line={"change": False},
    )
    assert len(timing["windows"]) == 1
    civil = timing["windows"][0]["civil_interval"]
    assert civil["interval_index"] == 2 and civil["interval_count"] == 2
    assert civil["start_utc"] == "1988-10-30T03:30:00+00:00"
    assert civil["end_utc"] == "1988-10-31T03:00:00+00:00"
    assert civil["duration_seconds"] == 84600
