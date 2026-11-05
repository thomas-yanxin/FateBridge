"""Frozen Ming day diagrams and major-star verses, never engine snapshots."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/data/ziwei_independent"
BRANCHES_FROM_YIN = "寅卯辰巳午未申酉戌亥子丑"
# A numeral parser for literal source labels, independent of placement code.
DAY_LABELS = (
    "初一 初二 初三 初四 初五 初六 初七 初八 初九 初十 十一 十二 十三 十四 十五 "
    "十六 十七 十八 十九 二十 廿一 廿二 廿三 廿四 廿五 廿六 廿七 廿八 廿九 三十"
).split()


def _seed(year: int, month: int, day: int) -> MetaphysicsSeed:
    """Synthetic lunar rule inputs, not historical civil-date conversions."""
    return MetaphysicsSeed(
        input_datetime=datetime(year, 1, 1),
        corrected_datetime=datetime(year, 1, 1),
        timezone="Asia/Shanghai",
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0,
        pillars={"day": ("甲", "子"), "hour": ("甲", "子")},
        calendar_context={
            "lunar_calendar": {
                "year": year,
                "month": month,
                "day": day,
                "is_leap_month": False,
            }
        },
    )


def audit_day_tables(fixtures: Path = FIXTURES) -> dict[str, Any]:
    directory = fixtures / "naj_ming_day_tables_v1"
    manifest = json.loads((directory / "checksums.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        if (
            hashlib.sha256((directory / item["path"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError(f"Ming day-table source checksum mismatch: {item['path']}")
    source = json.loads((directory / "collation.json").read_text(encoding="utf-8"))
    labels = {label: index + 1 for index, label in enumerate(DAY_LABELS)}
    labels["廿"] = 20
    literal: dict[tuple[int, int], list[dict[str, str]]] = {}
    for table in source["tables"]:
        for branch, readings in table["literal_days_by_branch"].items():
            for reading in readings:
                key = (table["bureau"], labels[reading])
                literal.setdefault(key, []).append(
                    {"branch": branch, "printed_label": reading}
                )
    prose = {(row["bureau"], row["day"]): row for row in source["prose_derived_cases"]}
    frames = {table["bureau"]: table["frame"] for table in source["tables"]}
    expected: dict[tuple[int, int], dict[str, Any]] = {}
    conflicts, missing, same_branch_duplicates = [], [], []
    for bureau in range(2, 7):
        for day in range(1, 31):
            key = (bureau, day)
            candidates = literal.get(key, [])
            branches = sorted({candidate["branch"] for candidate in candidates})
            row = {
                "branch": None,
                "frame": frames[bureau],
                "printed_labels": [c["printed_label"] for c in candidates],
                "candidates": candidates,
            }
            if len(branches) == 1:
                row.update(branch=branches[0], source_kind="direct_grid_cell")
                if len(candidates) > 1:
                    same_branch_duplicates.append(
                        dict(bureau=bureau, day=day, candidates=candidates)
                    )
            elif len(branches) > 1:
                row["source_kind"] = "unresolved_conflicting_grid_day"
                conflicts.append(dict(bureau=bureau, day=day, candidates=candidates))
            else:
                missing.append(
                    dict(bureau=bureau, day=day, has_prose_derivation=key in prose)
                )
                if key in prose:
                    row.update(
                        branch=prose[key]["branch"],
                        source_kind="prose_derived_with_unresolved_grid_label",
                        source_quote=prose[key]["source_quote"],
                    )
                else:
                    row["source_kind"] = "unresolved_missing_grid_day"
            expected[key] = row
    production = json.loads(
        (ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-days.json").read_text(
            encoding="utf-8"
        )
    )
    rows = production["records"]
    actual_source = {(r["bureau"], r["day"]): r for r in rows}
    mismatches: list[dict[str, Any]] = []
    if set(actual_source) != set(expected) or len(rows) != len(actual_source):
        mismatches.append({"case": "production_source_input_coverage"})
    for key, wanted in expected.items():
        actual = actual_source.get(key, {})
        facts = {name: actual.get(name) for name in wanted}
        if facts != wanted:
            mismatches.append(
                {
                    "case": f"production_source_data/{key[0]}/{key[1]}",
                    "expected": wanted,
                    "actual": facts,
                }
            )
    # Only star placement conditioned on the resolved bureau is checked here.
    # Calendar conversion and the bureau derivation need their own sources.
    seeds: dict[int, tuple[int, int]] = {}
    for year in range(1984, 1989):
        for month in range(1, 13):
            chart = build_ziwei_chart(_seed(year, month, 1), "男")
            seeds.setdefault(chart["wuxing_ju"]["number"], (year, month))
    reflection_reference = json.loads(
        (directory / source["tianfu_reflection_reference"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    reflection = reflection_reference["tianfu_reflection"]["expected_by_ziwei_branch"]
    placements, comparisons, comparable = 0, 0, 0
    for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
        for (bureau, day), expected_row in sorted(expected.items()):
            year, month = seeds[bureau]
            chart = build_ziwei_chart(
                _seed(year, month, day), "男", rule_profile=profile
            )
            trace = next(
                t
                for t in chart["rule_trace"]
                if t["rule_id"] == "ziwei_tianfu_placement"
            )
            evidence = trace["outputs"]["source_comparison"]
            actual_ziwei = next(
                p["ganzhi"][1]
                for p in chart["palaces"]
                if any(s["name"] == "紫微" for s in p["stars_detail"])
            )
            ziwei = expected_row["branch"]
            wanted_trace = [
                ziwei,
                expected_row["source_kind"],
                expected_row["printed_labels"],
                expected_row["candidates"],
                ziwei == actual_ziwei if ziwei is not None else None,
                actual_ziwei,
            ]
            actual_trace = [
                evidence["expected_ziwei_branch"],
                evidence["source_kind"],
                evidence["printed_day_labels"],
                evidence["source_candidates"],
                evidence["matches_source_record"],
                evidence["actual_ziwei_branch"],
            ]
            if actual_trace != wanted_trace:
                mismatches.append(
                    {
                        "case": f"source_trace/{profile}/{bureau}/{day}",
                        "expected": wanted_trace,
                        "actual": actual_trace,
                    }
                )
            comparisons += 1
            if ziwei is None:
                continue  # Counted as unresolved, never as a matching chart.
            expected_stars = {}
            for anchor, slots, direction in (
                (
                    ziwei,
                    source["major_star_groups"]["ziwei_counterclockwise_slots"],
                    -1,
                ),
                (
                    reflection[ziwei],
                    source["major_star_groups"]["tianfu_clockwise_slots"],
                    1,
                ),
            ):
                start = BRANCHES_FROM_YIN.index(anchor)
                for offset, name in enumerate(slots):
                    if name is not None:
                        expected_stars[name] = BRANCHES_FROM_YIN[
                            (start + direction * offset) % 12
                        ]
            if len(expected_stars) != 14:
                raise ValueError(
                    "Printed major-star groups do not resolve 14 distinct stars"
                )
            actual_stars = {
                s["name"]: p["ganzhi"][1]
                for p in chart["palaces"]
                for s in p["stars_detail"]
                if s["name"] in expected_stars
            }
            if actual_stars != expected_stars:
                mismatches.append(
                    {
                        "case": f"major_stars/{profile}/{bureau}/{day}",
                        "expected": expected_stars,
                        "actual": actual_stars,
                    }
                )
            comparable += 1
            placements += len(expected_stars)
    direct = sum(row["source_kind"] == "direct_grid_cell" for row in expected.values())
    return {
        "status": "partial" if not mismatches else "failed",
        "source": source["source_url"],
        "manual_reader_count": source["reader_count"],
        "printed_label_occurrences": sum(
            len(candidates) for candidates in literal.values()
        ),
        "unambiguous_direct_grid_positions": direct,
        "prose_derived_cases": len(prose),
        "unresolved_bureau_day_inputs": sum(
            row["branch"] is None for row in expected.values()
        ),
        "conflicting_grid_days": conflicts,
        "missing_grid_days": missing,
        "same_branch_duplicate_labels": same_branch_duplicates,
        "distinct_bureau_day_inputs": len(expected),
        "profile_charts_built": comparisons,
        "source_comparable_chart_count": comparable,
        "derived_major_star_positions_checked": placements,
        "major_star_rules_from_one_verse_pair": 14,
        "all_150_direct_grid_positions_verified": direct == 150 and not mismatches,
        "classical_day_table_acceptance_passed": direct == 150 and not mismatches,
        "whole_book_acceptance_passed": False,
        "scope": source["scope"],
        "source_differences": source["source_differences"],
        "post_comparison_adjudication_ledger": source[
            "post_comparison_adjudication_ledger"
        ],
        "limits": source["limits"],
        "mismatches": mismatches,
    }
