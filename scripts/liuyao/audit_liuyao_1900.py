"""Close the 1900 sixyao civil-label cohort using a frozen printed primary table."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from fatebridge.validation.meihua import hko_calendar_rows, read_source
from fatebridge.validation.meihua_calendar import reference_bundle
from scripts.liuyao.audit_liuyao_calendar import naoj_day, reference

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests/fixtures/meihua_calendar_v2"
WATCHED = (
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/lunar_1900_prefix.py",
    "src/fatebridge/data/lunar_calendar_pmo_1900_prefix.json",
    "src/fatebridge/core/calendar.py",
    "src/fatebridge/core/local_techniques/sixyao.py",
    "src/fatebridge/validation/meihua_calendar.py",
    "scripts/liuyao/audit_liuyao_1900.py",
    "scripts/liuyao/audit_liuyao_calendar.py",
    "tests/fixtures/meihua_calendar_v2/sources.json",
    "tests/fixtures/meihua_calendar_v2/sources/publisher.html",
    "tests/fixtures/meihua_calendar_v2/sources/tam-1900.pdf",
    "tests/fixtures/meihua_calendar_v2/retrieval.json",
    "tests/fixtures/meihua_calendar_v2/cells.json",
    "tests/fixtures/meihua_calendar_v2/extraction.json",
    "tests/fixtures/meihua_calendar_v2/landmarks.json",
    "tests/fixtures/liuyao_scan_v3/naoj-day-reference.json",
    "tests/fixtures/liuyao_scan_v3/calendar-freeze.json",
    "tests/fixtures/meihua_v1/sources.json",
)


def hashes() -> dict[str, str]:
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in WATCHED
    }


def audit() -> dict[str, Any]:
    from fatebridge.core.almanac import (
        LUNAR_SUPPORTED_SOLAR_END,
        LUNAR_SUPPORTED_SOLAR_START,
    )

    if (LUNAR_SUPPORTED_SOLAR_START, LUNAR_SUPPORTED_SOLAR_END) != (
        date(1900, 1, 1),
        date(2100, 12, 31),
    ):
        raise ValueError("Supported range changed; do not shrink the fixed 1900 cohort")
    before = hashes()
    manifest, full_rows = reference_bundle(REFERENCE)
    hko, anchor = reference()
    rows = list(full_rows)
    if len(full_rows) != 365 or len(rows) != 365:
        raise ValueError("The audit must retain all 365 printed and supported dates")
    first_source = next(s for s in hko["sources"] if s["id"] == "hko-1901")
    first_hko = hko_calendar_rows(
        read_source(ROOT / "tests/fixtures/meihua_v1" / first_source["file"]),
        first_source,
    )[0]
    last = rows[-1]
    seam = (
        first_hko["date"] == date(1901, 1, 1)
        and all(first_hko[k] == last[k] for k in ("year", "month", "is_leap_month"))
        and first_hko["day"] == last["day"] + 1
    )
    reports = []
    for zone in ("+08:00", "Asia/Shanghai"):
        mismatches, errors, unavailable = [], [], []
        day_checks = lunar_checks = 0
        for row in rows:
            solar = row["date"]
            for clock, late in (("12:00:00", False), ("23:00:00", True)):
                try:
                    actual = build_sixyao_result(
                        date=solar.isoformat(), time=clock, zone=zone, gua_code="111111"
                    )
                except (ValueError, RuntimeError) as error:
                    errors.append(
                        {"date": solar.isoformat(), "time": clock, "error": str(error)}
                    )
                    continue
                expected_day = naoj_day(solar, late_zi=late, anchor=anchor)
                day_checks += 1
                if actual["nongli"]["dayGanZi"] != expected_day:
                    mismatches.append(
                        {
                            "date": solar.isoformat(),
                            "time": clock,
                            "layer": "day_ganzhi",
                            "expected": expected_day,
                            "actual": actual["nongli"]["dayGanZi"],
                        }
                    )
                if late:
                    continue
                lunar = actual["calendar_context"]["lunar_calendar"]
                if lunar is None:
                    unavailable.append(solar.isoformat())
                    continue
                expected_lunar = {
                    k: row[k] for k in ("year", "month", "day", "is_leap_month")
                }
                actual_lunar = {k: lunar[k] for k in expected_lunar}
                lunar_checks += 1
                if actual_lunar != expected_lunar:
                    mismatches.append(
                        {
                            "date": solar.isoformat(),
                            "layer": "lunar",
                            "expected": expected_lunar,
                            "actual": actual_lunar,
                        }
                    )
        reports.append(
            {
                "timezone": zone,
                "date_count": len(rows),
                "day_checks": day_checks,
                "lunar_checks": lunar_checks,
                "mismatches": mismatches,
                "calculation_errors": errors,
                "lunar_unavailable": unavailable,
            }
        )
    after = hashes()
    passed = (
        before == after
        and seam
        and all(
            not r["mismatches"]
            and not r["calculation_errors"]
            and not r["lunar_unavailable"]
            and r["day_checks"] == 730
            and r["lunar_checks"] == 365
            for r in reports
        )
    )
    return {
        "audit_id": "liuyao_primary_1900_v6",
        "source_id": manifest["source_id"],
        "primary_printed_date_count": len(full_rows),
        "unique_supported_date_count": len(rows),
        "excluded_before_supported_start": 0,
        "newly_supported_prefix_count": 30,
        "supported_first_date": rows[0]["date"].isoformat(),
        "supported_last_date": rows[-1]["date"].isoformat(),
        "hko_1901_seam_passed": seam,
        "reports": reports,
        "implementation_and_manifests_unchanged": before == after,
        "sha256_before": before,
        "sha256_after": after,
        "selected_checks_passed": passed,
        "scope": "Printed Gregorian civil labels at noon; day Ganzhi at noon and local 23:00. Zones do not multiply the 365 unique dates. The newly supported 30-day prefix uses PMO data and is compared with the separately published TAM table; ancestral independence is not established. No exact astronomical-instant or universal historical-calendar certification.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("unique_supported_date_count", "selected_checks_passed")
            }
        )
    )
    raise SystemExit(0 if result["selected_checks_passed"] else 1)


if __name__ == "__main__":
    main()
