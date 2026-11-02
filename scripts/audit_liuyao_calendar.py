"""Compare actual sixyao calendar output with frozen HKO data and NAOJ facts."""

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from fatebridge.validation.meihua import (
    hko_calendar_rows,
    read_source,
    reference_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "tests/fixtures/liuyao_scan_v3"
HKO = ROOT / "tests/fixtures/meihua_v1"
IMPLEMENTATION_FILES = (
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/lunar_supplement.py",
    "src/fatebridge/data/lunar_calendar_hko_2100.json",
    "src/fatebridge/core/calendar.py",
    "src/fatebridge/core/local_techniques/sixyao.py",
    "scripts/audit_liuyao_calendar.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference() -> tuple[dict[str, Any], dict[str, Any]]:
    freeze = json.loads((REFERENCES / "calendar-freeze.json").read_text())
    if (
        sha(REFERENCES / "naoj-day-reference.json") != freeze["naoj_reference_sha256"]
        or sha(HKO / "sources.json") != freeze["hko_manifest_sha256"]
    ):
        raise ValueError("Frozen independent calendar reference changed")
    return reference_bundle(HKO), json.loads(
        (REFERENCES / "naoj-day-reference.json").read_text()
    )


def naoj_day(solar: date, *, late_zi: bool, anchor: dict[str, Any]) -> str:
    effective = solar + timedelta(days=int(late_zi))
    jdn = (
        anchor["jdn_anchor"]
        + (effective - date.fromisoformat(anchor["jdn_anchor_date"])).days
    )
    index = (jdn + anchor["day_cycle_offset"]) % 60
    return "甲乙丙丁戊己庚辛壬癸"[index % 10] + "子丑寅卯辰巳午未申酉戌亥"[index % 12]


def audit(years: list[int] | None = None) -> dict[str, Any]:
    implementation = {name: sha(ROOT / name) for name in IMPLEMENTATION_FILES}
    manifest, anchor = reference()
    requested = set(years or range(1901, 2101))
    if not requested or not requested <= set(range(1901, 2101)):
        raise ValueError("HKO reference years must be within 1901..2100")
    reports: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    unavailable: list[str] = []
    date_count = day_checks = lunar_checks = 0
    overlapping_source_checks = 0
    unavailable_count = 0
    for source in manifest["sources"]:
        if (
            source["kind"] != "official_calendar"
            or int(source["id"].split("-")[1]) not in requested
        ):
            continue
        rows = hko_calendar_rows(read_source(HKO / source["file"]), source)
        annual_day = annual_lunar = annual_unavailable = 0
        for row in rows:
            date_count += 1
            solar = row["date"]
            for clock, late in (("12:00:00", False), ("23:00:00", True)):
                try:
                    result = build_sixyao_result(
                        date=solar.isoformat(),
                        time=clock,
                        zone="+08:00",
                        gua_code="111111",
                    )
                except (ValueError, RuntimeError) as error:
                    errors.append(
                        {"date": solar.isoformat(), "time": clock, "error": str(error)}
                    )
                    continue
                expected_day = naoj_day(solar, late_zi=late, anchor=anchor)
                actual_day = result["nongli"]["dayGanZi"]
                day_checks += 1
                annual_day += 1
                if actual_day != expected_day:
                    mismatches.append(
                        {
                            "date": solar.isoformat(),
                            "time": clock,
                            "layer": "day_ganzhi",
                            "expected": expected_day,
                            "actual": actual_day,
                        }
                    )
                if late:
                    continue
                lunar = result["calendar_context"]["lunar_calendar"]
                if lunar is None:
                    unavailable_count += 1
                    annual_unavailable += 1
                    if len(unavailable) < 20:
                        unavailable.append(solar.isoformat())
                    continue
                expected = {
                    key: row[key] for key in ("year", "month", "day", "is_leap_month")
                }
                actual = {key: lunar[key] for key in expected}
                lunar_checks += 1
                if date(2100, 2, 9) <= solar <= date(2100, 12, 31):
                    overlapping_source_checks += 1
                annual_lunar += 1
                if actual != expected:
                    mismatches.append(
                        {
                            "date": solar.isoformat(),
                            "layer": "lunar",
                            "expected": expected,
                            "actual": actual,
                        }
                    )
        reports.append(
            {
                "source_id": source["id"],
                "dates": len(rows),
                "day_pillar_checks": annual_day,
                "lunar_checks": annual_lunar,
                "lunar_unavailable_count": annual_unavailable,
            }
        )
        if len(reports) % 20 == 0:
            print(
                f"Calendar audit: {len(reports)} years, {date_count} dates", flush=True
            )
    unchanged = implementation == {
        name: sha(ROOT / name) for name in IMPLEMENTATION_FILES
    }
    return {
        "audit_id": "liuyao_independent_calendar_v3",
        "years": sorted(requested),
        "full_hko_cohort": requested == set(range(1901, 2101)),
        "clock_convention": "fixed +08:00; noon and local 23:00 late-Zi; Gregorian civil dates",
        "civil_date_count": date_count,
        "day_pillar_comparison_count": day_checks,
        "lunar_comparison_count": lunar_checks,
        "lunar_engine_source_overlap_count": overlapping_source_checks,
        "lunar_external_reference_other_count": lunar_checks
        - overlapping_source_checks,
        "lunar_source_lineage_scope": "2100-02-09..12-31 runtime conversion now ingests the same HKO publication used by the reference. Those checks verify data decoding/ingestion consistency, not independent astronomical truth. Other date labels are compared with external published tables; counts are not independent real-world samples.",
        "lunar_unavailable_with_hko_reference": unavailable_count,
        "first_unavailable_examples": unavailable,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "calculation_error_count": len(errors),
        "calculation_errors": errors,
        "all_performed_comparisons_passed": not mismatches and not errors and unchanged,
        "implementation_unchanged_during_audit": unchanged,
        "unrestricted_calendar_conformance_established": False,
        "coverage_gaps": [
            "HKO annual bundle starts at 1901; supported 1900 dates need another independent reference",
            "Lunar dates unavailable despite HKO reference are counted explicitly, not dropped",
            "This audit does not replace independent exact solar-term and historical time-zone tests",
        ],
        "annual_reports": reports,
        "reference_sha256": {
            "hko_manifest": sha(HKO / "sources.json"),
            "naoj_anchor": sha(REFERENCES / "naoj-day-reference.json"),
        },
        "sources": {
            "hko": "https://www.hko.gov.hk/tc/gts/time/conversion.htm",
            "naoj": anchor["source_url"],
        },
        "implementation_sha256": implementation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--year", action="append", type=int)
    args = parser.parse_args()
    report = audit(args.year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "civil_date_count",
                    "day_pillar_comparison_count",
                    "lunar_comparison_count",
                    "mismatch_count",
                    "lunar_unavailable_with_hko_reference",
                )
            }
        ),
        flush=True,
    )
    return 0 if report["all_performed_comparisons_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
