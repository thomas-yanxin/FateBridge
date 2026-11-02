"""Audit the missing 1900 civil-date cohort against a printed primary table."""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fatebridge.validation.meihua_runtime_guard import (
    capture_calendar_runtime,
    verify_calendar_runtime,
)
from fatebridge.validation.meihua_source_guard import (
    capture_package_sources,
    verify_package_sources,
)

_DAYS = (
    "初一 初二 初三 初四 初五 初六 初七 初八 初九 初十 "
    "十一 十二 十三 十四 十五 十六 十七 十八 十九 二十 "
    "廿一 廿二 廿三 廿四 廿五 廿六 廿七 廿八 廿九 三十"
).split()
_MONTHS = "正月 二月 三月 四月 五月 六月 七月 八月 九月 十月 十一月 十二月".split()


def tam_calendar_rows(
    cells: list[dict[str, Any]], *, initial_lunar_year: int
) -> list[dict[str, Any]]:
    """Decode printed labels only; never obtain expected dates from a calculator."""
    if initial_lunar_year != 1899 or len(cells) != 365:
        raise ValueError("The fixed primary cohort must retain all 365 dates in 1900")
    year, month, day, leap = initial_lunar_year, 0, 0, False
    rows: list[dict[str, Any]] = []
    for index, cell in enumerate(cells):
        solar = date.fromisoformat(cell["date"])
        if solar != date(1900, 1, 1) + timedelta(days=index):
            raise ValueError("Primary cells have a missing, duplicate or invalid date")
        if (cell["gregorian_month_row"], cell["gregorian_day_column"]) != (
            solar.month,
            solar.day,
        ) or cell["source_page"] != 0:
            raise ValueError("Primary cell coordinates disagree with their civil date")
        label = cell["printed_label"]
        if label.endswith("月"):
            next_leap = label.startswith("閏")
            nominal = label.removeprefix("閏")
            if nominal not in _MONTHS:
                raise ValueError("Unrecognized printed lunar month")
            next_month = _MONTHS.index(nominal) + 1
            if index == 0:
                if label != "十二月":
                    raise ValueError("The fixed table must start at lunar 1899/12/1")
            else:
                if day not in (29, 30):
                    raise ValueError("Printed lunar month length must be 29 or 30")
                if next_leap:
                    if leap or next_month != month:
                        raise ValueError("A leap month must repeat its preceding month")
                elif next_month != month % 12 + 1:
                    raise ValueError("Printed lunar months must advance in order")
                if next_month == 1 and not next_leap:
                    year += 1
            month, day, leap = next_month, 1, next_leap
        elif label in _DAYS:
            next_day = _DAYS.index(label) + 1
            if not rows or next_day != day + 1:
                raise ValueError("Printed lunar days must advance without gaps")
            day = next_day
        else:
            raise ValueError("Unrecognized printed lunar day")
        rows.append(
            {
                "date": solar,
                "year": year,
                "month": month,
                "day": day,
                "is_leap_month": leap,
            }
        )
    return rows


def reference_bundle(directory: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads((directory / "sources.json").read_text(encoding="utf-8"))
    required = {
        "sources/publisher.html",
        "sources/tam-1900.pdf",
        "retrieval.json",
        "cells.json",
        "extraction.json",
        "landmarks.json",
    }
    if {r["file"] for r in manifest["artifacts"]} != required:
        raise ValueError("The primary bundle must retain source, cells and landmarks")
    for record in manifest["artifacts"]:
        path = (directory / record["file"]).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Reference path escapes its frozen bundle")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Frozen primary reference changed: {record['file']}")
    cells = json.loads((directory / "cells.json").read_text(encoding="utf-8"))["cells"]
    landmarks = json.loads((directory / "landmarks.json").read_text(encoding="utf-8"))
    labels = {c["date"]: c["printed_label"] for c in cells}
    if any(labels.get(d) != label for d, label in landmarks["landmarks"].items()):
        raise ValueError("Extracted cells disagree with visual primary landmarks")
    return manifest, tam_calendar_rows(
        cells, initial_lunar_year=landmarks["initial_lunar_year"]
    )


