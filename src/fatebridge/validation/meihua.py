"""Bounded Mei Hua audit against frozen primary material, never efficacy scoring."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fatebridge.core.almanac import (
    LUNAR_SUPPORTED_SOLAR_END,
    LUNAR_SUPPORTED_SOLAR_START,
)
from fatebridge.core.divination import derive_meihua_hexagram
from fatebridge.core.meihua import build_meihua_evidence, meihua_ruleset
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.validation.meihua_runtime_guard import (
    capture_calendar_runtime,
    verify_calendar_runtime,
)
from fatebridge.validation.meihua_source_guard import (
    capture_package_sources,
    verify_package_sources,
)

_DAYS = [
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
]
_MONTHS = [
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
]


def read_source(path: Path) -> str:
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8-sig")


def reference_bundle(directory: Path) -> dict[str, Any]:
    """Fail on any changed reference before calculating results."""
    manifest = json.loads((directory / "sources.json").read_text(encoding="utf-8"))
    for record in [*manifest["sources"], *manifest["artifacts"]]:
        path = (directory / record["file"]).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Reference path escapes its frozen bundle")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Frozen reference changed: {record['file']}")
        if "content_sha256" in record:
            raw = (
                gzip.decompress(path.read_bytes())
                if path.suffix == ".gz"
                else path.read_bytes()
            )
            if hashlib.sha256(raw).hexdigest() != record["content_sha256"]:
                raise ValueError(f"Frozen source content changed: {record['file']}")
    calendar_ids = [
        r["id"] for r in manifest["sources"] if r["kind"] == "official_calendar"
    ]
    if len(calendar_ids) != 200 or set(calendar_ids) != {
        f"hko-{y}" for y in range(1901, 2101)
    }:
        raise ValueError("The v1 audit requires every HKO year from 1901 through 2100")
    return manifest  # type: ignore[no-any-return]


def hko_calendar_rows(text: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse HKO's labels; no production lunar conversion supplies expected dates."""
    year = source["initial_lunar_year"]
    month = source["initial_lunar_month"]
    leap = source["initial_is_leap_month"]
    rows = []
    previous = None
    for line in text.splitlines():
        match = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\S+)", line)
        if match is None:
            continue
        y, m, d = map(int, match.group(1, 2, 3))
        solar = date(y, m, d)
        if previous is not None and solar != previous + timedelta(days=1):
            raise ValueError("HKO reference has a missing or duplicate date")
        label = match.group(4)
        if label in _DAYS:
            day = _DAYS.index(label) + 1
        else:
            leap = label.startswith("閏")
            nominal_label = label.removeprefix("閏")
            if nominal_label not in _MONTHS:
                raise ValueError(f"Unknown HKO month label: {label}")
            month = _MONTHS.index(nominal_label) + 1
            if month == 1 and not leap:
                year = y
            day = 1
        rows.append(
            {
                "date": solar,
                "year": year,
                "month": month,
                "day": day,
                "is_leap_month": leap,
            }
        )
        previous = solar
    if not rows or rows[0]["date"].month != 1 or rows[0]["date"].day != 1:
        raise ValueError("HKO audit requires a complete calendar year")
    if rows[-1]["date"].month != 12 or rows[-1]["date"].day != 31:
        raise ValueError("HKO audit requires a complete calendar year")
    return rows


