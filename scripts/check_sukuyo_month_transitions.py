"""Audit every first lunar day of all three hosts, with fixed source-only gates.

Expected monthly contexts come from frozen provider bytes, never domain output.
The two modern reconstructions remain hypotheses, not accepted source priority.
Run without sampling: uv run --locked --extra dev python scripts/check_sukuyo_month_transitions.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import parse_qs
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))

from scripts.build_sukuyo_historical_calendar import read_fixture

PROTOCOL = ROOT / "tests/fixtures/sukuyo-month-transition-protocol-v1.json"
PROTOCOL_SHA256 = "138728babb6b4e8e66db8bd4c291c9b09c53edad6ed40ac816635fe11c9cf6ef"
PARENT_MANIFEST = "aecaba2e310475074245ef84af0d129dbf0a4a57f5172144d67a914edbf28969"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def hko_days() -> dict[int, tuple[int, int, int, bool]]:
    """Read all published labels, including the separately captured Chinese gap."""
    directory = ROOT / "tests/fixtures/sukuyo_hko_v1"
    manifest = json.loads((directory / "manifest.json").read_bytes())
    with ZipFile(directory / "official_texts.zip") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate HKO capture member")
        sources = {name: archive.read(name) for name in names}
    if {name: sha(raw) for name, raw in sources.items()} != {
        row["file"]: row["sha256"] for row in manifest["sources"]
    }:
        raise ValueError("HKO captured source bytes changed")

    def decode(raw: bytes) -> str:
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return raw.decode("big5")

    printed: list[tuple[date, int | None, int]] = []
    for year in range(1901, 2100):
        for line in decode(sources[f"T{year}e.txt"]).splitlines():
            match = re.match(r"\s*(\d{4})/(\d{1,2})/(\d{1,2})\s+(.+?)\s{2,}", line)
            if not match:
                continue
            civil = date(*map(int, match.group(1, 2, 3)))
            label = match[4].strip()
            month = re.fullmatch(r"(\d+)(?:st|nd|rd|th) Lunar [Mm]onth", label)
            if not month and not label.isdigit():
                raise ValueError("Unrecognized HKO printed date label")
            printed.append(
                (civil, int(month[1]) if month else None, 1 if month else int(label))
            )
    gap = date(2069, 12, 30)
    if not re.search(
        r"2069年12月30日\s+十七\s+星期一", decode(sources["T2069c.txt"])
    ) or any(row[0] == gap for row in printed):
        raise ValueError("HKO English gap or Chinese supplement changed")
    printed.append((gap, None, 17))
    printed.sort()
    if len(printed) != 72684 or any(
        b[0] - a[0] != timedelta(days=1) for a, b in zip(printed, printed[1:])
    ):
        raise ValueError("HKO source must cover every declared day once")
    upcoming_month = next(row[1] for row in printed if row[1] is not None)
    assert upcoming_month is not None
    current_month, lunar_year, leap = upcoming_month - 1 or 12, 1900, False
    result = {}
    for civil, new_month, day in printed:
        if new_month is not None:
            leap = new_month == current_month
            if new_month == 1:
                lunar_year = civil.year
            current_month = new_month
        result[civil.toordinal()] = (lunar_year, current_month, day, leap)
    return result


def source_expectations() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rebuild the entire pre-comparison oracle from verified raw source captures."""
    root = ROOT

    def fixture(name: str) -> tuple[dict[str, bytes], dict[str, Any]]:
        return read_fixture(root / "tests/fixtures" / name)

    # Literal circle and NAOJ first-day row are deliberately not imported from domain code.
    order = list("角亢氐房心尾箕斗女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸")
    anchors = json.loads(
        (root / "tests/fixtures/sukuyo-t1299-reference.json").read_bytes()
    )["naoj_month_starts"]

    def mansion(m: int, d: int) -> str:
        return order[(order.index(anchors[m - 1]) + d - 1) % 27]

    def ordinal(y: int, m: int, d: int) -> int:
        a = y - 1
        leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
        lengths = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        return 365 * a + a // 4 - a // 100 + a // 400 + sum(lengths[: m - 1]) + d

    references: dict[str, dict[int, Any]] = {}
    members = {}
    references["chinese_hko_utc08"] = hko_days()
    members["hko_fixture_manifest_sha256"] = sha(
        (root / "tests/fixtures/sukuyo_hko_v1/manifest.json").read_bytes()
    )
    files, manifest = fixture("sukuyo_hutime_daily_v1")
    daily = {}
    for batch in manifest["daily_batches"]:
        req = parse_qs(files[batch["request"]].decode("ascii"), strict_parsing=True)
        dates = req["ival"][0].splitlines()
        rows = json.loads(files[batch["response"]])
        assert len(dates) == len(rows)
        for d, r in zip(dates, rows):
            if r is None:
                continue
            match = re.fullmatch(r"(\d{4})\|(閏)?(\d{1,2})\|(\d{1,2})", r["text"])
            assert match
            daily[date.fromisoformat(d).toordinal()] = (
                int(match[1]),
                int(match[3]),
                int(match[4]),
                bool(match[2]),
            )
    references["japanese_hutime_1002_1_utc09"] = daily
    members["hutime_daily_archive_sha256"] = manifest["archive_sha256"]
    files, manifest = fixture("sukuyo_historical_calendar_v1")
    starts: dict[int, tuple[int, int, bool]] = {}
    for y in range(1873):
        rows = csv.reader(
            io.StringIO(files[f"naoj-{y:04d}.response.bin"].decode("cp932"))
        )
        next(rows)
        for r in rows:
            yy, mm, dd = map(int, r[0].strip().split("/"))
            o = ordinal(yy, mm, dd)
            lunar_match = re.search(r"(閏)?(\d{2})月01日$", r[1])
            assert lunar_match
            label = (int(r[2]) - 660, int(lunar_match[2]), bool(lunar_match[1]))
            assert o not in starts or starts[o] == label
            starts[o] = label
    ordered = sorted(starts)
    historical = {}
    end = date(1873, 1, 1).toordinal()
    for i, start in enumerate(ordered):
        stop = min(ordered[i + 1] if i + 1 < len(ordered) else end, end)
        y, m, l = starts[start]
        for o in range(max(start, 1), stop):
            historical[o] = (y, m, o - start + 1, l)
    references["japanese_naoj_historical_utc09"] = historical
    members["historical_archive_sha256"] = manifest["archive_sha256"]
    ledger = []
    counts = {}
    for basis, days in references.items():
        first = min(days)
        last = max(days)
        summary: Counter[str] = Counter()
        patterns: Counter[str] = Counter()
        for o, fields in sorted(days.items()):
            y, m, d, leap = fields
            if d != 1:
                continue
            prev = days.get(o - 1)
            prior = days.get(o - prev[2] - 1) if prev and leap else None
            base = mansion(m, 1)
            adjacent = mansion(prev[1], 30) if prev and prev[2] == 29 else base
            repeat = mansion(prior[1], 30) if prior and prior[2] == 29 else base
            firsts = list(
                dict.fromkeys([adjacent, repeat] if leap and prior else [adjacent])
            )
            row: dict[str, Any] = {
                "basis": basis,
                "date": date.fromordinal(o).isoformat(),
                "lunar_fields": list(fields),
                "previous_lunar_fields": list(prev) if prev else None,
                "before_regular_fields": list(prior) if prior else None,
                "branch_first_mansions": firsts,
                "base": base,
                "expectations": {},
            }
            if leap:
                patterns[
                    f'{prior[2] if prior else "unknown"}/{prev[2] if prev else "unknown"}'
                ] += 1
            for half in [None, "first_half", "second_half"]:
                incomplete = (
                    prev is None or (leap and prior is None)
                ) and half != "second_half"
                choices = (
                    list(dict.fromkeys(firsts + [base]))
                    if half is None
                    else firsts if half == "first_half" else [base]
                )
                resolved = not incomplete and len(choices) == 1
                reason = (
                    "hinoo_previous_lunar_context_unavailable"
                    if incomplete
                    else (
                        "computed_under_declared_profile"
                        if resolved
                        else (
                            "hinoo_leap_short_month_precedence_unresolved"
                            if half == "first_half"
                            else "hinoo_short_month_day_part_unresolved"
                        )
                    )
                )
                row["expectations"][str(half)] = {
                    "status": "computed" if resolved else "partial",
                    "natal_su27": choices[0] if resolved else None,
                    "candidate_su27s": [] if resolved else choices,
                    "resolution_reason": reason,
                    "candidate_set_complete_under_declared_reconstructions": not incomplete,
                }
                summary["conditions"] += 1
                summary["resolved" if resolved else "partial"] += 1
                summary["missing_previous_context"] += incomplete
            ledger.append(row)
            summary["month_starts"] += 1
            summary["leap_month_starts"] += leap
            summary["first_half_models_differ"] += leap and len(firsts) > 1
        counts[basis] = {
            "source_days": len(days),
            "range": [
                date.fromordinal(first).isoformat(),
                date.fromordinal(last).isoformat(),
            ],
            **summary,
            "leap_previous_two_lengths": dict(patterns),
        }
    raw = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in ledger
    ).encode()
    protocol_raw = PROTOCOL.read_bytes()
    if sha(protocol_raw) != PROTOCOL_SHA256:
        raise ValueError(
            "Fixed month-transition protocol changed; review a new version explicitly"
        )
    protocol = json.loads(protocol_raw)
    if (
        sha(raw) != protocol["oracle_sha256"]
        or counts != protocol["counts"]
        or members != protocol["source_bindings"]
        or protocol["parent_source_manifest_sha256"] != PARENT_MANIFEST
    ):
        raise ValueError("Full source-only transition domain or oracle changed")
    return ledger, protocol


