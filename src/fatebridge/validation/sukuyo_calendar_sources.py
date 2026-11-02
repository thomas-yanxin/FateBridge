"""Quarantine candidate Japanese calendar data before any runtime integration.

This checks frozen provider responses, not FateBridge's computed calendar.
Passing structural checks would not establish historical or classical truth.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from zipfile import ZipFile

FIRST = date(1872, 2, 9)
LAST = date(2033, 1, 30)
CALENDAR_ID = "1002.1"
_KEYS = {"text", "jdBegin", "jdEnd", "uri", "isLeap"}


@dataclass(frozen=True)
class SourceMonth:
    start: date
    end_exclusive: date
    year: int
    month: int
    leap: bool
    source_uri: str

    def report(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "start": self.start.isoformat(),
            "end_exclusive": self.end_exclusive.isoformat(),
        }


def parse_month(row: Any, query: str) -> SourceMonth:
    """Parse printed yW|MMM, never an ordinal M or bool('False')."""
    if not isinstance(row, dict) or set(row) != _KEYS:
        raise ValueError("Unexpected month response properties")
    match = re.fullmatch(r"(\d{4})\|(閏)?([1-9]|1[0-2])", str(row["text"]))
    if not match:
        raise ValueError("Month must use yW|MMM printed name, including 閏")
    leap = match[2] is not None
    if row["isLeap"] not in ("True", "False") or (row["isLeap"] == "True") != leap:
        raise ValueError("Printed leap name and exact string flag disagree")
    begin, end = row["jdBegin"], row["jdEnd"]
    if any(
        isinstance(n, bool)
        or not isinstance(n, (float, int))
        or not math.isfinite(n)
        or n % 1 != 0.5
        for n in (begin, end)
    ) or end - begin not in (29, 30):
        raise ValueError("Month periods require half-integer JD and 29/30 days")
    # These are calendar-date period indexes, not physical UTC new-moon times.
    start = date(2000, 1, 1) + timedelta(days=begin - 2451544.5)
    finish = date(2000, 1, 1) + timedelta(days=end - 2451544.5)
    if not start <= date.fromisoformat(query) < finish:
        raise ValueError("Requested date is not inside the returned month")
    if row["uri"] != (
        "http://datetime.hutime.org/calendar/1002.1/month/" + f"{begin:.1f}"
    ):
        raise ValueError("Month URI does not identify the declared calendar period")
    return SourceMonth(start, finish, int(match[1]), int(match[3]), leap, row["uri"])


def _request(raw: bytes, *, calendar: str, period: str, form: str) -> list[str]:
    params = parse_qs(raw.decode("ascii"), strict_parsing=True)
    fixed = {
        "ical": "2.1",  # Explicit proleptic Gregorian input.
        "itype": "date",
        "method": "conv",
        "ep": "b",
        "ocal": calendar,
        "otype": period,
        "oprop": "text;jdBegin;jdEnd;uri;isLeap",
        "oform": form,
        "out": "json",
    }
    if (
        set(params) != {*fixed, "ival"}
        or any(params[key] != [value] for key, value in fixed.items())
        or len(params["ival"]) != 1
    ):
        raise ValueError("Source request changed: review calendar and format semantics")
    return params["ival"][0].splitlines()


def _naoj_rows(raw: bytes) -> list[tuple[date, int, int, int, bool]]:
    records = list(csv.reader(io.StringIO(raw.decode("cp932"))))
    if not records or records[0][:2] != ["西暦", "和暦"]:
        raise ValueError("Unexpected NAOJ CSV header")
    rows = []
    for row in records[1:]:
        if not row:
            continue
        match = re.fullmatch(r"明治05年(閏)?(\d{2})月(\d{2})日", row[1])
        if not match:
            raise ValueError("NAOJ control extends beyond declared pre-reform scope")
        civil = date.fromisoformat(row[0].replace("/", "-"))
        rows.append((civil, 1872, int(match[2]), int(match[3]), bool(match[1])))
    expected = [FIRST + timedelta(days=n) for n in range(327)]
    if [row[0] for row in rows] != expected:
        raise ValueError("NAOJ control must contain all 327 declared dates once")
    return rows


def audit_candidate(fixture: Path) -> dict[str, Any]:
    """Always retain source defects; never trim the advertised range to pass."""
    manifest_raw = (fixture / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    archive_raw = (fixture / "captures.zip").read_bytes()
    if hashlib.sha256(archive_raw).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("Candidate calendar capture archive hash mismatch")
    with ZipFile(io.BytesIO(archive_raw)) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())) or set(
            archive.namelist()
        ) != set(manifest["files_sha256"]):
            raise ValueError("Candidate capture inventory mismatch")
        files = {name: archive.read(name) for name in archive.namelist()}
    for name, raw in files.items():
        if hashlib.sha256(raw).hexdigest() != manifest["files_sha256"][name]:
            raise ValueError(f"Candidate source hash mismatch: {name}")
    queried, missing, errors = [], [], []
    months: dict[date, SourceMonth] = {}
    for batch in manifest["month_batches"]:
        days = _request(
            files[batch["request"]], calendar=CALENDAR_ID, period="month", form="yW|MMM"
        )
        response = json.loads(files[batch["response"]])
        if not isinstance(response, list) or len(response) != len(days):
            raise ValueError("Candidate request/response row counts disagree")
        queried.extend(days)
        for day, row in zip(days, response):
            if row is None:
                missing.append(day)
                continue
            try:
                month = parse_month(row, day)
            except (ValueError, OverflowError) as exc:
                errors.append({"query": day, "error": str(exc)})
                continue
            if month.start in months and months[month.start] != month:
                errors.append({"query": day, "error": "Conflicting repeated month"})
            else:
                months[month.start] = month
    expected_queries = [
        (FIRST + timedelta(days=n)).isoformat()
        for n in range(0, (LAST - FIRST).days + 1, 28)
    ]
    if expected_queries[-1] != LAST.isoformat():
        expected_queries.append(LAST.isoformat())
    if queried != expected_queries:
        raise ValueError(
            "Advertised-range query grid changed; range trimming is forbidden"
        )
    ordered = sorted(months.values(), key=lambda month: month.start)
    intervals, sequence = [], []
    for previous, current in zip(ordered, ordered[1:]):
        if previous.end_exclusive != current.start:
            intervals.append({"previous": previous.report(), "next": current.report()})
        expected_next = (
            (previous.year + 1, 1)
            if previous.month == 12
            else (previous.year, previous.month + 1)
        )
        if (
            current.leap
            and (
                previous.leap
                or (current.year, current.month) != (previous.year, previous.month)
            )
        ) or (not current.leap and (current.year, current.month) != expected_next):
            sequence.append({"previous": previous.report(), "next": current.report()})
    control = manifest["naoj_control"]
    naoj_request = parse_qs(files[control["request"]].decode("ascii"))
    expected_naoj = {
        "type": ["0"],
        "gengo": ["a000"],
        "year": ["1872"],
        "month": ["2"],
        "day": ["9"],
        "jg": ["1"],
        "div": ["1"],
        "divu": ["3"],
        "len": ["327"],
        "lenu": ["3"],
        "gen": ["1"],
        "csv": ["CSV"],
    }
    if naoj_request != expected_naoj:
        raise ValueError("NAOJ control calendar, range or day-unit convention changed")
    controls = _naoj_rows(files[control["response"]])
    disagreements = []
    for civil, year, number, control_day, leap in controls:
        matches = [m for m in ordered if m.start <= civil < m.end_exclusive]
        actual = [
            [m.year, m.month, (civil - m.start).days + 1, m.leap] for m in matches
        ]
        if actual != [[year, number, control_day, leap]]:
            disagreements.append({"date": civil.isoformat(), "candidate": actual})
    probe = manifest["version_probe"]
    probe_days = _request(
        files[probe["request"]], calendar="1002.2", period="month", form="yW|MMM"
    )
    probe_response = json.loads(files[probe["response"]])
    if not isinstance(probe_response, list) or len(probe_response) != len(probe_days):
        raise ValueError("Calendar-ID probe row counts disagree")
    findings = []
    for kind, count in [
        ("malformed_month_rows", len(errors)),
        ("missing_advertised_range_queries", len(missing)),
        ("month_interval_conflicts", len(intervals)),
        ("month_label_sequence_errors", len(sequence)),
        ("independent_control_disagreements", len(disagreements)),
    ]:
        if count:
            findings.append({"kind": kind, "count": count})
    null_probe_dates = [d for d, row in zip(probe_days, probe_response) if row is None]
    if null_probe_dates:
        findings.append(
            {
                "kind": "published_calendar_id_probe_nulls",
                "count": len(null_probe_dates),
            }
        )
    daily_probe = manifest["day_probe"]
    daily_dates = _request(
        files[daily_probe["request"]],
        calendar=CALENDAR_ID,
        period="date",
        form="yW|MMM|d",
    )
    daily_response = json.loads(files[daily_probe["response"]])
    if not isinstance(daily_response, list) or len(daily_response) != len(daily_dates):
        raise ValueError("Day-period probe row counts disagree")
    daily_conflicts = []
    for value, row in zip(daily_dates, daily_response):
        civil = date.fromisoformat(value)
        jd = 2451544.5 + (civil - date(2000, 1, 1)).days
        if (
            not isinstance(row, dict)
            or set(row) != _KEYS
            or (row["jdBegin"], row["jdEnd"], row["uri"])
            != (jd, jd + 1, f"http://datetime.hutime.org/calendar/1002.1/date/{jd:.1f}")
        ):
            raise ValueError("Invalid day-period probe")
        text = row["text"].split("|")
        if len(text) != 3 or row["isLeap"] not in ("True", "False"):
            raise ValueError("Invalid day-period printed date")
        expected = [
            int(text[0]),
            int(text[1].removeprefix("閏")),
            int(text[2]),
            row["isLeap"] == "True",
        ]
        derived = [
            [m.year, m.month, (civil - m.start).days + 1, m.leap]
            for m in ordered
            if m.start <= civil < m.end_exclusive
        ]
        if derived != [expected]:
            daily_conflicts.append(
                {
                    "date": value,
                    "day_response": expected,
                    "month_period_derived_dates": derived,
                }
            )
    if daily_conflicts:
        findings.append(
            {"kind": "day_month_period_disagreements", "count": len(daily_conflicts)}
        )
    return {
        "format": "sukuyo_japanese_candidate_audit_v1",
        "source_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "source_archive_sha256": manifest["archive_sha256"],
        "calendar_id": CALENDAR_ID,
        "documented_range_inclusive": [FIRST.isoformat(), LAST.isoformat()],
        "query_spacing_days": 28,
        "query_count": len(queried),
        "unique_months": len(ordered),
        "observed_month_extent": (
            [ordered[0].start.isoformat(), ordered[-1].end_exclusive.isoformat()]
            if ordered
            else None
        ),
        "month_extent_end_exclusive": True,
        "missing_query_dates": missing,
        "parse_errors": errors,
        "month_interval_conflicts": intervals,
        "month_label_sequence_errors": sequence,
        "independent_control": {
            "provider": "NAOJ",
            "dates": len(controls),
            "range_inclusive": ["1872-02-09", "1872-12-31"],
            "disagreements": disagreements,
            "whole_candidate_range_verified": False,
        },
        "published_id_probe": {
            "calendar_id": "1002.2",
            "query_dates": probe_days,
            "null_query_dates": null_probe_dates,
        },
        "day_month_control": {
            "independent_provider": False,
            "query_dates": daily_dates,
            "disagreements": daily_conflicts,
        },
        "blocking_findings": findings,
        "structural_import_eligible": not findings,
        "runtime_calendar_enabled": False,
        "historical_calendar_acceptance": False,
        "independent_scholarly_acceptance": False,
        "source_provenance": manifest["source_provenance"],
        "scope": "Quarantined provider snapshot. The 28-day grid samples every 29/30-day month under the declared model; it is not a complete independent daily verification. No intervals are corrected, no nulls are interpolated and no production host calendar is changed.",
    }


def require_importable(report: dict[str, Any]) -> None:
    if report["blocking_findings"] or not report["structural_import_eligible"]:
        raise ValueError("Candidate calendar rejected: unresolved source findings")