def audit_tam_1900(directory: Path) -> dict[str, Any]:
    package = Path(__file__).resolve().parents[1]
    implementation = capture_package_sources(package)
    runtime_inputs = capture_calendar_runtime()
    # Imports belong to the comparison stage, after the printed oracle exists.
    from fatebridge.core.almanac import (
        LUNAR_SUPPORTED_SOLAR_END,
        LUNAR_SUPPORTED_SOLAR_START,
    )
    from fatebridge.services.divination import calculate_meihua_analysis

    manifest, full_rows = reference_bundle(directory)
    if (LUNAR_SUPPORTED_SOLAR_START, LUNAR_SUPPORTED_SOLAR_END) != (
        date(1900, 1, 1),
        date(2100, 12, 31),
    ):
        raise ValueError("Supported dates changed; do not shrink this audit cohort")
    rows = list(full_rows)
    if len(rows) != 365:
        raise ValueError("Every supported 1900 civil date must be compared")
    reports = []
    for zone in ("UTC+08:00", "Asia/Shanghai"):
        mismatches = []
        for row in rows:
            solar = row["date"]
            result = calculate_meihua_analysis(
                analysis_year=solar.year,
                analysis_month=solar.month,
                analysis_day=solar.day,
                analysis_hour=12,
                analysis_timezone=zone,
            )
            if "error" in result:
                mismatches.append(
                    {"date": solar.isoformat(), "error_code": result["error_code"]}
                )
                continue
            expected = {
                key: row[key] for key in ("year", "month", "day", "is_leap_month")
            }
            lunar = result["calendar_context"]["lunar_calendar"]
            actual = {key: lunar[key] for key in expected}
            expected.update(
                year_branch="亥" if row["year"] == 1899 else "子",
                lunar_month=row["month"],
                lunar_day=row["day"],
                hour_branch="午",
            )
            seed = result["meihua"]["seed"]
            actual.update(
                {
                    key: seed[key]
                    for key in (
                        "year_branch",
                        "lunar_month",
                        "lunar_day",
                        "hour_branch",
                    )
                }
            )
            if actual != expected:
                mismatches.append(
                    {"date": solar.isoformat(), "expected": expected, "actual": actual}
                )
        reports.append(
            {
                "timezone": zone,
                "hour": 12,
                "date_count": len(rows),
                "mismatch_count": len(mismatches),
                "mismatches": mismatches,
            }
        )
    verify_package_sources(package, implementation)
    verify_calendar_runtime(runtime_inputs)
    return {
        "audit_id": "meihua_tam_calendar_1900_v3",
        "implementation_sha256": implementation,
        "runtime_input_guard": runtime_inputs,
        "implementation_guard_scope": "package_files_and_resources_excluding_caches; fresh_process_and_stable_snapshot_required",
        "source_bundle_sha256": hashlib.sha256(
            (directory / "sources.json").read_bytes()
        ).hexdigest(),
        "source_id": manifest["source_id"],
        "primary_printed_date_count": len(full_rows),
        "unique_supported_date_count": len(rows),
        "excluded_before_supported_start": 0,
        "newly_supported_prefix_count": 30,
        "prefix_source_scope": "Runtime prefix uses PMO's retained historical labels; this comparison uses the separately published TAM table. Ancestral calendar independence is not established.",
        "first_supported_date": rows[0]["date"].isoformat(),
        "last_supported_date": rows[-1]["date"].isoformat(),
        "reports": reports,
        "selected_checks_passed": all(not r["mismatches"] for r in reports),
        "scope": "Printed civil date-label agreement at selected-zone noon; not astronomical instant reconstruction or all timezone policies.",
        "real_world_predictive_efficacy_established": False,
    }


def audit_hko_2100_supplement(directory: Path) -> dict[str, Any]:
    """Test the added normative segment without rewriting the v1 denominator."""
    package = Path(__file__).resolve().parents[1]
    implementation = capture_package_sources(package)
    runtime_inputs = capture_calendar_runtime()
    from fatebridge.services.divination import calculate_meihua_analysis
    from fatebridge.validation.meihua import hko_calendar_rows, read_source
    from fatebridge.validation.meihua import reference_bundle as hko_bundle

    manifest = hko_bundle(directory)
    source = next(s for s in manifest["sources"] if s["id"] == "hko-2100")
    rows = [
        r
        for r in hko_calendar_rows(read_source(directory / source["file"]), source)
        if date(2100, 2, 9) <= r["date"] <= date(2100, 12, 31)
    ]
    if len(rows) != 326:
        raise ValueError("The normative supplement cohort must retain all 326 dates")
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
        expected = {k: row[k] for k in ("year", "month", "day", "is_leap_month")}
        expected["meihua_year_branch"] = "子丑寅卯辰巳午未申酉戌亥"[
            (row["year"] - 4) % 12
        ]
        actual = {k: lunar[k] for k in ("year", "month", "day", "is_leap_month")}
        actual["meihua_year_branch"] = result["meihua"]["seed"]["year_branch"]
        if expected != actual:
            mismatches.append(
                {"date": solar.isoformat(), "expected": expected, "actual": actual}
            )
    verify_package_sources(package, implementation)
    verify_calendar_runtime(runtime_inputs)
    return {
        "source_id": source["id"],
        "implementation_sha256": implementation,
        "runtime_input_guard": runtime_inputs,
        "implementation_guard_scope": "package_files_and_resources_excluding_caches; fresh_process_and_stable_snapshot_required",
        "first_date": "2100-02-09",
        "last_date": "2100-12-31",
        "unique_date_count": len(rows),
        "mismatches": mismatches,
        "production_source_overlap": True,
        "scope": "The same HKO publication supplies production month starts and expected labels; this verifies ingestion and time-cast use, not independent astronomical accuracy.",
    }