def compare_calendar(
    row: dict[str, Any], half: str, result: dict[str, Any]
) -> dict[str, Any]:
    """Compare values and derivation inputs; a matching final宿 cannot hide a wrong month."""
    expected = row["expectations"][half]
    selection = result["profile_calculation"]
    actual = {key: result[key] if key in result else selection[key] for key in expected}
    differences = {
        key: {"expected": value, "actual": actual[key]}
        for key, value in expected.items()
        if actual[key] != value
    }
    fields = [
        result[key]
        for key in ("lunar_year", "lunar_month", "lunar_day", "is_leap_month")
    ]
    if fields != row["lunar_fields"]:
        differences["lunar_fields"] = {
            "expected": row["lunar_fields"],
            "actual": fields,
        }
    assignment = selection["short_month_assignment"]
    expected_assignment = row["previous_lunar_fields"] is not None and (
        row["previous_lunar_fields"][2] == 29 or row["lunar_fields"][3]
    )
    if (assignment is not None) != expected_assignment:
        differences["assignment_present"] = {
            "expected": expected_assignment,
            "actual": assignment is not None,
        }
    if assignment is not None:
        prev = assignment["previous_lunar"]
        actual_previous = [
            prev[key]
            for key in ("lunar_year", "lunar_month", "lunar_day", "is_leap_month")
        ]
        if actual_previous != row["previous_lunar_fields"]:
            differences["previous_lunar"] = {
                "expected": row["previous_lunar_fields"],
                "actual": actual_previous,
            }
        firsts = assignment["slots"][0]["candidate_mansions"]
        if firsts != row["branch_first_mansions"]:
            differences["first_half_branches"] = {
                "expected": row["branch_first_mansions"],
                "actual": firsts,
            }
        prior = prev.get("before_regular_month")
        actual_prior = (
            [
                prior[key]
                for key in ("lunar_year", "lunar_month", "lunar_day", "is_leap_month")
            ]
            if prior
            else None
        )
        if actual_prior != row["before_regular_fields"]:
            differences["before_regular_month"] = {
                "expected": row["before_regular_fields"],
                "actual": actual_prior,
            }
    return {"actual": actual, "differences": differences}


