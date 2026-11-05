"""Compare all printed 1900 dates with Ziwei outputs; audit source attribution."""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fatebridge.core.almanac import LUNAR_YEAR_INFO_CORRECTIONS
from fatebridge.services.metaphysics import calculate_ziwei_birth
from fatebridge.utils.birth_input import create_person_info

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/data/ziwei_independent"


def frozen_calendar_rows(
    fixtures: Path = FIXTURES,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    folder = fixtures / "calendar_1900_sources_v1"
    for name, expected in json.loads((folder / "checksums.json").read_text()).items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Ziwei printed calendar source checksum mismatch: " + name)
    source = json.loads((folder / "manifest.json").read_text())
    expected = json.loads((folder / "expected_dates.json").read_text())
    if len(expected) != 365 or [r["solar"] for r in expected] != [
        (date(1900, 1, 1) + timedelta(days=i)).isoformat() for i in range(365)
    ]:
        raise ValueError("The entire fixed 1900 date cohort must be retained")
    return source, expected


def audit_calendar_sources(fixtures: Path = FIXTURES) -> dict[str, Any]:
    folder = fixtures / "calendar_1900_sources_v1"
    source, expected = frozen_calendar_rows(fixtures)
    compiled = json.loads(
        (
            ROOT / "src/fatebridge/data/classical/ziwei-calendar-references.json"
        ).read_text()
    )
    differences: list[dict[str, Any]] = []
    if compiled["references"] != source["references"]:
        differences.append(dict(case="compiled_date_reference_catalogue"))
    reports = []
    for zone in source["zones"]:
        for profile in source["profiles"]:
            cells = joins = prefix = 0
            for row in expected:
                solar = date.fromisoformat(row["solar"])
                result = calculate_ziwei_birth(
                    create_person_info(
                        birth_year=1900,
                        birth_month=solar.month,
                        birth_day=solar.day,
                        birth_hour=source["birth_hour"],
                        birth_timezone=zone,
                        gender=source["gender"],
                        use_true_solar_time=source["true_solar"],
                    ),
                    rule_profile=profile,
                )
                if "error" in result:
                    differences.append(
                        dict(
                            case="calendar_input_rejected",
                            date=row["solar"],
                            zone=zone,
                            profile=profile,
                            error=result["error"],
                        )
                    )
                    continue
                chart = result["ziwei_birth"]
                basis = chart["calendar_basis"]
                p = basis["date_conversion_provenance"]
                expected_lunar = {
                    k: row[k] for k in ("year", "month", "day", "is_leap_month")
                }
                provider = (
                    "pmo_1900_january_prefix_v1"
                    if solar < date(1900, 1, 31)
                    else "fatebridge_lunardate_adapter_v1"
                )
                ok = all(chart["lunar_date"][k] == v for k, v in expected_lunar.items())
                ok = ok and chart["year_stem"] == (
                    "己" if row["year"] == 1899 else "庚"
                )
                ok = ok and chart["chart_masters"]["body"]["basis_branch"] == (
                    "亥" if row["year"] == 1899 else "子"
                )
                for clock, key in [
                    ("placement", "placement_lunar_date"),
                    ("civil", "civil_date_lunar_date"),
                    ("reference_utc_plus_08", "reference_lunar_date"),
                ]:
                    ok = ok and basis[key] == expected_lunar
                    ok = ok and p["lookups"][clock] == dict(
                        solar_date=row["solar"],
                        status="available",
                        implementation_provider=provider,
                        printed_date_reference="tam_1900",
                        applied_year_info_correction=None,
                    )
                    joins += 1
                ok = ok and (
                    basis["reference_source"] == source["references"]["tam_1900"]["url"]
                    and p["printed_date_references"]
                    == {"tam_1900": source["references"]["tam_1900"]}
                    and p["historical_clock_policy_verified"] is False
                    and p["implementation_data_is_independent_validation"] is False
                    and result["analysis_context"]["lunar_date_provider"] == provider
                    and result["analysis_context"]["lunar_date_reference"] == "tam_1900"
                    and "臺北市立天文科學教育館" in result["snapshot_text"]
                )
                if provider != "fatebridge_lunardate_adapter_v1":
                    impl = p["implementation_sources"][provider]
                    ok = ok and impl["publisher"] == "中国科学院紫金山天文台"
                    ok = (
                        ok
                        and impl["raw_sha256"]
                        == json.loads(
                            (folder / "pmo_prefix/reference.json").read_text()
                        )["source_sha256"]
                    )
                    prefix += 1
                else:
                    ok = (
                        ok
                        and p["implementation_sources"][provider]["publisher"]
                        == "FateBridge"
                    )
                if not ok:
                    differences.append(
                        dict(
                            case="printed_date_or_attribution",
                            date=row["solar"],
                            zone=zone,
                            profile=profile,
                        )
                    )
                cells += 1
            reports.append(
                dict(
                    zone=zone,
                    profile=profile,
                    dates_checked=cells,
                    clock_reference_joins=joins,
                    pmo_prefix_cases=prefix,
                )
            )
    extension = json.loads(
        (fixtures / "calendar_implementation_coverage_extension.json").read_text()
    )
    if (
        extension["original_1900_manifest_sha256"]
        != hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest()
        or not extension["declared_after_implementation"]
        or len(extension["correction_cases"]) != 6
    ):
        raise ValueError("Calendar implementation coverage policy mismatch")
    if {r["lunar_year"] for r in extension["correction_cases"]} != set(
        LUNAR_YEAR_INFO_CORRECTIONS
    ):
        differences.append(dict(case="uncovered_year_info_correction_registry"))
    correction_receipts = 0
    for row in extension["correction_cases"]:
        solar = date.fromisoformat(row["solar"])
        for profile in source["profiles"]:
            for zone in source["zones"]:
                result = calculate_ziwei_birth(
                    create_person_info(
                        birth_year=solar.year,
                        birth_month=solar.month,
                        birth_day=solar.day,
                        birth_hour=12,
                        birth_timezone=zone,
                        use_true_solar_time=False,
                        gender="未知",
                    ),
                    rule_profile=profile,
                )
                chart = result.get("ziwei_birth", {})
                p = chart.get("calendar_basis", {}).get(
                    "date_conversion_provenance", {}
                )
                if (
                    chart.get("lunar_date", {}).get("year") != row["lunar_year"]
                    or not p.get("lookups")
                    or not all(
                        v["implementation_provider"] == extension["expected_provider"]
                        and v["applied_year_info_correction"]
                        == row["encoded_year_info"]
                        for v in p["lookups"].values()
                    )
                ):
                    differences.append(
                        dict(
                            case="adapter_correction_attribution",
                            solar=row["solar"],
                            profile=profile,
                            zone=zone,
                        )
                    )
                correction_receipts += 1
    return dict(
        method_id=source["method_id"],
        distinct_printed_civil_dates=365,
        reused_existing_primary_corpus=True,
        new_publishing_institutions_in_this_round=0,
        distinct_publishers_in_reused_material=2,
        independent_human_reviewers=0,
        independent_model_reviewers=0,
        calendar_receipts_checked=sum(r["dates_checked"] for r in reports),
        clock_reference_joins_checked=sum(r["clock_reference_joins"] for r in reports),
        adapter_correction_code_path_cases=len(extension["correction_cases"]),
        adapter_correction_receipts_checked=correction_receipts,
        adapter_correction_probes_are_independent_calendar_truth=False,
        reports=reports,
        moon_instants_or_classical_clock_rule_validated=False,
        mixed_clock_age_boundary_resolved=False,
        live_model_blind_evaluation="not_run",
        full_calendar_acceptance_passed=False,
        differences=differences,
        limits=source["limits"],
    )
