"""Independent walks for the explicitly selected Ming limit/fire readings."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.ziwei import (
    _palace_for_nominal_age,
    _xiaoxian_branch,
    build_ziwei_chart,
    build_ziwei_horoscope,
)
from scripts.ziwei_conditional_inputs import synthetic_birth_clock

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/data/ziwei_independent"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
# Normalized names from the separately frozen twelve-palace text (clockwise).
PALACES = [
    "命宫",
    "父母宫",
    "福德宫",
    "田宅宫",
    "官禄宫",
    "仆役宫",
    "迁移宫",
    "疾厄宫",
    "财帛宫",
    "子女宫",
    "夫妻宫",
    "兄弟宫",
]


def _seed(
    year: int, month: int = 1, day: int = 1, hour: str = "子", leap: bool = False
) -> MetaphysicsSeed:
    """Synthetic lunar rule input; not a civil-date conversion oracle."""
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


def walk(branch: str, steps: int, direction: int) -> str:
    index = BRANCHES.index(branch)
    for _ in range(steps):
        index += direction
        if index < 0:
            index = 11
        if index > 11:
            index = 0
    return BRANCHES[index]


def audit_limits(fixtures: Path = FIXTURES) -> dict[str, Any]:
    d = fixtures / "naj_ming_limits_v1"
    m = json.loads((d / "checksums.json").read_text())
    for row in m["files"]:
        if hashlib.sha256((d / row["path"]).read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"Ming limit source checksum mismatch: {row['path']}")
    source = json.loads((d / "collation.json").read_text())
    expected_compiled = {
        k: v for k, v in source.items() if k not in ("images", "image_conditions_url")
    }
    actual_compiled = json.loads(
        (ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-limits.json").read_text()
    )
    mismatches: list[dict[str, Any]] = []
    if actual_compiled != expected_compiled:
        mismatches.append(dict(case="production_source_data"))
    # Validate normalized palace-name inputs against the existing frozen text,
    # not against whatever names the engine happens to return.
    prefix = json.loads(
        (fixtures / "naj_ming_prerequisites_v1/collation.json").read_text()
    )
    reverse = [
        n if n.endswith("宫") else n + "宫"
        for n in prefix["palace_order"]["modern_names"]
    ]
    if [reverse[0], *reversed(reverse[1:])] != PALACES:
        raise ValueError("Source palace sequence changed")
    assignments = boundaries = 0
    starts = {
        p: dict(matches=0, differences=0) for p in ("iztro_2_5_8", "quanshu_v2_excerpt")
    }
    bureau_coverage = set()
    for profile in starts:
        for year in range(1904, 1914):
            for month in range(1, 13):
                for gender in ("男", "女"):
                    chart = build_ziwei_chart(
                        _seed(year, month), gender, rule_profile=profile
                    )
                    is_yang = (year - 1904) % 2 == 0
                    direction = 1 if is_yang == (gender == "男") else -1
                    source_first = source["daxian"]["initial_palace_by_direction"][
                        "forward" if direction == 1 else "reverse"
                    ]
                    selected_first = (
                        source_first if profile == "quanshu_v2_excerpt" else "命宫"
                    )
                    start_index = PALACES.index(selected_first)
                    names = []
                    cursor = start_index
                    for _ in range(12):
                        names.append(PALACES[cursor])
                        cursor = (cursor + direction) % 12
                    ju = chart["wuxing_ju"]["number"]
                    bureau_coverage.add(ju)
                    by_name = {p["name"]: p for p in chart["palaces"]}
                    actual_first = next(
                        p["name"] for p in chart["palaces"] if p["daxian_period"] == 1
                    )
                    starts[profile][
                        "matches" if actual_first == source_first else "differences"
                    ] += 1
                    for period, name in enumerate(names):
                        actual = by_name[name]
                        lo = ju + period * 10
                        hi = lo + 9
                        if (
                            actual["daxian"] != f"{lo}~{hi}"
                            or actual["daxian_period"] != period + 1
                        ):
                            mismatches.append(
                                dict(
                                    case=f"daxian_assignment/{profile}/{year}/{month}/{gender}/{name}"
                                )
                            )
                        if (
                            _palace_for_nominal_age(chart["palaces"], lo)["name"]
                            != name
                            or _palace_for_nominal_age(chart["palaces"], hi)["name"]
                            != name
                        ):
                            mismatches.append(
                                dict(
                                    case=f"daxian_lookup/{profile}/{year}/{month}/{gender}/{name}"
                                )
                            )
                        assignments += 1
                    for age in (ju - 1, ju, ju + 9, ju + 10):
                        h = build_ziwei_horoscope(
                            birth_seed=synthetic_birth_clock(
                                int((chart)["lunar_date"]["year"])
                            ),
                            chart=chart,
                            gender=gender,
                            target_seed=_seed(year + age - 1),
                        )
                        comparison = h["source_comparison"]["daxian"]
                        active = h["scopes"][0]
                        expected_name = None if age < ju else names[(age - ju) // 10]
                        if (
                            active["natal_palace_name"] != expected_name
                            or comparison["actual_branch"] != active["branch"]
                            or comparison["matches_literal_initial_palace"]
                            != (actual_first == source_first)
                        ):
                            mismatches.append(
                                dict(
                                    case=f"daxian_horoscope/{profile}/{year}/{month}/{gender}/{age}"
                                )
                            )
                        if age < ju and (
                            comparison["matches_literal_reading_given_bureau_age"]
                            is not None
                            or active["status"] != "not_started"
                            or active["mutagen"] is not None
                            or active["palace_map"]
                            or active["mutagen_natal_links"]
                        ):
                            mismatches.append(
                                dict(case="childhood_cannot_certify_formal_decade")
                            )
                        if (
                            profile == "quanshu_v2_excerpt"
                            and age >= ju
                            and not comparison[
                                "matches_literal_reading_given_bureau_age"
                            ]
                        ):
                            mismatches.append(
                                dict(case="selected_daxian_reading_trace")
                            )
                        boundaries += 1
    xiao_cases = 0
    for row in source["xiaoxian"]["anchors"]:
        for branch in row["year_branches"]:
            for gender in ("男", "女"):
                for age in range(1, 25):
                    wanted = walk(row["branch"], age - 1, 1 if gender == "男" else -1)
                    if _xiaoxian_branch(branch, age, gender) != wanted:
                        mismatches.append(
                            dict(case=f"xiaoxian/{branch}/{gender}/{age}")
                        )
                    xiao_cases += 1
    dou_cases = 0
    for profile in starts:
        for month in range(1, 13):
            for hour in BRANCHES:
                chart = build_ziwei_chart(
                    _seed(1904, month, hour=hour), "男", rule_profile=profile
                )
                for year in range(1944, 1956):
                    target = BRANCHES[(year - 1984) % 12]
                    wanted = walk(walk(target, month - 1, -1), BRANCHES.index(hour), 1)
                    h = build_ziwei_horoscope(
                        birth_seed=synthetic_birth_clock(
                            int((chart)["lunar_date"]["year"])
                        ),
                        chart=chart,
                        gender="男",
                        target_seed=_seed(year),
                    )
                    row = h["source_comparison"]["doujun"]
                    actual_month = next(
                        s["branch"] for s in h["scopes"] if s["scope"] == "流月"
                    )
                    if (
                        row["expected_branch"] != wanted
                        or row["actual_branch"] != wanted
                        or not row["matches_source_rule"]
                        or actual_month != wanted
                    ):
                        mismatches.append(
                            dict(case=f"doujun/{profile}/{month}/{hour}/{target}")
                        )
                    dou_cases += 1
    fire_cases = 0
    fire_matches = {p: dict(matches=0, differences=0) for p in starts}
    for profile in starts:
        for year in range(1904, 1916):
            branch = BRANCHES[(year - 1984) % 12]
            pair = next(
                r for r in source["fire_bell"]["pairs"] if branch in r["year_branches"]
            )
            for hour in BRANCHES:
                c = build_ziwei_chart(
                    _seed(year, hour=hour), "女", rule_profile=profile
                )
                actual = {
                    s["name"]: p["ganzhi"][1]
                    for p in c["palaces"]
                    for s in p["stars_detail"]
                }
                literal = {"火星": pair["fire"], "铃星": pair["bell"]}
                selected = (
                    literal
                    if profile == "quanshu_v2_excerpt"
                    else {
                        s: walk(b, BRANCHES.index(hour), 1) for s, b in literal.items()
                    }
                )
                if any(actual[s] != b for s, b in selected.items()):
                    mismatches.append(dict(case=f"fire_bell/{profile}/{branch}/{hour}"))
                fire_matches[profile][
                    (
                        "matches"
                        if all(actual[s] == b for s, b in literal.items())
                        else "differences"
                    )
                ] += 1
                fire_cases += 1
    return dict(
        status="pass_in_frozen_corpus" if not mismatches else "failed",
        daxian_assignments_checked=assignments,
        daxian_boundary_horoscopes_checked=boundaries,
        bureau_coverage=sorted(bureau_coverage),
        xiaoxian_age_ordinal_cases=xiao_cases,
        ordinary_birth_month_doujun_cases=dou_cases,
        fire_bell_selected_method_cases=fire_cases,
        daxian_literal_first_palace_comparison=starts,
        fire_bell_year_only_reading_comparison=fire_matches,
        unique_historical_fire_hour_interpretation_verified=False,
        age_calendar_convention_verified=False,
        whole_book_acceptance_passed=False,
        manual_reader_count=source["manual_reader_count"],
        mismatches=mismatches,
        limits=source["limits"],
    )