def verify_transitions(ledger_output: TextIO | None = None) -> dict[str, Any]:
    from fatebridge.core.sukuyo import calendar_mansion

    rows, protocol = source_expectations()
    counts: Counter[str] = Counter()
    failures = []
    actual_digest = hashlib.sha256()
    for row in rows:
        actual = {}
        for half in row["expectations"]:
            args = {
                "calendar_profile": "hinoo_t1299_host27",
                "calendar_basis": row["basis"],
                "zone": "+08:00" if row["basis"] == "chinese_hko_utc08" else "+09:00",
            }
            if half != "None":
                args["calendar_day_part"] = half
            try:
                actual[half] = compare_calendar(
                    row, half, calendar_mansion(row["date"], **args)
                )
            except Exception as error:
                actual[half] = {
                    "exception": type(error).__name__,
                    "message": str(error),
                }
            counts[row["basis"]] += 1
        item = {"date": row["date"], "basis": row["basis"], "conditions": actual}
        encoded = json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
        actual_digest.update(encoded.encode())
        if ledger_output is not None:
            ledger_output.write(encoded)
        if any(
            value.get("differences") or "exception" in value
            for value in actual.values()
        ):
            failures.append(item)
    complete = counts == {
        key: value["conditions"] for key, value in protocol["counts"].items()
    }
    return {
        "format": "sukuyo_month_transition_check_v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "oracle_sha256": protocol["oracle_sha256"],
        "counts": dict(counts),
        "month_starts": len(rows),
        "all_declared_conditions_evaluated": complete,
        "failures": failures,
        "all_expected_fields_match": complete and not failures,
        "actual_ledger_sha256": actual_digest.hexdigest(),
        "historical_daybreak_or_rule_priority_certified": False,
        "real_samples": 0,
        "scope": protocol["scope"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args()
    if args.ledger:
        with args.ledger.open("x", encoding="utf-8") as output:
            result = verify_transitions(output)
    else:
        result = verify_transitions()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["all_expected_fields_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