def audit_meihua(directory: Path) -> dict[str, Any]:
    package = Path(__file__).resolve().parents[1]
    implementation = capture_package_sources(package)
    runtime_inputs = capture_calendar_runtime()
    manifest = reference_bundle(directory)
    case_bundle = json.loads((directory / "cases.json").read_text(encoding="utf-8"))
    case_reports = []
    if {c["id"] for c in case_bundle["cases"]} != {
        "observing-plum",
        "peony",
        "pure-qian-changed-mutual",
        "pure-kun-changed-mutual",
    } or len(case_bundle["cases"]) != 4:
        raise ValueError("The v1 audit requires all four frozen cases")
    for case in case_bundle["cases"]:
        cast = derive_meihua_hexagram(**case["input"])
        # Historical examples supply a branch, not an absolute civil year or
        # zone. Neither is guessed; season is irrelevant to these comparisons.
        evidence = build_meihua_evidence(
            cast,
            lunar_year=None,
            is_leap_month=False,
            timezone_name="unspecified_classical_instant",
            month_branch="寅",
        )
        stages = {r["role"]: r for r in evidence["stage_relations"]}
        actual = {
            **{
                key: cast["seed"][key]
                for key in ("upper_number", "lower_number", "moving_line")
            },
            "base_code": cast["base_hexagram"]["binary_code"],
            "changed_code": cast["changed_hexagram"]["binary_code"],
            "mutual_code": cast["mutual_hexagram"]["binary_code"],
            "body": cast["body_trigram"]["name"],
            "use": cast["use_trigram"]["name"],
            "relation": cast["body_use_relation"],
            "changed_relation": stages["changed_use"]["relation"],
            "body_mutual": stages["body_mutual"]["trigram"],
            "use_mutual": stages["use_mutual"]["trigram"],
        }
        disagreements = [
            {"field": key, "expected": expected, "actual": actual[key]}
            for key, expected in case["expected"].items()
            if actual[key] != expected
        ]
        if set(case["expected"]) != set(actual):
            raise ValueError("Case oracle must retain every required field")
        case_reports.append(
            {"id": case["id"], "kind": case["kind"], "disagreements": disagreements}
        )

    calendar_reports = []
    for source in manifest["sources"]:
        if source["kind"] != "official_calendar":
            continue
        full_rows = hko_calendar_rows(read_source(directory / source["file"]), source)
        rows = [
            row
            for row in full_rows
            # Preserve the original v1 cohort when runtime support expands.
            # The new normative HKO segment has its own validation layer.
            if date(1901, 1, 1) <= row["date"] <= date(2100, 2, 8)
        ]
        mismatches = []
        for row in rows:
            solar = row["date"]
            result = calculate_meihua_analysis(
                analysis_year=solar.year,
                analysis_month=solar.month,
                analysis_day=solar.day,
                analysis_hour=12,
                analysis_timezone="Asia/Shanghai",
            )
            if "error" in result:
                mismatches.append(
                    {"date": solar.isoformat(), "error_code": result["error_code"]}
                )
                continue
            lunar = result["calendar_context"]["lunar_calendar"]
            expected = {
                key: row[key] for key in ("year", "month", "day", "is_leap_month")
            }
            actual = {key: lunar[key] for key in expected}
            expected_branch = "子丑寅卯辰巳午未申酉戌亥"[(row["year"] - 4) % 12]
            actual["meihua_year_branch"] = result["meihua"]["seed"]["year_branch"]
            expected["meihua_year_branch"] = expected_branch
            if actual != expected:
                mismatches.append(
                    {"date": solar.isoformat(), "expected": expected, "actual": actual}
                )
        calendar_reports.append(
            {
                "source_id": source["id"],
                "date_count": len(rows),
                "excluded_outside_supported_range": len(full_rows) - len(rows),
                "mismatch_count": len(mismatches),
                "mismatches": mismatches,
            }
        )

    quote_checks = []
    for rule in meihua_ruleset()["rules"]:
        if "quote" not in rule:
            continue
        source = next(r for r in manifest["sources"] if r["id"] == rule["source_id"])
        text = (directory / source["file"]).read_text(encoding="utf-8")
        quote_checks.append({"rule_id": rule["id"], "matched": rule["quote"] in text})
    if sum(r["date_count"] for r in calendar_reports) != 72723:
        raise ValueError("The v1 supported calendar cohort must contain 72723 dates")
    if LUNAR_SUPPORTED_SOLAR_START > date(
        1901, 1, 1
    ) or LUNAR_SUPPORTED_SOLAR_END < date(2100, 2, 8):
        raise ValueError("Runtime support must not shrink the frozen v1 cohort")
    passed = (
        all(not c["disagreements"] for c in case_reports)
        and all(not r["mismatches"] for r in calendar_reports)
        and all(q["matched"] for q in quote_checks)
    )
    verify_package_sources(package, implementation)
    verify_calendar_runtime(runtime_inputs)
    return {
        "audit_id": "meihua_frozen_reference_v1",
        "profile_id": meihua_ruleset()["id"],
        "implementation_sha256": implementation,
        "runtime_input_guard": runtime_inputs,
        "implementation_guard_scope": "package_files_and_resources_excluding_caches; fresh_process_and_stable_snapshot_required",
        "source_bundle_sha256": hashlib.sha256(
            (directory / "sources.json").read_bytes()
        ).hexdigest(),
        "selected_checks_passed": passed,
        "calendar": {
            "scope": "固定v1基准1901-01-01至2100-02-08、Asia/Shanghai、12:00；生产范围扩大不改旧分母。新增官方数据段另验，不代表所有时区、历制或独立天文精度",
            "reports": calendar_reports,
        },
        "classical_rules": {
            "cases": case_reports,
            "quote_checks": quote_checks,
            "full_text_conformance_established": False,
        },
        "interpretation": {
            "deterministic_fact_paths_exposed": True,
            "real_model_semantic_acceptance": "not_tested",
        },
        "real_world_prediction": {
            "status": "not_tested",
            "prospective_case_count": 0,
            "authority_certified": False,
            "universal_perfect_prediction_established": False,
        },
        "unresolved": case_bundle["unresolved"],
    }
