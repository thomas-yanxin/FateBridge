"""Frozen selected Ming auxiliary passages, not whole-catalogue acceptance."""

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
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def _seed(year: int, month: int, day: int, hour: str, leap: bool) -> MetaphysicsSeed:
    return MetaphysicsSeed(
        input_datetime=datetime(year, 1, 1),
        corrected_datetime=datetime(year, 1, 1),
        timezone="Asia/Shanghai",
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0,
        pillars={"day": ("甲", "子"), "hour": ("甲", hour)},
        calendar_context={
            "lunar_calendar": dict(year=year, month=month, day=day, is_leap_month=leap)
        },
    )


def expected_from_passages(
    source: dict[str, Any],
    month: int,
    day: int,
    hour: str,
    year_branch: str,
    leap: bool,
) -> dict[str, str | None]:
    """Independent source walk: never import production placement helpers."""
    result: dict[str, str | None] = {}
    for method in source["methods"]:
        for row in method["rows"]:
            axis = method["input_axis"]
            if leap and axis in ("month", "day_from_month_star"):
                result[row["star"]] = None
                continue
            sign = 1 if row["direction"] == "forward" else -1
            index = BRANCHES.index(row["anchor"])
            if axis == "day_from_month_star":
                # Source's monthly parent and day walk share the direction.
                # Derive the parent afresh rather than reading engine positions.
                steps = month - 1 + day - 1
            elif axis == "month":
                steps = month - 1
            elif axis == "hour":
                steps = BRANCHES.index(hour)
            else:
                steps = BRANCHES.index(year_branch)
            for _ in range(steps):
                index += sign
                if index < 0:
                    index = 11
                if index > 11:
                    index = 0
            result[row["star"]] = BRANCHES[index]
    result.update(火星=None, 铃星=None)
    return result


def audit_auxiliaries(fixtures: Path = FIXTURES) -> dict[str, Any]:
    d = fixtures / "naj_ming_auxiliaries_v1"
    checksums = json.loads((d / "checksums.json").read_text())
    for item in checksums["files"]:
        if (
            hashlib.sha256((d / item["path"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError(f"Ming auxiliary source checksum mismatch: {item['path']}")
    source = json.loads((d / "collation.json").read_text())
    expected_keys = set(source) - {"images", "catalog_url", "image_conditions_url"}
    compiled = json.loads(
        (
            ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-auxiliaries.json"
        ).read_text()
    )
    mismatches: list[dict[str, Any]] = []
    if set(compiled) != expected_keys:
        mismatches.append(dict(case="production_source_data/coverage"))
    for key in expected_keys:
        if compiled.get(key) != source[key]:
            mismatches.append(dict(case=f"production_source_data/{key}"))
    # Complete factor domains of independent rule inputs, not a brute-force
    # Cartesian expansion of irrelevant axes. Two configurations share sources.
    normal = {(1984, m, day, "子", False) for m in range(1, 13) for day in range(1, 31)}
    normal.update((1984, 1, 1, h, False) for h in BRANCHES)
    normal.update((y, 1, 1, "子", False) for y in range(1984, 1996))
    leap_inputs = {
        (y, m, day, h, True)
        for y in (1984, 1985)
        for m in (4, 12)
        for day in (1, 15, 16, 30)
        for h in ("子", "亥")
    }
    charts = comparable = unresolved = 0
    for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
        for year, month, day, hour, leap in sorted(normal | leap_inputs):
            year_branch = BRANCHES[(year - 1984) % 12]
            wanted = expected_from_passages(source, month, day, hour, year_branch, leap)
            chart = build_ziwei_chart(
                _seed(year, month, day, hour, leap), "男", rule_profile=profile
            )
            evidence = chart["auxiliary_placement_sources"]
            rows = {r["star"]: r for r in evidence["placements"]}
            case = f"{profile}/{year}/{month}/{day}/{hour}/leap={leap}"
            if set(rows) != set(wanted) or len(evidence["placements"]) != 18:
                mismatches.append(dict(case=f"source_coverage/{case}"))
            actual_positions = {
                s["name"]: p["ganzhi"][1]
                for p in chart["palaces"]
                for s in p["stars_detail"]
            }
            actual_paths = {
                s["name"]: f"ziwei_birth.palaces.{i}.stars_detail.{j}"
                for i, p in enumerate(chart["palaces"])
                for j, s in enumerate(p["stars_detail"])
            }
            for star, expected in wanted.items():
                row = rows[star]
                actual = actual_positions[star]
                expected_match = actual == expected if expected is not None else None
                if (
                    row["expected_branch"] != expected
                    or row["actual_branch"] != actual
                    or row["matches_source_rule"] != expected_match
                    or row["calculation_path"] != actual_paths[star]
                ):
                    mismatches.append(dict(case=f"source_join/{case}/{star}"))
                if expected is None:
                    unresolved += 1
                    if not row.get("unresolved_reason"):
                        mismatches.append(dict(case=f"unresolved_reason/{case}/{star}"))
                else:
                    comparable += 1
                    if actual != expected:
                        mismatches.append(
                            dict(
                                case=f"placement/{case}/{star}",
                                expected=expected,
                                actual=actual,
                            )
                        )
            pair = next(
                r["pair_as_written"]
                for r in source["fire_bell"]["pairs"]
                if year_branch in r["branches"]
            )
            if evidence["methods"]["fire_bell"]["pair_as_written"] != pair:
                mismatches.append(dict(case=f"fire_bell_pair/{case}"))
            if set(evidence["unchecked_star_names"]) != set(actual_positions) - set(
                wanted
            ):
                mismatches.append(dict(case=f"unchecked_coverage/{case}"))
            charts += 1
    return dict(
        status="pass_in_frozen_corpus" if not mismatches else "failed",
        source_complete_directional_rule_groups=len(source["methods"]),
        source_stars_with_complete_normal_month_rules=16,
        source_incomplete_fire_bell_pairs=4,
        normal_factor_domain_inputs=len(normal),
        leap_boundary_inputs=len(leap_inputs),
        derived_charts_checked_across_two_profiles=charts,
        derived_comparable_placement_rows=comparable,
        derived_unresolved_rows=unresolved,
        fire_bell_hour_expectations_verified=False,
        monthly_leap_policy_verified=False,
        all_auxiliary_stars_verified=False,
        whole_book_acceptance_passed=False,
        manual_reader_count=source["manual_reader_count"],
        mismatches=mismatches,
        limits=source["limits"],
    )
