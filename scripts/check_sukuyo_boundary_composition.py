"""Compose every original month-start condition with both one-microsecond edges.

The source-only oracle is fixed before importing the calculation implementation.
This adds an interaction gate; it never replaces the original 82,743-condition
gate, resolves a textual priority, or establishes an ancient physical clock.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterator, TextIO

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts import check_sukuyo_month_transitions as monthly

PROTOCOL = ROOT / "tests/data/sukuyo-boundary-composition-protocol-v1.json"
PROTOCOL_SHA256 = "0302bfb789d030f2e1475783d46a33b93f4a2c600078f1cb67672bd3396a81b8"
DAY_US = 86_400_000_000
EPOCH_US = (date(1970, 1, 1).toordinal() - 1) * DAY_US
FIELDS = ("lunar_year", "lunar_month", "lunar_day", "is_leap_month")
ORDER = list("角亢氐房心尾箕斗女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸")


def encode(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()


def _utc_label(ticks: int) -> str:
    ordinal, remainder = divmod(ticks, DAY_US)
    cycles, day = divmod(ordinal, 146097)
    reference = date.fromordinal(day + 1)
    year = reference.year + cycles * 400
    h, remainder = divmod(remainder, 3_600_000_000)
    m, remainder = divmod(remainder, 60_000_000)
    s, us = divmod(remainder, 1_000_000)
    suffix = f".{us:06d}" if us else ""
    return f"{year:04d}-{reference.month:02d}-{reference.day:02d}T{h:02d}:{m:02d}:{s:02d}{suffix}+00:00"


def source_expectations() -> tuple[Iterator[dict[str, Any]], dict[str, Any]]:
    """Use captured provider labels, literal T1299 anchors and Fraction only."""
    rows, original = monthly.source_expectations()
    anchors = json.loads(
        (ROOT / "tests/data/sukuyo-t1299-reference.json").read_bytes()
    )["naoj_month_starts"]
    starts = {(r["basis"], r["date"]): r for r in rows}

    def mansion(month: int, day: int) -> str:
        return ORDER[(ORDER.index(anchors[month - 1]) + day - 1) % 27]

    def generate() -> Iterator[dict[str, Any]]:
        index = 0
        for row in rows:
            basis, center = row["basis"], date.fromisoformat(row["date"])
            ref = 8 if basis == "chinese_hko_utc08" else 9
            bounds = original["counts"][basis]["range"]
            for delta in (1, -1):
                zone = (
                    f"{ref}.0000000002777778"
                    if delta == 1
                    else f"{ref - 1}.9999999997222222"
                )
                offset = round(Fraction(zone) * 3_600_000_000)
                assert offset == ref * 3_600_000_000 + delta
                lo = (center.toordinal() - 1) * DAY_US - offset
                hi = lo + DAY_US
                first = (lo + ref * 3_600_000_000) // DAY_US + 1
                last = (hi - 1 + ref * 3_600_000_000) // DAY_US + 1
                intervals, dates = [], []
                for ordinal in range(first, last + 1):
                    target = date.fromordinal(ordinal).isoformat()
                    start = max(lo, (ordinal - 1) * DAY_US - ref * 3_600_000_000)
                    end = min(hi, ordinal * DAY_US - ref * 3_600_000_000)
                    assert start < end
                    dates.append(target)
                    intervals.append(
                        {
                            "calendar_date": target,
                            "start_utc_inclusive": _utc_label(start),
                            "end_utc_exclusive": _utc_label(end),
                            "start_utc_epoch_microseconds": str(start - EPOCH_US),
                            "end_utc_epoch_microseconds": str(end - EPOCH_US),
                        }
                    )
                for half in ("None", "first_half", "second_half"):
                    branches: list[dict[str, Any]] = []
                    excluded: list[str] = []
                    names: list[str] = []
                    complete = True
                    for target in dates:
                        if not bounds[0] <= target <= bounds[1]:
                            excluded.append(target)
                            complete = False
                            continue
                        monthly_row = starts.get((basis, target))
                        if monthly_row is not None:
                            fields = monthly_row["lunar_fields"]
                            expected = monthly_row["expectations"][half]
                        else:
                            fields = (
                                row["previous_lunar_fields"]
                                if target < row["date"]
                                else [
                                    *row["lunar_fields"][:2],
                                    2,
                                    row["lunar_fields"][3],
                                ]
                            )
                            assert fields is not None
                            expected = {
                                "status": "computed",
                                "natal_su27": mansion(fields[1], fields[2]),
                                "candidate_su27s": [],
                                "resolution_reason": "computed_under_declared_profile",
                                "candidate_set_complete_under_declared_reconstructions": True,
                            }
                        complete = (
                            complete
                            and expected[
                                "candidate_set_complete_under_declared_reconstructions"
                            ]
                        )
                        branch_names = (
                            [expected["natal_su27"]]
                            if expected["natal_su27"]
                            else expected["candidate_su27s"]
                        )
                        names.extend(n for n in branch_names if n not in names)
                        branches.append(
                            {
                                "calendar_date": target,
                                "lunar_fields": fields,
                                "expected": expected,
                                "monthly_context": monthly_row,
                            }
                        )
                    resolved = (
                        complete
                        and len(names) == 1
                        and all(b["expected"]["natal_su27"] for b in branches)
                    )
                    yield {
                        "id": f"composition-{index:06d}",
                        "basis": basis,
                        "date": row["date"],
                        "zone": zone,
                        "half": half,
                        "offset_microseconds": offset,
                        "dates": dates,
                        "intervals": intervals,
                        "branches": branches,
                        "excluded": excluded,
                        "outer": {
                            "status": "partial",
                            "natal_su27": names[0] if resolved else None,
                            "candidate_su27s": [] if resolved else names,
                            "candidate_su27": (
                                names[0] if not resolved and len(names) == 1 else None
                            ),
                            "candidate_set_complete_under_declared_reconstructions": complete,
                            "resolved": resolved,
                        },
                    }
                    index += 1

    return generate(), original


def compare_case(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """A matching merged宿 cannot hide a dropped date, slot, epoch or lunar field."""
    differences: dict[str, Any] = {}

    def check(path: str, expected: Any, actual: Any) -> None:
        if expected != actual or type(expected) is not type(actual):
            differences[path] = {"expected": expected, "actual": actual}

    profile = result["profile_calculation"]
    for key, value in row["outer"].items():
        check(key, value, result[key] if key in result else profile.get(key))
    check("calendar_date", None, result["calendar_date"])
    check("birth_time_known", False, result["birth_time_known"])
    check(
        "out_of_range_calendar_dates",
        row["excluded"],
        result["out_of_range_calendar_dates"],
    )
    check(
        "classical_full_profile_acceptance",
        False,
        profile["classical_full_profile_acceptance"],
    )
    support = result["date_support"]
    for key, expected in {
        "possible_calendar_dates": row["dates"],
        "utc_support_intervals": row["intervals"],
        "fixed_offset_microseconds": row["offset_microseconds"],
        "civil_support_seconds": 86400,
        "interval_resolution_microseconds": 1,
        "complete_under_loaded_timezone_rules": True,
        "birth_time_imputed": False,
    }.items():
        check("date_support." + key, expected, support.get(key))
    actual_branches = result["calendar_candidates"]
    check(
        "branch_dates",
        [b["calendar_date"] for b in row["branches"]],
        [b["calendar_date"] for b in actual_branches],
    )
    for index, (expected, actual) in enumerate(zip(row["branches"], actual_branches)):
        prefix = f"branch[{index}]."
        check(
            prefix + "lunar_fields",
            expected["lunar_fields"],
            [actual[k] for k in FIELDS],
        )
        for key, value in expected["expected"].items():
            check(
                prefix + key,
                value,
                (
                    actual[key]
                    if key in actual
                    else actual["profile_calculation"].get(key)
                ),
            )
        context = expected["monthly_context"]
        assignment = actual["profile_calculation"].get("short_month_assignment")
        if context is None:
            check(prefix + "short_month_assignment", None, assignment)
            continue
        for path, diff in monthly.compare_calendar(context, row["half"], actual)[
            "differences"
        ].items():
            differences[prefix + path] = diff
        if assignment is not None:
            check(
                prefix + "second_half_slot",
                [context["base"]],
                assignment["slots"][1]["candidate_mansions"],
            )
            check(
                prefix + "selected_day_part",
                None if row["half"] == "None" else row["half"],
                assignment["selected_day_part"],
            )
            precedence = assignment.get("leap_short_month_precedence")
            if (
                context["lunar_fields"][3]
                and context["before_regular_fields"] is not None
            ):
                prev, prior = (
                    context["previous_lunar_fields"],
                    context["before_regular_fields"],
                )
                anchors = json.loads(
                    (ROOT / "tests/data/sukuyo-t1299-reference.json").read_bytes()
                )["naoj_month_starts"]

                def first(fields: list[Any]) -> str:
                    return (
                        ORDER[(ORDER.index(anchors[fields[1] - 1]) + 29) % 27]
                        if fields[2] == 29
                        else context["base"]
                    )

                check(
                    prefix + "both_model_first_halves",
                    [first(prev), first(prior)],
                    [
                        precedence["adjacent_month_first_half"],
                        precedence["repeat_true_month_first_half"],
                    ],
                )
                check(
                    prefix + "both_model_second_halves",
                    context["base"],
                    precedence["second_half_both_variants"],
                )
                check(
                    prefix + "source_rule_priority_established",
                    False,
                    precedence["source_rule_priority_established"],
                )
                models = precedence["reconstruction_calculations"]
                check(
                    prefix + "model_ids",
                    [
                        "adjacent_month_short_day_assignment",
                        "repeat_regular_month_first_day_assignment",
                    ],
                    [model["id"] for model in models],
                )
                for model_index, (model, fields) in enumerate(
                    zip(models, (prev, prior))
                ):
                    model_path = prefix + f"model[{model_index}]."
                    check(
                        model_path + "previous_lunar",
                        fields,
                        [model["previous_lunar"][k] for k in FIELDS],
                    )
                    for part in ("first_half_calculation", "second_half_calculation"):
                        month = (
                            fields[1]
                            if part == "first_half_calculation" and fields[2] == 29
                            else context["lunar_fields"][1]
                        )
                        day = (
                            30
                            if part == "first_half_calculation" and fields[2] == 29
                            else 1
                        )
                        anchor = anchors[month - 1]
                        name = ORDER[(ORDER.index(anchor) + day - 1) % 27]
                        calculation = model[part]
                        for key, value in {
                            "lunar_month": month,
                            "lunar_day": day,
                            "fullmoon_day": 15,
                            "fullmoon_mansion": ORDER[(ORDER.index(anchor) + 14) % 27],
                            "signed_day_offset": day - 15,
                            "direct_mansion": name,
                            "shortcut_mansion": name,
                            "methods_agree": True,
                        }.items():
                            check(
                                model_path + part + "." + key, value, calculation[key]
                            )
    for field_index, key in enumerate(FIELDS):
        fields = [b["lunar_fields"][field_index] for b in row["branches"]]
        common = (
            fields[0]
            if not row["excluded"] and all(x == fields[0] for x in fields)
            else None
        )
        check("common_" + key, common, result[key])
    return differences


def verify_all(ledger: TextIO | None = None) -> dict[str, Any]:
    raw = PROTOCOL.read_bytes()
    if monthly.sha(raw) != PROTOCOL_SHA256:
        raise ValueError(
            "Fixed composition protocol changed; no narrowed replacement accepted"
        )
    protocol = json.loads(raw)
    rows, original = source_expectations()
    if (
        protocol["original_protocol_sha256"] != monthly.PROTOCOL_SHA256
        or protocol["original_oracle_sha256"] != original["oracle_sha256"]
    ):
        raise ValueError("Original full month-start gate binding changed")
    # The complete source-only digest is checked before any calculation imports.
    oracle_digest = hashlib.sha256()
    counts: Counter[str] = Counter()
    for row in rows:
        oracle_digest.update(encode(row))
        counts[row["basis"]] += 1
    if (
        oracle_digest.hexdigest() != protocol["oracle_sha256"]
        or dict(counts) != protocol["counts"]
    ):
        raise ValueError("Full composition oracle or domain changed")
    from fatebridge.core.sukuyo import calendar_mansion

    actual_digest, failures = hashlib.sha256(), []
    completed: Counter[str] = Counter()
    for row in source_expectations()[0]:
        try:
            result = calendar_mansion(
                row["date"],
                zone=row["zone"],
                calendar_basis=row["basis"],
                calendar_profile="hinoo_t1299_host27",
                calendar_day_part=None if row["half"] == "None" else row["half"],
            )
            item = {
                "id": row["id"],
                "basis": row["basis"],
                "date": row["date"],
                "zone": row["zone"],
                "half": row["half"],
                "differences": compare_case(row, result),
            }
        except Exception as error:
            item = {
                "id": row["id"],
                "exception": type(error).__name__,
                "message": str(error),
            }
        completed[row["basis"]] += 1
        encoded = encode(item)
        actual_digest.update(encoded)
        if ledger is not None:
            ledger.write(encoded.decode())
        if item.get("differences") or "exception" in item:
            failures.append(item)
    complete = dict(completed) == protocol["counts"]
    return {
        "format": "sukuyo_boundary_composition_check_v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "oracle_sha256": protocol["oracle_sha256"],
        "counts": dict(completed),
        "all165486_conditions_evaluated": complete,
        "all_expected_fields_match": complete and not failures,
        "failures": failures,
        "actual_ledger_sha256": actual_digest.hexdigest(),
        "original82743_gate_replaced": False,
        "ancient_physical_daybreak_or_textual_priority_certified": False,
        "real_samples": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    with args.ledger.open("x", encoding="utf-8") as ledger:
        result = verify_all(ledger)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "failures"}, ensure_ascii=False
        )
    )
    return 0 if result["all_expected_fields_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
