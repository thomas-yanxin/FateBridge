"""A reproduced provider defect must remain a failed source-admission result."""

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs
from zipfile import ZipFile

import pytest

from fatebridge.core.sukuyo import calendar_mansion
from fatebridge.validation.sukuyo_calendar_sources import (
    audit_candidate,
    parse_month,
    require_importable,
)

FIXTURE = Path(__file__).parents[1] / "data/sukuyo_hutime_v1"
ROOT = Path(__file__).resolve().parents[2]


def captured_months():
    manifest = json.loads((FIXTURE / "manifest.json").read_bytes())
    with ZipFile(FIXTURE / "captures.zip") as archive:
        for batch in manifest["month_batches"]:
            dates = parse_qs(archive.read(batch["request"]).decode())["ival"][
                0
            ].splitlines()
            rows = json.loads(archive.read(batch["response"]))
            for civil, row in zip(dates, rows):
                if row is not None:
                    yield parse_month(row, civil), row


def sample():
    return next((m, r) for m, r in captured_months() if m.leap and m.year == 2017)


def test_quarantine_retains_all_observed_findings_and_narrow_independent_control():
    report = audit_candidate(FIXTURE)
    assert report["query_count"] == 2101
    assert report["unique_months"] == 1966
    assert report["documented_range_inclusive"] == ["1872-02-09", "2033-01-30"]
    assert report["observed_month_extent"] == ["1872-02-09", "2031-01-23"]
    assert len(report["missing_query_dates"]) == 27
    assert len(report["month_interval_conflicts"]) == 1
    assert report["month_label_sequence_errors"] == []
    conflict = report["month_interval_conflicts"][0]
    assert conflict["previous"]["end_exclusive"] == "1989-02-07"
    assert conflict["next"]["start"] == "1989-02-06"
    assert report["independent_control"]["dates"] == 327
    assert report["independent_control"]["disagreements"] == []
    assert report["independent_control"]["whole_candidate_range_verified"] is False
    assert len(report["published_id_probe"]["null_query_dates"]) == 6
    assert report["day_month_control"]["disagreements"] == [
        {
            "date": "1989-02-06",
            "day_response": [1989, 1, 1, False],
            "month_period_derived_dates": [[1988, 12, 30, False], [1989, 1, 1, False]],
        }
    ]
    assert not report["structural_import_eligible"]
    assert not report["runtime_calendar_enabled"]
    assert not report["historical_calendar_acceptance"]
    with pytest.raises(ValueError, match="Candidate calendar rejected"):
        require_importable(report)


def test_cli_report_reproduction_still_exits_two_for_rejected_source(tmp_path):
    output = tmp_path / "audit.json"
    command = [
        sys.executable,
        str(ROOT / "scripts/sukuyo/audit_sukuyo_japanese_candidate.py"),
        "--output",
        str(output),
    ]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 2, first.stderr
    assert json.loads(output.read_text()) == audit_candidate(FIXTURE)
    repeated = subprocess.run([*command, "--check"], capture_output=True, text=True)
    assert repeated.returncode == 2, repeated.stderr
    assert json.loads(repeated.stdout)["structural_import_eligible"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("isLeap", False),
        ("isLeap", "False"),
        ("text", "2017|6"),
        ("text", "2017|閏13"),
        ("jdEnd", float("nan")),
        ("jdEnd", True),
        ("jdEnd", 2457959.5),
        ("uri", "http://datetime.hutime.org/calendar/1002.2/month/2457928.5"),
    ],
)
def test_ambiguous_or_malformed_months_cannot_enter_normalized_data(field, value):
    _, source = sample()
    modified = deepcopy(source)
    modified[field] = value
    with pytest.raises(ValueError):
        parse_month(modified, "2017-06-24")


def test_false_string_is_false_and_printed_leap_fifth_is_not_ordinal_sixth():
    leap, _ = sample()
    assert (leap.year, leap.month, leap.leap) == (2017, 5, True)
    assert leap.start.isoformat() == "2017-06-24"
    regular = next(
        m for m, _ in captured_months() if m.start.isoformat() == "2017-07-23"
    )
    assert (regular.month, regular.leap) == (6, False)


@pytest.mark.parametrize(
    "start,expected",
    [
        ("1947-04-21", (1947, 3, True)),
        ("1969-08-13", (1969, 7, False)),
        ("1989-01-08", (1988, 12, False)),
    ],
)
def test_published_exceptions_and_lunar_year_are_preserved(start, expected):
    month = next(m for m, _ in captured_months() if m.start.isoformat() == start)
    assert (month.year, month.month, month.leap) == expected


def test_a_tokyo_birth_zone_does_not_silently_select_japanese_old_calendar():
    actual = calendar_mansion("2017-06-24", "12:00:00", "Asia/Tokyo")
    assert actual["calendar_system"] == "modern_chinese_lunisolar"
    assert actual["calendar_timezone"] == "UTC+08:00"
    assert (actual["lunar_month"], actual["is_leap_month"]) == (6, False)
    # The candidate source calls this leap fifth month. Birth timezone, host
    # calendar and source-specific mansion algorithm are separate choices.
    japanese, _ = sample()
    assert (japanese.month, japanese.leap) == (5, True)


def test_changed_raw_archive_is_not_normalized_as_a_new_source(tmp_path):
    import shutil

    shutil.copytree(FIXTURE, tmp_path / "candidate")
    archive = tmp_path / "candidate/captures.zip"
    archive.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="archive hash mismatch"):
        audit_candidate(tmp_path / "candidate")
