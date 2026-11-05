"""Audit the actual Ren seed/board chain against every frozen HKO civil date.

NAOJ day-cycle arithmetic and HKO hour/month tables supply independent
expectations. Published annual term dates cannot certify crossing minutes:
two admissible labels on a boundary date are counted as underdetermined.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_calendar_v1"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"
MONTH_BRANCHES = "寅卯辰巳午未申酉戌亥子丑"
DAYS = "初一 初二 初三 初四 初五 初六 初七 初八 初九 初十 十一 十二 十三 十四 十五 十六 十七 十八 十九 二十 廿一 廿二 廿三 廿四 廿五 廿六 廿七 廿八 廿九 三十".split()
MONTHS = "正月 二月 三月 四月 五月 六月 七月 八月 九月 十月 十一月 十二月".split()
TERM_NAMES = "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
TERM_SPELLING = {
    "驚蟄": "惊蛰",
    "穀雨": "谷雨",
    "小滿": "小满",
    "處暑": "处暑",
    "芒種": "芒种",
}
IMPLEMENTATION = (
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/calendar.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/core/metaphysics/ren_calendar.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/core/metaphysics/liureng_transmissions.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "scripts/audit_ren_calendar.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    expected = {"reference.json", "hko-stems.html", "hko-solar.html", "naoj-jdn.html"}
    if set(manifest["files"]) != expected or {
        p.name for p in corpus.iterdir()
    } != expected | {"freeze.json"}:
        raise ValueError("Frozen Ren calendar source inventory changed")
    for name, checksum in manifest["files"].items():
        if sha(corpus / name) != checksum:
            raise ValueError(f"Frozen Ren calendar reference changed: {name}")
    ref = json.loads((corpus / "reference.json").read_text())
    for name, checksum in ref["references"].items():
        if sha(ROOT / name) != checksum:
            raise ValueError(f"Referenced calendar manifest changed: {name}")
    return ref


def annual_rows(
    text: str, year: int, state: tuple[int, int, bool]
) -> tuple[list[dict[str, Any]], tuple[int, int, bool]]:
    lunar_year, month, leap = state
    rows = []
    for line in text.splitlines():
        match = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\S+)", line)
        if not match:
            continue
        solar = date(*map(int, match.group(1, 2, 3)))
        label = match.group(4)
        if label in DAYS:
            day = DAYS.index(label) + 1
        else:
            leap = label.startswith(("閏", "闰"))
            month_label = label.removeprefix("閏").removeprefix("闰")
            if month_label not in MONTHS:
                raise ValueError(f"Unknown HKO lunar token {label}")
            month = MONTHS.index(month_label) + 1
            day = 1
            if month == 1 and not leap:
                lunar_year = solar.year
        parts = line.split()
        term = TERM_SPELLING.get(parts[-1], parts[-1]) if len(parts) > 3 else None
        if term is not None and term not in TERM_NAMES:
            raise ValueError(f"Unknown HKO term token {term}")
        rows.append(
            dict(
                date=solar,
                year=lunar_year,
                month=month,
                day=day,
                is_leap_month=leap,
                term=term,
            )
        )
    length = (date(year + 1, 1, 1) - date(year, 1, 1)).days
    if [r["date"] for r in rows] != [
        date(year, 1, 1) + timedelta(days=i) for i in range(length)
    ]:
        raise ValueError("HKO has missing, duplicated, unordered or wrong-year dates")
    if [r["term"] for r in rows if r["term"]] != TERM_NAMES:
        raise ValueError("HKO must contain all 24 terms in published order")
    return rows, (lunar_year, month, leap)


def expected_day(solar: date, ref: dict[str, Any], late: bool) -> str:
    anchor = ref["day_cycle"]
    jdn = (
        anchor["jdn_anchor"]
        + (
            solar
            + timedelta(days=int(late))
            - date.fromisoformat(anchor["jdn_anchor_date"])
        ).days
    )
    cycle = (jdn + anchor["cycle_offset"]) % 60
    return STEMS[cycle % 10] + BRANCHES[cycle % 12]


def year_pair(year: int) -> str:
    return STEMS[(year - 1984) % 10] + BRANCHES[(year - 1984) % 12]


def table_stem(table: dict[str, str], stem: str, index: int) -> str:
    return next(value[index] for group, value in table.items() if stem in group)


def audit(years: list[int] | None = None, *, progress: bool = True) -> dict[str, Any]:
    ref = reference()
    requested = set(years or range(1901, 2101))
    if not requested or not requested <= set(range(1901, 2101)):
        raise ValueError("HKO years must be 1901..2100")
    manifest = json.loads(
        (ROOT / "tests/data/ziwei_independent/calendar_manifest.json").read_text()
    )
    if [s["year"] for s in manifest["sources"]] != list(range(1901, 2101)):
        raise ValueError("The source cohort must retain all 200 HKO years")
    implementation = {name: sha(ROOT / name) for name in IMPLEMENTATION}
    # Only now import the production chain.
    from fatebridge.core.almanac import get_solar_terms_for_year
    from fatebridge.core.metaphysics.jinkou import build_jinkou_board
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from fatebridge.core.metaphysics.ren_calendar import require_ren_calendar
    from fatebridge.services.metaphysics import _build_analysis_seed

    annual = []
    failures = []
    errors = []
    term_failures = []
    state = (1900, 11, False)
    source_root = ROOT / "tests/data/ziwei_independent"
    totals = dict(
        civil_dates=0,
        day_checks=0,
        hour_checks=0,
        year_month_date_brackets=0,
        year_month_underdetermined=0,
        month_general_date_brackets=0,
        month_general_underdetermined=0,
        lunar_checks=0,
        lunar_unavailable=0,
        term_dates=0,
        calendar_policies=0,
    )
    for source in manifest["sources"]:
        file = source_root / source["path"]
        if sha(file) != source["sha256"]:
            raise ValueError(f"Frozen HKO text changed: {source['path']}")
        rows, state = annual_rows(
            file.read_text(encoding="utf-8-sig"), source["year"], state
        )
        if source["year"] not in requested:
            continue
        year = source["year"]
        before = dict(totals)
        terms = {t.name: t for t in get_solar_terms_for_year(year, "+08:00")}
        prior_month = "子"
        prior_general = "丑"
        prior_year = year - 1
        for row in rows:
            solar = row["date"]
            term = row["term"]
            totals["civil_dates"] += 1
            if term:
                totals["term_dates"] += 1
                actual = terms[term]
                if (
                    actual.moment.date() != solar
                    or actual.resolution_provider != "swisseph"
                ):
                    term_failures.append(
                        dict(
                            year=year,
                            term=term,
                            expected_date=solar.isoformat(),
                            actual=actual.moment.isoformat(),
                            provider=actual.resolution_provider,
                        )
                    )
            new_month = ref["month_starts"].get(term, prior_month)
            new_general = ref["general_starts"].get(term, prior_general)
            new_year = year if term == "立春" else prior_year
            # A term date bounds a physical crossing but does not say whether
            # noon is before or after it. The two correlated year/month states
            # are retained, never a permissive Cartesian product.
            ym_states = {(prior_year, prior_month), (new_year, new_month)}
            expected_ym = {
                (
                    year_pair(y),
                    table_stem(
                        ref["month_stems"], year_pair(y)[0], MONTH_BRANCHES.index(m)
                    )
                    + m,
                )
                for y, m in ym_states
            }
            allowed_generals = {prior_general, new_general}
            for hour in (12, 23):
                try:
                    seed = _build_analysis_seed(
                        analysis_year=year,
                        analysis_month=solar.month,
                        analysis_day=solar.day,
                        analysis_hour=hour,
                        analysis_timezone="+08:00",
                        use_true_solar_time=False,
                    )
                    policy = require_ren_calendar(seed)
                    seed.calendar_context["ren_calendar_policy"] = policy
                    board = build_liureng_board(seed)
                    jinkou = build_jinkou_board(seed, board, di_fen="子")
                except Exception as error:
                    errors.append(
                        dict(
                            date=solar.isoformat(),
                            hour=hour,
                            error_type=type(error).__name__,
                            message=str(error),
                        )
                    )
                    continue
                day = expected_day(solar, ref, hour == 23)
                hour_index = 6 if hour == 12 else 0
                expected_hour = (
                    table_stem(ref["hour_stems"], day[0], hour_index)
                    + BRANCHES[hour_index]
                )
                actual_day = "".join(seed.pillars["day"])
                actual_hour = "".join(seed.pillars["hour"])
                actual_ym = (
                    "".join(seed.pillars["year"]),
                    "".join(seed.pillars["month"]),
                )
                checks = {
                    "day": (actual_day, day),
                    "hour": (actual_hour, expected_hour),
                }
                totals["day_checks"] += 1
                totals["hour_checks"] += 1
                for layer, (actual, expected) in checks.items():
                    if actual != expected:
                        failures.append(
                            dict(
                                date=solar.isoformat(),
                                hour=hour,
                                layer=layer,
                                actual=actual,
                                expected=expected,
                            )
                        )
                totals["year_month_date_brackets"] += 1
                totals["year_month_underdetermined"] += int(len(expected_ym) > 1)
                if actual_ym not in expected_ym:
                    failures.append(
                        dict(
                            date=solar.isoformat(),
                            hour=hour,
                            layer="year_month",
                            actual=actual_ym,
                            expected_date_bracket=sorted(expected_ym),
                        )
                    )
                totals["month_general_date_brackets"] += 1
                totals["month_general_underdetermined"] += int(
                    len(allowed_generals) > 1
                )
                general = board["month_general"]["branch"]
                if (
                    general not in allowed_generals
                    or jinkou["overview"]["month_general"]["branch"] != general
                ):
                    failures.append(
                        dict(
                            date=solar.isoformat(),
                            hour=hour,
                            layer="month_general",
                            actual=general,
                            expected_date_bracket=sorted(allowed_generals),
                        )
                    )
                totals["calendar_policies"] += 1
                if (
                    board["calendar_policy"] != policy
                    or jinkou["calendar_policy"] != policy
                ):
                    failures.append(
                        dict(
                            date=solar.isoformat(),
                            hour=hour,
                            layer="calendar_policy_propagation",
                        )
                    )
                if hour == 12:
                    lunar = seed.calendar_context.get("lunar_calendar")
                    if lunar is None:
                        totals["lunar_unavailable"] += 1
                    else:
                        totals["lunar_checks"] += 1
                        keys = ("year", "month", "day", "is_leap_month")
                        expected = {key: row[key] for key in keys}
                        actual = {key: lunar[key] for key in keys}
                        if expected != actual:
                            failures.append(
                                dict(
                                    date=solar.isoformat(),
                                    layer="lunar",
                                    actual=actual,
                                    expected=expected,
                                )
                            )
            prior_year, prior_month, prior_general = new_year, new_month, new_general
        annual.append(
            dict(year=year, **{key: totals[key] - before[key] for key in totals})
        )
        if progress and len(annual) % 10 == 0:
            print(
                f"Ren calendar: {len(annual)} years, {totals['civil_dates']} dates, {len(failures)} calculation differences, {len(term_failures)} term-date differences",
                flush=True,
            )
    unchanged = implementation == {name: sha(ROOT / name) for name in IMPLEMENTATION}
    return dict(
        audit_id="ren_calendar_independent_v1",
        years=sorted(requested),
        full_hko_cohort=requested == set(range(1901, 2101)),
        clock="fixed +08:00 noon and 23:00 with declared late-Zi rollover",
        totals=totals,
        calculation_mismatch_count=len(failures),
        calculation_mismatches=failures,
        calculation_errors=errors,
        term_date_mismatch_count=len(term_failures),
        term_date_mismatches=term_failures,
        annual_reports=annual,
        implementation_sha256=implementation,
        implementation_unchanged_during_audit=unchanged,
        all_performed_comparisons_passed=not failures
        and not errors
        and not term_failures
        and unchanged,
        full_supported_calendar_domain_certified=False,
        goal_complete=False,
        source_sha256=sha(CORPUS / "reference.json"),
        limits=ref["limits"]
        + [
            ref["source_precision"],
            "No production errors or unavailable lunar dates are removed from counts. Unknown years and clocks remain unverified; source-day brackets cannot substitute for exact-minute boundary checks.",
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--year", action="append", type=int)
    args = parser.parse_args()
    report = audit(args.year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "totals": report["totals"],
                "calculation_mismatches": report["calculation_mismatch_count"],
                "term_date_mismatches": report["term_date_mismatch_count"],
                "errors": len(report["calculation_errors"]),
                "implementation_unchanged": report[
                    "implementation_unchanged_during_audit"
                ],
            }
        ),
        flush=True,
    )
    return 0 if report["all_performed_comparisons_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