def audit_supported_calendar(
    tam_directory: Path, hko_directory: Path
) -> dict[str, Any]:
    """Join the two independently published cohorts without double-counting zones."""
    from fatebridge.validation.meihua import (
        audit_meihua,
        hko_calendar_rows,
        read_source,
    )
    from fatebridge.validation.meihua import reference_bundle as hko_bundle

    package = Path(__file__).resolve().parents[1]
    implementation = capture_package_sources(package)
    runtime_inputs = capture_calendar_runtime()
    tam = audit_tam_1900(tam_directory)
    hko = audit_meihua(hko_directory)
    supplement = audit_hko_2100_supplement(hko_directory)
    manifest = hko_bundle(hko_directory)
    source = next(s for s in manifest["sources"] if s["id"] == "hko-1901")
    first_hko = hko_calendar_rows(read_source(hko_directory / source["file"]), source)[
        0
    ]
    _, tam_rows = reference_bundle(tam_directory)
    last_tam = tam_rows[-1]
    seam_fields = ("year", "month", "is_leap_month")
    seam_passed = (
        first_hko["date"] == last_tam["date"] + timedelta(days=1)
        and all(first_hko[k] == last_tam[k] for k in seam_fields)
        and first_hko["day"] == last_tam["day"] + 1
    )
    baseline_count = sum(r["date_count"] for r in hko["calendar"]["reports"])
    hko_count = baseline_count + supplement["unique_date_count"]
    unique_count = tam["unique_supported_date_count"] + hko_count
    if unique_count != (date(2100, 12, 31) - date(1900, 1, 1)).days + 1:
        raise ValueError("Published cohorts must cover the unchanged supported range")
    verify_package_sources(package, implementation)
    verify_calendar_runtime(runtime_inputs)
    return {
        "audit_id": "meihua_supported_civil_calendar_v3",
        "implementation_sha256": implementation,
        "runtime_input_guard": runtime_inputs,
        "implementation_guard_scope": "package_files_and_resources_excluding_caches; fresh_process_and_stable_snapshot_required",
        "supported_first_date": "1900-01-01",
        "supported_last_date": "2100-12-31",
        "normative_source_overlap": {
            "first_date": "2100-02-09",
            "last_date": "2100-12-31",
            "date_count": 326,
            "scope": "Runtime now ingests the same HKO publication for this finite segment. Agreement checks faithful ingestion, not independent astronomical accuracy.",
        },
        "annual_primary_sources": 201,
        "unique_civil_dates_compared": unique_count,
        "tam_1900": tam,
        "hko_1901_2100": {
            "source_bundle_sha256": hko["source_bundle_sha256"],
            "calendar": hko["calendar"],
            "unique_date_count": hko_count,
            "v1_baseline_unique_date_count": baseline_count,
            "supplement_2100": supplement,
        },
        "cross_publisher_seam": {
            "tam_last": {
                k: str(v) if isinstance(v, date) else v for k, v in last_tam.items()
            },
            "hko_first": {
                k: str(v) if isinstance(v, date) else v for k, v in first_hko.items()
            },
            "consecutive_printed_lunar_days": seam_passed,
        },
        "selected_checks_passed": (
            tam["selected_checks_passed"]
            and all(not r["mismatches"] for r in hko["calendar"]["reports"])
            and not supplement["mismatches"]
            and seam_passed
        ),
        "scope": "Complete supported civil-date labels at selected-zone noon. HKO uses Asia/Shanghai; TAM also checks fixed UTC+08:00. Historical Asia/Shanghai offsets are not uniformly UTC+8. No assertion about all instants, timezone conventions, solar terms or original-text exclusivity.",
        "real_world_predictive_efficacy_established": False,
        "authority_certified": False,
    }
