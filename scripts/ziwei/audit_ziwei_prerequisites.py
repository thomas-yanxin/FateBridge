"""Ming prerequisite prose/anchors; no engine-generated expected chart files."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/data/ziwei_independent"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"


def _seed(year: int, month: int, day: int, hour: str, leap: bool) -> MetaphysicsSeed:
    """Synthetic lunar domain input; not a civil-date conversion claim."""
    return MetaphysicsSeed(
        input_datetime=datetime(year, 1, 1),
        corrected_datetime=datetime(year, 1, 1),
        timezone="Asia/Shanghai",
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0,
        pillars={"day": ("甲", "子"), "hour": ("甲", hour)},
        calendar_context={
            "lunar_calendar": {
                "year": year,
                "month": month,
                "day": day,
                "is_leap_month": leap,
            }
        },
    )


def _source_expected(
    source: dict[str, Any], month: int, hour: str, stem: str
) -> tuple[dict[str, Any], dict[str, str]]:
    # Walk the two source directions. This oracle does not use the runtime
    # compiled first-month lookup, its rotations or any production Nayin table.
    cursor = BRANCHES.index("寅")
    for _ in range(month - 1):
        cursor = (cursor + 1) % 12
    ming, shen = cursor, cursor
    for _ in range(BRANCHES.index(hour)):
        ming = (ming - 1) % 12
        shen = (shen + 1) % 12
    wanted_stems = {}
    yin_stem = next(
        r["yin_stem"] for r in source["wuhu_dun"]["rows"] if stem in r["year_stems"]
    )
    branch, stem_index = BRANCHES.index("寅"), STEMS.index(yin_stem)
    for _ in range(12):
        wanted_stems[BRANCHES[branch]] = STEMS[stem_index]
        branch, stem_index = (branch + 1) % 12, (stem_index + 1) % 10
    ganzhi = wanted_stems[BRANCHES[ming]] + BRANCHES[ming]
    nayin = next(r for r in source["nayin"]["rows"] if ganzhi in r["ganzhi_pair"])
    return {
        "effective_month": month,
        "ming_branch": BRANCHES[ming],
        "shen_branch": BRANCHES[shen],
        "ming_ganzhi": ganzhi,
        "nayin_element": nayin["element"],
        "ju_number": source["bureau_numbers"]["values"][nayin["element"]],
    }, wanted_stems


def audit_prerequisites(fixtures: Path = FIXTURES) -> dict[str, Any]:
    directory = fixtures / "naj_ming_prerequisites_v1"
    checksums = json.loads((directory / "checksums.json").read_text())
    for item in checksums["files"]:
        if (
            hashlib.sha256((directory / item["path"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError(
                f"Ming prerequisite source checksum mismatch: {item['path']}"
            )
    source = json.loads((directory / "collation.json").read_text())
    reference = directory / source["bureau_numbers"]["reference"]
    if (
        hashlib.sha256(reference.read_bytes()).hexdigest()
        != source["bureau_numbers"]["reference_sha256"]
    ):
        raise ValueError("Ming prerequisite bureau-heading reference changed")
    headings = json.loads(reference.read_text())
    if sorted(t["bureau"] for t in headings["tables"]) != [2, 3, 4, 5, 6]:
        raise ValueError("Ming prerequisite bureau-heading coverage incomplete")
    mismatches: list[dict[str, Any]] = []
    compiled = json.loads(
        (
            ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-prerequisites.json"
        ).read_text()
    )
    for key, value in compiled.items():
        if source.get(key) != value:
            mismatches.append({"case": f"production_source_data/{key}"})
    # Assert the intended resource keys as well, so dropping a source section
    # cannot make compilation comparison vacuously pass.
    required = {
        "id",
        "version",
        "title",
        "source_url",
        "printed_volume",
        "manual_reader_count",
        "ming_shen",
        "palace_order",
        "wuhu_dun",
        "nayin",
        "bureau_numbers",
        "limits",
    }
    if set(compiled) != required:
        mismatches.append({"case": "production_source_data/coverage"})
    # The source supplies three explicit first-month hour examples; the
    # remaining nine entries are transparent prose derivations, not quotations.
    for row in source["ming_shen"]["first_month_by_hour"]:
        expected, _ = _source_expected(source, 1, row["hour"], "甲")
        if [row["ming_branch"], row["shen_branch"]] != [
            expected["ming_branch"],
            expected["shen_branch"],
        ]:
            mismatches.append({"case": f"derived_first_month/{row['hour']}"})
    normal_inputs = [
        (1984 + i, month, 1, hour, False)
        for i in range(10)
        for month in range(1, 13)
        for hour in BRANCHES
    ]
    leap_inputs = [
        (year, month, day, hour, True)
        for year in (1984, 1987)
        for month in (3, 12)
        for day in (15, 16)
        for hour in ("子", "亥")
    ]
    policy_differences = []
    charts_checked = 0
    seen_ganzhi = set()
    for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
        for year, month, day, hour, leap in normal_inputs + leap_inputs:
            stem = STEMS[(year - 1984) % 10]
            source_month = month + int(leap)
            selected_month = month + int(
                leap and (profile == "quanshu_v2_excerpt" or day > 15)
            )
            expected, stems = _source_expected(source, source_month, hour, stem)
            selected, _ = _source_expected(source, selected_month, hour, stem)
            chart = build_ziwei_chart(
                _seed(year, month, day, hour, leap), "男", rule_profile=profile
            )
            trace = next(
                t for t in chart["rule_trace"] if t["rule_id"] == "wuhu_dun_nayin_ju"
            )
            evidence = trace["outputs"]["source_comparison"]
            palaces = chart["palaces"]
            ming = next(p for p in palaces if p["name"] == "命宫")
            actual = dict(
                effective_month=chart["rule_trace"][0]["outputs"]["effective_month"],
                ming_branch=ming["ganzhi"][1],
                shen_branch=chart["shen_gong"]["branch"],
                ming_ganzhi=ming["ganzhi"],
                nayin_element=chart["wuxing_ju"]["nayin"][-1],
                ju_number=chart["wuxing_ju"]["number"],
            )
            names = {}
            cursor = BRANCHES.index(actual["ming_branch"])
            for name in source["palace_order"]["modern_names"]:
                names[BRANCHES[cursor]] = name if name.endswith("宫") else name + "宫"
                cursor = (cursor - 1) % 12
            palace_names_ok = len(palaces) == 12 and all(
                p["name"] == names[p["ganzhi"][1]] for p in palaces
            )
            palace_stems_ok = len(palaces) == 12 and all(
                p["ganzhi"][0] == stems[p["ganzhi"][1]] for p in palaces
            )
            checks = {name: actual[name] == value for name, value in expected.items()}
            checks.update(
                palace_names_given_actual_ming=palace_names_ok,
                palace_stems_by_absolute_branch=palace_stems_ok,
            )
            case = f"{profile}/{year}/{month}/{day}/{hour}/leap={leap}"
            if actual != selected or not palace_names_ok or not palace_stems_ok:
                mismatches.append(
                    {
                        "case": f"placement/{case}",
                        "expected": selected,
                        "actual": actual,
                    }
                )
            if (
                evidence["expected"] != expected
                or evidence["actual"] != actual
                or evidence["checks"] != checks
                or evidence["matches_source_chain"] != all(checks.values())
            ):
                mismatches.append({"case": f"source_trace/{case}"})
            if not all(checks.values()):
                policy_differences.append(
                    {"case": case, "expected": expected, "actual": actual}
                )
            seen_ganzhi.add(actual["ming_ganzhi"])
            charts_checked += 1
    return {
        "status": "pass_in_frozen_corpus" if not mismatches else "failed",
        "source_wuhu_anchor_rows": len(source["wuhu_dun"]["rows"]),
        "source_nayin_pair_rows": len(source["nayin"]["rows"]),
        "source_palace_names": len(source["palace_order"]["names_as_written"]),
        "derived_first_month_hour_pairs": 12,
        "normal_lunar_input_combinations": len(normal_inputs),
        "leap_boundary_input_combinations": len(leap_inputs),
        "derived_charts_checked_across_two_profiles": charts_checked,
        "distinct_nayin_ganzhi_reached": len(seen_ganzhi),
        "known_profile_differences": policy_differences,
        "current_profiles_conform_to_this_prerequisite_subset": not policy_differences,
        "unresolved_internal_nayin_name_glyphs": sum(
            not r["name_reading_complete"] for r in source["nayin"]["rows"]
        ),
        "nayin_name_equality_tested": False,
        "manual_reader_count": source["manual_reader_count"],
        "mismatches": mismatches,
        "whole_book_acceptance_passed": False,
        "limits": source["limits"],
    }
