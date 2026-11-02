"""Offline, evidence-bounded Ziwei audit. Unknowns never become full marks.

Calendar expectations come directly from frozen HKO cells; classical
expectations are literal excerpts/hand-derived vectors, not engine snapshots.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.almanac import (
    LUNAR_SUPPORTED_SOLAR_END,
    LUNAR_SUPPORTED_SOLAR_START,
    _lunar_date_from_solar,
)
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.ziwei import (
    build_ziwei_chart,
    build_ziwei_horoscope,
    build_ziwei_rules,
)
from fatebridge.core.ziwei_tables import lookup_star_brightness

if TYPE_CHECKING or __package__:
    from .audit_ziwei_activation import audit_activation
    from .audit_ziwei_age import audit_age_calendar
    from .audit_ziwei_auxiliaries import audit_auxiliaries
    from .audit_ziwei_calendar_sources import (
        audit_calendar_sources,
        frozen_calendar_rows,
    )
    from .audit_ziwei_childhood import audit_childhood
    from .audit_ziwei_civil_fold import audit_civil_fold
    from .audit_ziwei_clock import audit_clock_basis
    from .audit_ziwei_conditions import audit_conditions
    from .audit_ziwei_cycles import audit_cycles
    from .audit_ziwei_days import audit_day_tables
    from .audit_ziwei_independent_readings import audit_independent_readings
    from .audit_ziwei_limits import audit_limits
    from .audit_ziwei_ming_properties import audit_ming_properties
    from .audit_ziwei_natal import audit_natal
    from .audit_ziwei_natal_prerequisites import audit_natal_prerequisites
    from .audit_ziwei_phase import audit_phase_days
    from .audit_ziwei_prerequisites import audit_prerequisites
    from .audit_ziwei_review_disclosure import audit_review_disclosure
    from .audit_ziwei_sihua_selection import audit_sihua_selection
    from .audit_ziwei_solar_clock import audit_solar_clock
    from .audit_ziwei_subperiods import audit_subperiods
    from .audit_ziwei_targeted_rereading import audit_targeted_rereading
    from .audit_ziwei_time_input import audit_time_input
else:
    from audit_ziwei_activation import audit_activation
    from audit_ziwei_age import audit_age_calendar
    from audit_ziwei_auxiliaries import audit_auxiliaries
    from audit_ziwei_calendar_sources import (
        audit_calendar_sources,
        frozen_calendar_rows,
    )
    from audit_ziwei_childhood import audit_childhood
    from audit_ziwei_civil_fold import audit_civil_fold
    from audit_ziwei_clock import audit_clock_basis
    from audit_ziwei_conditions import audit_conditions
    from audit_ziwei_cycles import audit_cycles
    from audit_ziwei_days import audit_day_tables
    from audit_ziwei_independent_readings import audit_independent_readings
    from audit_ziwei_limits import audit_limits
    from audit_ziwei_ming_properties import audit_ming_properties
    from audit_ziwei_natal import audit_natal
    from audit_ziwei_natal_prerequisites import audit_natal_prerequisites
    from audit_ziwei_phase import audit_phase_days
    from audit_ziwei_prerequisites import audit_prerequisites
    from audit_ziwei_review_disclosure import audit_review_disclosure
    from audit_ziwei_sihua_selection import audit_sihua_selection
    from audit_ziwei_solar_clock import audit_solar_clock
    from audit_ziwei_subperiods import audit_subperiods
    from audit_ziwei_targeted_rereading import audit_targeted_rereading
    from audit_ziwei_time_input import audit_time_input

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/ziwei_independent"
MONTHS = {
    name: i
    for i, name in enumerate(
        (
            "正月",
            "二月",
            "三月",
            "四月",
            "五月",
            "六月",
            "七月",
            "八月",
            "九月",
            "十月",
            "十一月",
            "十二月",
        ),
        1,
    )
}
DAYS = {
    name: i
    for i, name in enumerate(
        (
            "初一",
            "初二",
            "初三",
            "初四",
            "初五",
            "初六",
            "初七",
            "初八",
            "初九",
            "初十",
            "十一",
            "十二",
            "十三",
            "十四",
            "十五",
            "十六",
            "十七",
            "十八",
            "十九",
            "二十",
            "廿一",
            "廿二",
            "廿三",
            "廿四",
            "廿五",
            "廿六",
            "廿七",
            "廿八",
            "廿九",
            "三十",
        ),
        1,
    )
}
HKO_ROW = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\S+)")


def hko_rows(
    text: str,
    year: int,
    initial_month: int | None = None,
    initial_leap: bool | None = None,
) -> list[dict[str, Any]]:
    """Read HKO cells independently; retain missing prefix month information.

    Annual text tables omit the month name on Jan 1 when it is not 初一.
    Never infer that missing month/leap status using the engine under test.
    Every day cell is checked; the full-date denominator is separate.
    """
    result = []
    month, leap = initial_month, initial_leap
    lunar_year = year - 1
    for line in text.splitlines():
        match = HKO_ROW.match(line)
        if not match:
            continue
        y, m, d = (int(x) for x in match.groups()[:3])
        solar = date(y, m, d)
        token = match.group(4)
        month_token = token.removeprefix("閏").removeprefix("闰")
        if month_token in MONTHS:
            month = MONTHS[month_token]
            leap = token.startswith(("閏", "闰"))
            day = 1
            if month == 1 and not leap:
                lunar_year = year
        else:
            day = DAYS[token]  # unknown spellings are errors, not skipped rows
        result.append(
            dict(solar=solar, year=lunar_year, month=month, day=day, is_leap=leap)
        )
    expected_count = (date(year + 1, 1, 1) - date(year, 1, 1)).days
    expected_dates = [
        date(year, 1, 1) + timedelta(days=i) for i in range(expected_count)
    ]
    if [r["solar"] for r in result] != expected_dates:
        raise ValueError(f"HKO {year} table has missing, duplicate or unordered rows")
    return result


def audit_calendar(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest = json.loads(
        (fixtures / "calendar_manifest.json").read_text(encoding="utf-8")
    )
    mismatches: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    if [s["year"] for s in manifest["sources"]] != list(range(1901, 2101)):
        raise ValueError(
            "The complete fixed HKO 1901-2100 source cohort must be retained"
        )
    supported_start, supported_end = (
        LUNAR_SUPPORTED_SOLAR_START,
        LUNAR_SUPPORTED_SOLAR_END,
    )
    _, printed_1900 = frozen_calendar_rows(fixtures)
    last = printed_1900[-1]
    last_year, last_month, last_leap = 1900, last["month"], last["is_leap_month"]
    recovered_prefix_cells = 0
    for source in manifest["sources"]:
        data = (fixtures / source["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError(f"Source checksum mismatch: {source['path']}")
        adjacent = last_year is not None and source["year"] == last_year + 1
        if source["year"] == 1901:
            recovered_prefix_cells = sum(
                r["month"] is None
                for r in hko_rows(data.decode("utf-8-sig"), source["year"])
            )
        rows = hko_rows(
            data.decode("utf-8-sig"),
            source["year"],
            last_month if adjacent else None,
            last_leap if adjacent else None,
        )
        if source["year"] == 1901 and (
            rows[0]["solar"] != date.fromisoformat(last["solar"]) + timedelta(days=1)
            or (rows[0]["year"], rows[0]["month"], rows[0]["day"], rows[0]["is_leap"])
            != (last["year"], last["month"], last["day"] + 1, last["is_leap_month"])
        ):
            mismatches.append(dict(case="tam_1900_hko_1901_printed_date_seam"))
        last_year, last_month, last_leap = (
            source["year"],
            rows[-1]["month"],
            rows[-1]["is_leap"],
        )
        # The reference cohort is fixed. A smaller advertised runtime range is
        # a failure, never permission to drop difficult printed dates.
        supported_rows = rows
        for row in supported_rows:
            if not supported_start <= row["solar"] <= supported_end:
                mismatches.append(
                    dict(
                        case="runtime_support_reduced_fixed_reference_cohort",
                        solar=row["solar"].isoformat(),
                    )
                )
            got = _lunar_date_from_solar(row["solar"])
            expected = {"year": row["year"], "day": row["day"]}
            if row["month"] is not None:
                expected.update(month=row["month"], isLeapMonth=row["is_leap"])
            actual = {k: getattr(got, k) for k in expected}
            if expected != actual:
                mismatches.append(
                    dict(
                        solar=row["solar"].isoformat(), expected=expected, actual=actual
                    )
                )
        coverage.append(
            {
                "year": source["year"],
                "source_rows": len(rows),
                "day_and_year_cells": len(supported_rows),
                "full_date_cells": sum(r["month"] is not None for r in supported_rows),
                "prefix_month_not_published": sum(
                    r["month"] is None for r in supported_rows
                ),
                "outside_engine_support": sum(
                    not supported_start <= r["solar"] <= supported_end for r in rows
                ),
            }
        )
    return {
        "status": "pass_in_frozen_corpus" if not mismatches else "failed",
        "coverage": coverage,
        "day_and_year_cells": sum(r["day_and_year_cells"] for r in coverage),
        "full_date_cells": sum(r["full_date_cells"] for r in coverage),
        "outside_engine_support": sum(r["outside_engine_support"] for r in coverage),
        "frozen_manifest_declared_engine_range": {
            "start": manifest["engine_supported_solar_start"],
            "end": manifest["engine_supported_solar_end"],
        },
        "actual_engine_supported_range": {
            "start": supported_start.isoformat(),
            "end": supported_end.isoformat(),
        },
        "source_prefix_cells_recovered_from_preceding_tam_table": recovered_prefix_cells,
        "recovered_month_labels_are_explicitly_printed_in_each_hko_cell": False,
        "preceding_printed_anchor": last,
        "mismatches": mismatches,
        "limits": [
            "HKO begins in 1901; 1900 has a separately checked complete TAM printed-date witness, plus a NASA lunar-day-only comparison. None certifies all timezones or apparent-solar clock policies",
            "The 1901 January prefix inherits month/leap from the immediately preceding printed TAM 1900 table; recovered labels are not newly explicit HKO month cells",
            "HKO warns that some distant future new moons near midnight may shift civil dates",
        ],
    }


def synthetic_seed(
    year: int, month: int = 1, day: int = 1, hour: str = "子", leap: bool = False
) -> MetaphysicsSeed:
    """Synthetic lunar rule inputs, not claimed historical solar conversions."""
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


def audit_classical(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest = json.loads(
        (fixtures / "classical_manifest.json").read_text(encoding="utf-8")
    )
    for source in manifest["files"]:
        if (
            hashlib.sha256((fixtures / source["path"]).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError(f"Classical source checksum mismatch: {source['path']}")
    data = json.loads((fixtures / "classical_excerpt.json").read_text(encoding="utf-8"))
    checks = []

    def check(label: str, actual: Any, expected: Any) -> None:
        checks.append(
            {
                "case": label,
                "passed": actual == expected,
                "expected": expected,
                "actual": actual,
            }
        )

    profile = "quanshu_v2_excerpt"
    for stem, expected in data["sihua_by_stem"].items():
        rules = build_ziwei_rules(stem, rule_profile=profile)["focused_rules"]["sihua"]
        check(f"sihua/{stem}", [rules[k] for k in data["sihua_order"]], expected)
    for hour, expected in data["first_lunar_month_by_hour"].items():
        chart = build_ziwei_chart(
            synthetic_seed(1984, hour=hour), "男", rule_profile=profile
        )
        check(
            f"ming_shen/{hour}",
            [chart["ming_gong"]["branch"], chart["shen_gong"]["branch"]],
            expected,
        )
    for i, (stem, expected) in enumerate(data["yin_palace_by_stem"].items()):
        chart = build_ziwei_chart(synthetic_seed(1984 + i), "男", rule_profile=profile)
        check(f"yin_stem/{stem}", chart["ming_gong"]["ganzhi"], expected)
    for case in data["ziwei_positions"]:
        chart = build_ziwei_chart(
            synthetic_seed(case["lunar_year"], day=case["day"]),
            "男",
            rule_profile=profile,
        )
        palace = next(
            p
            for p in chart["palaces"]
            if any(s["name"] == "紫微" for s in p["stars_detail"])
        )
        check(
            f"ziwei/{case['ju']}/{case['day']}",
            [chart["wuxing_ju"]["number"], palace["ganzhi"][1]],
            [case["ju"], case["branch"]],
        )
    for day in (1, 15, 16, 30):
        chart = build_ziwei_chart(
            synthetic_seed(1984, day=day, leap=True), "男", rule_profile=profile
        )
        check(
            f"leap_month/{day}",
            [chart["ming_gong"]["branch"], chart["shen_gong"]["branch"]],
            ["卯", "卯"],
        )
    return {
        "status": "partial" if all(c["passed"] for c in checks) else "failed",
        "source": data["source"],
        "edition_status": data["edition_status"],
        "checked_vectors": len(checks),
        "failed_vectors": [c for c in checks if not c["passed"]],
        "unresolved_source_items": data["unresolved_source_items"],
        "whole_book_acceptance_passed": False,
    }


def audit_additional_classical(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest = json.loads(
        (fixtures / "additional_manifest.json").read_text(encoding="utf-8")
    )
    for source in manifest["files"]:
        if (
            hashlib.sha256((fixtures / source["path"]).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError("Additional classical source checksum mismatch")
    data = json.loads(
        (fixtures / "quanshu_additional_excerpts.json").read_text(encoding="utf-8")
    )
    names = dict(
        zip(
            "紫机日武同廉府月贪巨相梁杀破昌曲火铃羊陀禄",
            (
                "紫微",
                "天机",
                "太阳",
                "武曲",
                "天同",
                "廉贞",
                "天府",
                "太阴",
                "贪狼",
                "巨门",
                "天相",
                "天梁",
                "七杀",
                "破军",
                "文昌",
                "文曲",
                "火星",
                "铃星",
                "擎羊",
                "陀罗",
                "禄存",
            ),
        )
    )
    differences, checked = [], 0
    for branch, columns in data["brightness_rows"].items():
        for expected, glyphs in zip(data["brightness_heading"], columns):
            for glyph in glyphs:
                star = names[glyph]
                actual = lookup_star_brightness(
                    star, branch, rule_profile="quanshu_v2_excerpt"
                )
                checked += 1
                if actual != expected:
                    differences.append(
                        {
                            "star": star,
                            "branch": branch,
                            "expected": expected,
                            "actual": actual,
                        }
                    )
    return {
        "status": "partial" if not differences else "failed",
        "brightness_cells_checked": checked,
        "differences": differences,
        "unresolved": data["unresolved"],
        "whole_book_acceptance_passed": False,
    }


def audit_depth_classical(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest = json.loads(
        (fixtures / "depth_manifest.json").read_text(encoding="utf-8")
    )
    for entry in manifest["files"]:
        if (
            hashlib.sha256((fixtures / entry["path"]).read_bytes()).hexdigest()
            != entry["sha256"]
        ):
            raise ValueError("Depth classical source checksum mismatch")
    source = json.loads(
        (fixtures / "quanshu_v2_revision_1963110.json").read_text(encoding="utf-8")
    )
    page = next(iter(source["query"]["pages"].values()))
    revision = page["revisions"][0]
    if page["title"] != "紫微斗數全書/卷二" or revision["revid"] != 1963110:
        raise ValueError("Unexpected classical title/revision")
    original = revision["slots"]["main"]["*"]
    data = json.loads(
        (fixtures / "quanshu_depth_rules.json").read_text(encoding="utf-8")
    )
    failures = []

    def check(label: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            failures.append({"case": label, "expected": expected, "actual": actual})

    normalized = re.sub(r"\s+", "", original)
    for label, quote in data["excerpts"].items():
        check(f"source_quote/{label}", re.sub(r"\s+", "", quote) in normalized, True)
    stars = json.loads(
        (ROOT / "src/fatebridge/data/classical/ziwei-quanshu-v2-stars.json").read_text(
            encoding="utf-8"
        )
    )
    check(
        "symbolic_star_set",
        sorted(s["star"] for s in stars["entries"]),
        sorted(data["star_elements"]),
    )
    for item in stars["entries"]:
        check(f"source_quote/{item['star']}", item["quote"] in original, True)
        check(
            f"elements/{item['star']}",
            item["elements"],
            data["star_elements"][item["star"]],
        )
        # Parse only the literal opening element glyphs, independently from
        # the production property's data extraction and chart join.
        element_match = re.match(r"^.+?属([木火土金水]+)", item["quote"])
        check(
            f"literal_elements/{item['star']}",
            list(element_match[1]) if element_match else None,
            item["elements"],
        )

    profile = "quanshu_v2_excerpt"
    xun_order = ("甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅")
    joins = 0
    for index in range(60):
        chart = build_ziwei_chart(
            synthetic_seed(1984 + index), "男", rule_profile=profile
        )
        expected = data["void_pairs_by_xun"][xun_order[index // 10]]
        displayed = [
            p["ganzhi"][1]
            for p in chart["palaces"]
            if any(s["name"] == "旬空" for s in p["stars_detail"])
        ]
        check(f"void_pair/{1984+index}", sorted(displayed), sorted(expected))
        check(
            f"void_metadata/{1984+index}",
            chart["void_systems"]["xun"]["displayed_star_branches"],
            expected,
        )
        for item in chart["symbolic_properties"]["records"]:
            position = item["calculation_path"].split(".")
            palace = chart["palaces"][int(position[2])]
            actual = palace["stars_detail"][int(position[4])]
            check(
                f"symbolic_join/{index}/{item['star']}",
                [
                    item["star"],
                    item["natal_brightness"],
                    item["natal_mutagen"],
                    item["natal_palace_name"],
                    item["natal_branch"],
                ],
                [
                    actual["name"],
                    actual["brightness"],
                    actual["mutagen"],
                    palace["name"],
                    palace["ganzhi"][1],
                ],
            )
            joins += 1
    natal = build_ziwei_chart(synthetic_seed(1984), "男", rule_profile=profile)
    for offset, branch in enumerate("子丑寅卯辰巳午未申酉戌亥"):
        target = synthetic_seed(1996 + offset, month=6, day=15)
        horoscope = build_ziwei_horoscope(
            nominal_age_basis="legacy_mixed_clock",
            chart=natal,
            gender="男",
            target_seed=target,
        )
        annual = next(s for s in horoscope["scopes"] if s["scope"] == "流年")
        actual = {
            s["star"]: s["branch"]
            for s in annual["flowing_stars"]
            if s["rule_id"] != "annual_lucun_yang_tuo"
        }
        check(f"annual/{branch}", actual, data["annual_by_year_branch"][branch])
        group = next(group for group in data["annual_sha_by_triad"] if branch in group)
        check(
            f"annual_sha/{branch}",
            annual["annual_three_sha"]["branches"],
            data["annual_sha_by_triad"][group],
        )
        check(
            f"annual_sha_unpaired/{branch}",
            annual["annual_three_sha"]["individual_name_positions"],
            None,
        )
    return {
        "status": "partial" if not failures else "failed",
        "source_revision": 1963110,
        "source_title_verified": True,
        "void_pairs_checked": 60,
        "annual_placements_checked": 72,
        "annual_sha_sets_checked": 12,
        "symbolic_source_records_checked": len(stars["entries"]),
        "symbolic_calculation_joins_checked": joins,
        "mismatches": failures,
        "whole_book_acceptance_passed": False,
        "initial_source_limits_as_frozen": manifest["limits"],
        "unresolved": [
            "Exact printed base of the pinned online transcription is not identified; selected Ming crosschecks are reported separately",
            "Full volume is frozen for review, not fully implemented or certified",
            "Ambiguous named placement and contradictory text remain unresolved",
        ],
    }


def audit_ming_scan(fixtures: Path = FIXTURES) -> dict[str, Any]:
    root = fixtures / "naj_ming"
    checksums = json.loads((root / "checksums.json").read_text(encoding="utf-8"))
    for entry in checksums["files"]:
        if (
            hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest()
            != entry["sha256"]
        ):
            raise ValueError("Ming scan source checksum mismatch")
    source = json.loads((root / "collation.json").read_text(encoding="utf-8"))
    failures = []
    checks = 0
    for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
        for stem, expected in source["nobles"]["expected_by_stem"].items():
            index = "甲乙丙丁戊己庚辛壬癸".index(stem)
            chart = build_ziwei_chart(
                synthetic_seed(1984 + index), "男", rule_profile=profile
            )
            actual = [
                next(
                    p["ganzhi"][1]
                    for p in chart["palaces"]
                    if any(s["name"] == name for s in p["stars_detail"])
                )
                for name in ("天魁", "天钺")
            ]
            if actual != expected:
                failures.append(
                    dict(
                        case=f"nobles/{profile}/{stem}",
                        expected=expected,
                        actual=actual,
                    )
                )
            checks += 2
    xun_order = ("甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅")
    for index in range(60):
        chart = build_ziwei_chart(
            synthetic_seed(1984 + index), "男", rule_profile="quanshu_v2_excerpt"
        )
        expected = source["void_pairs"]["expected_by_xun"][xun_order[index // 10]]
        actual = chart["void_systems"]["xun"]["displayed_star_branches"]
        if actual != expected:
            failures.append(
                dict(case=f"scan_void/{index}", expected=expected, actual=actual)
            )
    production = json.loads(
        (ROOT / "src/fatebridge/data/classical/ziwei-quanshu-v2-stars.json").read_text(
            encoding="utf-8"
        )
    )
    actual_elements = {row["star"]: row["elements"] for row in production["entries"]}
    if actual_elements != source["elements"]["expected"]:
        failures.append(
            dict(
                case="scan_elements",
                expected=source["elements"]["expected"],
                actual=actual_elements,
            )
        )
    return {
        "status": "partial" if not failures else "failed",
        "catalog_uri": source["catalog_uri"],
        "reference_code": source["reference_code"],
        "scan_frames_frozen": len(source["images"]),
        "manual_scan_reader_count": 1,
        "noble_placement_checks": checks,
        "independent_noble_source_cells": 20,
        "void_pairs_checked": 60,
        "independent_void_source_pairs": 6,
        "element_records_checked": 16,
        "pinned_transcription_differences": source["nobles"][
            "pinned_transcription_differences"
        ],
        "body_master_unresolved": source["body_master"],
        "printed_volume": source["printed_volume_for_placement_sections"],
        "transcription_volume": source["transcription_volume_for_same_sections"],
        "mismatches": failures,
        "whole_book_acceptance_passed": False,
        "unresolved": source["unresolved"],
    }


def audit_ming_anxing(fixtures: Path = FIXTURES) -> dict[str, Any]:
    """Literal print readings; edition differences never count as conformity."""
    root = fixtures / "naj_ming_anxing_v1"
    manifest = json.loads((root / "checksums.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        if (
            hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest()
            != entry["sha256"]
        ):
            raise ValueError("Ming Anxing source checksum mismatch")
    source = json.loads((root / "collation.json").read_text(encoding="utf-8"))
    # Independently expand the frozen printed abbreviations, not engine output.
    names = dict(
        zip(
            "廉破武陽日機梁紫月同昌巨貪弼曲相府陰",
            [
                "廉贞",
                "破军",
                "武曲",
                "太阳",
                "太阳",
                "天机",
                "天梁",
                "紫微",
                "太阴",
                "天同",
                "文昌",
                "巨门",
                "贪狼",
                "右弼",
                "文曲",
                "天相",
                "天府",
                "太阴",
            ],
        )
    )
    expected = {
        row["stem"]: dict(
            zip(source["sihua"]["order"], [names[a] for a in row["star_abbreviations"]])
        )
        for row in source["sihua"]["rows"]
    }
    production = json.loads(
        (ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-sihua.json").read_text(
            encoding="utf-8"
        )
    )
    actual = {row["stem"]: row["assignments"] for row in production["rows"]}
    mismatches = []
    if actual != expected:
        mismatches.append(
            dict(case="literal_sihua_table", expected=expected, actual=actual)
        )
    readings = [
        (row["stem"], row["frame"], row["reading"]) for row in production["rows"]
    ]
    source_readings = [
        (row["stem"], row["frame"], row["reading"]) for row in source["sihua"]["rows"]
    ]
    if readings != source_readings:
        mismatches.append(
            dict(
                case="literal_sihua_readings", expected=source_readings, actual=readings
            )
        )
    edition_differences = {}
    joined_positions = 0
    for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
        selected = build_ziwei_rules(rule_profile=profile)["rule_catalogue"][
            "sihua_by_year_stem"
        ]
        differences = []
        for i, stem in enumerate("甲乙丙丁戊己庚辛壬癸"):
            chart = build_ziwei_chart(
                synthetic_seed(1984 + i), "男", rule_profile=profile
            )
            comparison = chart["sihua_source_comparison"]
            stem_differences = []
            for change, source_star in expected[stem].items():
                if selected[stem][change] != source_star:
                    stem_differences.append(
                        dict(
                            transformation=change,
                            selected_star=selected[stem][change],
                            compared_star=source_star,
                        )
                    )
                    differences.append(
                        dict(
                            year_stem=stem,
                            transformation=change,
                            selected_star=selected[stem][change],
                            compared_star=source_star,
                        )
                    )
            reported_stem_differences = [
                {
                    key: difference[key]
                    for key in ("transformation", "selected_star", "compared_star")
                }
                for difference in comparison["differences"]
            ]
            if reported_stem_differences != stem_differences:
                mismatches.append(
                    dict(
                        case=f"natal_edition_report/{profile}/{stem}",
                        actual=reported_stem_differences,
                        expected=stem_differences,
                    )
                )
            for difference in comparison["differences"]:
                for kind in ("selected", "compared"):
                    pos = difference[f"{kind}_position"]
                    parts = pos["calculation_path"].split(".")
                    palace = chart["palaces"][int(parts[2])]
                    star = palace["stars_detail"][int(parts[4])]
                    got = [
                        star["name"],
                        star["mutagen"],
                        palace["name"],
                        palace["ganzhi"][1],
                    ]
                    wanted = [
                        difference[f"{kind}_star"],
                        pos["natal_mutagen"],
                        pos["natal_palace_name"],
                        pos["natal_branch"],
                    ]
                    if got != wanted:
                        mismatches.append(
                            dict(
                                case=f"source_position/{profile}/{stem}/{kind}",
                                actual=got,
                                expected=wanted,
                            )
                        )
                    joined_positions += 1
            if comparison["compared_assignments_applied"]:
                mismatches.append(dict(case=f"variant_applied/{profile}/{stem}"))
        reported = build_ziwei_rules(rule_profile=profile)["rule_catalogue"][
            "sihua_source_comparison"
        ]["differences"]
        if reported != differences:
            mismatches.append(
                dict(
                    case=f"edition_report/{profile}",
                    actual=reported,
                    expected=differences,
                )
            )
        edition_differences[profile] = differences

    # Find synthetic inputs with each bureau; only star placement conditioned on
    # the resolved bureau is audited here, not the bureau calculation itself.
    seeds: dict[int, MetaphysicsSeed] = {}
    for year in range(1984, 1989):
        for month in range(1, 13):
            seed = synthetic_seed(year, month=month)
            chart = build_ziwei_chart(seed, "男")
            seeds.setdefault(chart["wuxing_ju"]["number"], seed)

    def star_branch(chart: dict[str, Any], name: str) -> str:
        return str(
            next(
                p["ganzhi"][1]
                for p in chart["palaces"]
                if any(s["name"] == name for s in p["stars_detail"])
            )
        )

    for anchor in source["ziwei_anchor_cells"]:
        base = seeds[anchor["bureau"]]
        lunar = base.calendar_context["lunar_calendar"]
        seed = synthetic_seed(lunar["year"], month=lunar["month"], day=anchor["day"])
        anchor_branch = star_branch(build_ziwei_chart(seed, "男"), "紫微")
        if anchor_branch != anchor["branch"]:
            mismatches.append(
                dict(
                    case=f"ziwei_anchor/{anchor['bureau']}/{anchor['day']}",
                    actual=anchor_branch,
                    expected=anchor["branch"],
                )
            )
    reflections = {}
    for day in range(1, 31):
        base = seeds[2].calendar_context["lunar_calendar"]
        chart = build_ziwei_chart(
            synthetic_seed(base["year"], month=base["month"], day=day), "男"
        )
        reflections[star_branch(chart, "紫微")] = star_branch(chart, "天府")
    expected_reflections = source["tianfu_reflection"]["expected_by_ziwei_branch"]
    if reflections != expected_reflections:
        mismatches.append(
            dict(
                case="tianfu_diagram", actual=reflections, expected=expected_reflections
            )
        )
    return {
        "status": "partial" if not mismatches else "failed",
        "source": source["item_url"],
        "scan_frames_frozen": len({image["frame"] for image in source["images"]}),
        "image_files_frozen": len(source["images"]),
        "manual_scan_reader_count": source["reader_count"],
        "independent_sihua_source_cells": sum(len(r) for r in expected.values()),
        "sihua_position_joins_checked": joined_positions,
        "edition_differences": edition_differences,
        "current_profiles_conform_to_ming_sihua": not any(edition_differences.values()),
        "comparison_context": "base_profiles_with_default_sihua_source_rule_profile",
        "ziwei_anchor_cells_checked": len(source["ziwei_anchor_cells"]),
        "tianfu_reflection_cells_checked": len(expected_reflections),
        "mismatches": mismatches,
        "whole_book_acceptance_passed": False,
        "limits": source["limits"],
    }


def report() -> dict[str, Any]:
    def implementation_hashes() -> dict[str, str]:
        return {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "pyproject.toml",
                "uv.lock",
                "src/fatebridge/core/almanac.py",
                "src/fatebridge/core/metaphysics/ziwei.py",
                "src/fatebridge/core/ziwei_rulesets.py",
                "src/fatebridge/core/ziwei_calendar.py",
                "src/fatebridge/core/ziwei_date_sources.py",
                "src/fatebridge/core/lunar_1900_prefix.py",
                "src/fatebridge/core/lunar_supplement.py",
                "src/fatebridge/core/ziwei_time_input.py",
                "src/fatebridge/core/metaphysics/common.py",
                "src/fatebridge/core/requests/birth.py",
                "src/fatebridge/core/ziwei_childhood.py",
                "src/fatebridge/core/ziwei_cycle_sources.py",
                "src/fatebridge/utils/solar_time.py",
                "src/fatebridge/utils/timezones.py",
                "src/fatebridge/utils/civil_clock.py",
                "src/fatebridge/core/ziwei_evidence.py",
                "src/fatebridge/core/ziwei_auxiliary.py",
                "src/fatebridge/core/ziwei_classical.py",
                "src/fatebridge/core/ziwei_ming_properties.py",
                "src/fatebridge/core/ziwei_conditions.py",
                "src/fatebridge/core/ziwei_subperiods.py",
                "src/fatebridge/core/ziwei_sources.py",
                "src/fatebridge/core/ziwei_aux_sources.py",
                "src/fatebridge/core/ziwei_limit_sources.py",
                "src/fatebridge/core/ziwei_tables.py",
                "src/fatebridge/utils/data.py",
                "src/fatebridge/core/output_chinese.py",
                "src/fatebridge/core/response_models.py",
                "src/fatebridge/core/requests/metaphysics.py",
                "src/fatebridge/data/agent_examples.json",
                "src/fatebridge/data/agent_scenarios.json",
                "skills/_shared/ziwei-topic-evidence.md",
                "skills/onda-xingpan/agents/interface.yaml",
                "src/fatebridge/data/classical/ziwei-quanshu-v2-table.json",
                "src/fatebridge/data/classical/ziwei-quanshu-v2-stars.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-symbolism.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-conditions.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-subperiods.json",
                "src/fatebridge/data/classical/ziwei-calendar-references.json",
                "src/fatebridge/data/lunar_calendar_pmo_1900_prefix.json",
                "src/fatebridge/data/lunar_calendar_hko_2100.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-sihua.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-days.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-prerequisites.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-auxiliaries.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-limits.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-childhood.json",
                "src/fatebridge/data/classical/ziwei-naj-ming-cycles.json",
                "src/fatebridge/services/metaphysics.py",
                "src/fatebridge/services/catalog/metaphysics.py",
                "src/fatebridge/application/result_delivery.py",
                "src/fatebridge/services/replay_metadata.py",
                "tests/fixtures/mcp_receipt.py",
                "tests/test_result_delivery.py",
                "tests/test_ziwei_eleventh_iteration.py",
                "tests/test_ziwei_twelfth_iteration.py",
                "scripts/audit_ziwei.py",
                "scripts/audit_ziwei_clock.py",
                "scripts/audit_ziwei_age.py",
                "src/fatebridge/core/ziwei_age.py",
                "src/fatebridge/data/classical/ziwei-age-source-scope.json",
                "tests/test_ziwei_twenty_first_iteration.py",
                "scripts/audit_ziwei_independent_readings.py",
                "scripts/audit_ziwei_review_disclosure.py",
                "scripts/build_ziwei_review_disclosure.py",
                "tests/test_ziwei_twenty_third_iteration.py",
                "src/fatebridge/validation/agent_capture.py",
                "src/fatebridge/data/classical/ziwei-naj-ming-targeted-review-r24.json",
                "scripts/build_ziwei_targeted_rereading.py",
                "scripts/audit_ziwei_targeted_rereading.py",
                "tests/test_ziwei_twenty_fourth_iteration.py",
                "tests/test_ziwei_twenty_fifth_iteration.py",
                "tests/test_ziwei_twenty_sixth_iteration.py",
                "scripts/audit_ziwei_natal_prerequisites.py",
                "src/fatebridge/data/classical/ziwei-naj-ming-days-review-r22.json",
                "src/fatebridge/api.py",
                "src/fatebridge/cli.py",
                "src/fatebridge/mcp_transport.py",
                "tests/test_ziwei_twenty_second_iteration.py",
                "scripts/audit_ziwei_time_input.py",
                "scripts/audit_ziwei_solar_clock.py",
                "scripts/collect_ziwei_solar_reference.py",
                "tests/test_ziwei_thirteenth_iteration.py",
                "tests/test_ziwei_fourteenth_iteration.py",
                "scripts/audit_ziwei_ming_properties.py",
                "scripts/audit_ziwei_childhood.py",
                "scripts/audit_ziwei_cycles.py",
                "scripts/audit_ziwei_natal.py",
                "scripts/audit_ziwei_phase.py",
                "scripts/audit_ziwei_days.py",
                "scripts/audit_ziwei_prerequisites.py",
                "scripts/audit_ziwei_auxiliaries.py",
                "scripts/audit_ziwei_limits.py",
                "scripts/audit_ziwei_activation.py",
                "tests/test_ziwei_fifteenth_iteration.py",
                "tests/test_ziwei_eighth_iteration.py",
                "tests/test_ziwei_horoscope.py",
                "tests/test_ziwei_depth.py",
                "tests/test_ziwei_horoscope_crosscheck.py",
                "tests/test_ziwei_depth_transports.py",
                "tests/test_mcp_receipt.py",
                "tests/test_ziwei_sixteenth_iteration.py",
                "scripts/audit_ziwei_sihua_selection.py",
                "scripts/audit_ziwei_civil_fold.py",
                "tests/test_ziwei_seventeenth_iteration.py",
                "scripts/audit_ziwei_conditions.py",
                "tests/test_ziwei_eighteenth_iteration.py",
                "scripts/audit_ziwei_subperiods.py",
                "tests/test_ziwei_nineteenth_iteration.py",
                "scripts/audit_ziwei_calendar_sources.py",
                "tests/test_ziwei_twentieth_iteration.py",
                "tests/test_ziwei_depth.py",
            )
        }

    def source_hashes() -> dict[str, str]:
        return {
            name: hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
            for name in (
                "calendar_manifest.json",
                "age_calendar_scope_v1/manifest.json",
                "age_calendar_scope_v2/manifest.json",
                "independent_readings_r22_v1/manifest.json",
                "targeted_rereading_r24_v1/manifest.json",
                "clock_manifest.json",
                "time_input_manifest.json",
                "pre_decade_policy_manifest.json",
                "sihua_selection_vectors.json",
                "ziwei_civil_fold_v1/manifest.json",
                "naj_ming_conditions_v1/checksums.json",
                "naj_ming_conditions_r25_v1/manifest.json",
                "naj_ming_conditions_r25_v2/manifest.json",
                "naj_ming_conditions_v1/coverage_extension.json",
                "naj_ming_subperiods_v1/checksums.json",
                "naj_ming_subperiods_v1/coverage_extension.json",
                "calendar_1900_sources_v1/checksums.json",
                "calendar_implementation_coverage_extension.json",
                "../ziwei_solar_jpl_v1/protocol.json",
                "../ziwei_solar_jpl_v1/manifest.json",
                "classical_manifest.json",
                "additional_manifest.json",
                "natal_manifest.json",
                "depth_manifest.json",
                "phase_manifest.json",
                "naj_ming/checksums.json",
                "naj_ming_anxing_v1/checksums.json",
                "naj_ming_day_tables_v1/checksums.json",
                "naj_ming_prerequisites_v1/checksums.json",
                "naj_ming_auxiliaries_v1/checksums.json",
                "naj_ming_limits_v1/checksums.json",
                "naj_ming_childhood_v1/checksums.json",
                "naj_ming_cycles_v1/checksums.json",
                "naj_ming_symbolism_v1/checksums.json",
            )
        }

    implementation, sources = implementation_hashes(), source_hashes()
    calendar, classical = audit_calendar(), audit_classical()
    natal, additional = audit_natal(), audit_additional_classical()
    depth = audit_depth_classical()
    phase_days = audit_phase_days()
    ming = audit_ming_scan()
    ming_anxing = audit_ming_anxing()
    ming_days = audit_day_tables()
    ming_prerequisites = audit_prerequisites()
    ming_auxiliaries = audit_auxiliaries()
    ming_limits = audit_limits()
    clock_basis = audit_clock_basis(hko_rows, FIXTURES)
    childhood = audit_childhood()
    cycles = audit_cycles()
    time_input = audit_time_input()
    solar_clock = audit_solar_clock(hko_rows, FIXTURES)
    ming_properties = audit_ming_properties()
    activation = audit_activation()
    sihua_selection = audit_sihua_selection()
    civil_fold = audit_civil_fold()
    conditions = audit_conditions()
    subperiods = audit_subperiods()
    calendar_sources = audit_calendar_sources()
    age_calendar = audit_age_calendar(hko_rows, FIXTURES)
    natal_prerequisites = audit_natal_prerequisites(FIXTURES)
    independent_readings = audit_independent_readings(FIXTURES)
    review_disclosure = audit_review_disclosure()
    targeted_rereading = audit_targeted_rereading()
    if implementation_hashes() != implementation or source_hashes() != sources:
        raise RuntimeError(
            "Source changed during Ziwei audit; rerun against a stable snapshot"
        )
    return {
        "audit_version": "ziwei_professional_axes_v26",
        "audit_root": str(ROOT),
        "runtime_environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "environment_prefix": str(Path(sys.prefix).resolve()),
            "dependency_versions": dict(
                sorted(
                    (distribution.metadata["Name"], distribution.version)
                    for distribution in importlib.metadata.distributions()
                    if distribution.metadata["Name"]
                )
            ),
        },
        "implementation_sha256": implementation,
        "source_manifest_sha256": sources,
        "source_stability_verified": True,
        "calendar": calendar,
        "calendar_new_moon_extension": phase_days,
        "calendar_clock_basis": clock_basis,
        "calendar_time_input_receipts": time_input,
        "calendar_solar_clock": solar_clock,
        "ming_symbolic_definitions": ming_properties,
        "formal_decade_activation": activation,
        "explicit_ming_sihua_selection": sihua_selection,
        "explicit_civil_offset_resolution": civil_fold,
        "ming_structural_conditions": conditions,
        "ming_limit_subperiods": subperiods,
        "calendar_date_sources": calendar_sources,
        "coherent_nominal_age_calendar": age_calendar,
        "horoscope_natal_prerequisite_evidence": natal_prerequisites,
        "independent_source_readings": independent_readings,
        "independent_review_disclosure": review_disclosure,
        "targeted_source_rereading": targeted_rereading,
        "current_supported_civil_date_label_coverage": {
            "distinct_dates_compared": calendar["full_date_cells"]
            + calendar_sources["distinct_printed_civil_dates"],
            "runtime_supported_date_count": (
                LUNAR_SUPPORTED_SOLAR_END - LUNAR_SUPPORTED_SOLAR_START
            ).days
            + 1,
            "printed_date_labels_only_not_full_clock_acceptance": True,
            "fixed_source_cohort_never_reduced_to_runtime_support": True,
            "source_join": "TAM 1900-12-31 lunar 1900/11/10 to HKO 1901-01-01 lunar 1900/11/11; nineteen missing January month labels carry from the preceding printed table",
        },
        "classical": classical,
        "natal_software_reference": natal,
        "additional_classical_tables": additional,
        "depth_classical_rules": depth,
        "ming_scan_collation": ming,
        "ming_anxing_collation": ming_anxing,
        "ming_day_table_collation": ming_days,
        "ming_prerequisite_collation": ming_prerequisites,
        "ming_auxiliary_collation": ming_auxiliaries,
        "ming_limit_readings": ming_limits,
        "ming_childhood_rows": childhood,
        "ming_cycle_rules": cycles,
        "active_objective_axes": ["calendar", "classical", "interpretation_fidelity"],
        "interpretation_fidelity": {
            "status": "partial",
            "engine_evidence": "Versioned rules, natal geometry, scope palace map and transformation joins",
            "live_model_blind_evaluation": "not_run",
            "structured_fact_verifier": "same_run_calculation_claims_v1; not a free-text semantic certification",
            "symbolic_source_records_checked": depth["symbolic_source_records_checked"],
            "symbolic_calculation_joins_checked": depth[
                "symbolic_calculation_joins_checked"
            ],
            "score": None,
        },
        "real_world_prediction": {
            "required_for_current_objective": False,
            "status": "not_tested",
            "prospective_locked_cases": 0,
            "independent_outcomes": 0,
            "score": None,
            "required": [
                "Preregistered outcomes and time windows",
                "Predictions locked before outcomes",
                "Blind outcome adjudication and held-out sample",
                "Compare with base rates and non-chart baselines; retain failures/abstentions",
            ],
        },
        "full_acceptance_passed": False,
        "regression_checks_passed": not calendar["mismatches"]
        and not classical["failed_vectors"]
        and not natal["differences"]
        and not additional["differences"]
        and not depth["mismatches"]
        and not phase_days["mismatches"]
        and not ming["mismatches"]
        and not ming_anxing["mismatches"]
        and not ming_days["mismatches"]
        and not ming_prerequisites["mismatches"]
        and not ming_auxiliaries["mismatches"]
        and not ming_limits["mismatches"]
        and not clock_basis["differences"]
        and not childhood["mismatches"]
        and not cycles["mismatches"]
        and not time_input["differences"]
        and not solar_clock["differences"]
        and not ming_properties["mismatches"]
        and not activation["mismatches"]
        and not sihua_selection["differences"]
        and not civil_fold["differences"]
        and not conditions["differences"]
        and not subperiods["differences"]
        and not calendar_sources["differences"]
        and not age_calendar["differences"]
        and not natal_prerequisites["differences"]
        and not independent_readings["direct_position_differences"]
        and not review_disclosure["mismatches"]
        and not targeted_rereading["mismatches"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-full",
        action="store_true",
        help="Exit nonzero unless calendar, classical and interpretation fidelity have actually been established",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = report()
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    raise SystemExit(
        0 if result["regression_checks_passed"] and not args.require_full else 1
    )


if __name__ == "__main__":
    main()
