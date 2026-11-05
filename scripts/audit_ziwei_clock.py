"""Compare Ziwei date labels with frozen HKO cells; retain policy gaps."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from fatebridge.services.metaphysics import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info


def audit_clock_basis(
    hko_reader: Callable[..., list[dict[str, Any]]], fixtures: Path
) -> dict[str, Any]:
    manifest = json.loads((fixtures / "clock_manifest.json").read_text())
    sources = json.loads((fixtures / "calendar_manifest.json").read_text())["sources"]
    sources_by_year = {s["year"]: s for s in sources}
    tables: dict[int, dict[str, Any]] = {}
    for source in manifest["source_documents"]:
        raw = (fixtures / source["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError("Clock source checksum mismatch: " + source["path"])

    def expected(label: str) -> dict[str, Any]:
        year = int(label[:4])
        if year not in tables:
            source = sources_by_year[year]
            raw = (fixtures / source["path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                raise ValueError("HKO clock cell checksum mismatch")
            tables[year] = {
                r["solar"].isoformat(): r
                for r in hko_reader(raw.decode("utf-8-sig"), year)
            }
        r = tables[year][label]
        if r["month"] is None or r["is_leap"] is None:
            raise ValueError("Clock case needs a complete independent HKO cell")
        return dict(
            year=r["year"], month=r["month"], day=r["day"], is_leap_month=r["is_leap"]
        )

    differences, receipts = [], []
    for case in manifest["cases"]:
        for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
            person = create_person_info(**case["input"])
            result = calculate_ziwei_birth(person, rule_profile=profile)
            basis = result["ziwei_birth"]["calendar_basis"]
            checks = {
                "placement_datetime": basis["placement_datetime"][:10]
                == case["placement_date"],
                "civil_datetime": basis["civil_datetime"][:10] == case["civil_date"],
                "reference_datetime": basis["reference_datetime_utc_plus_08"]
                == case["reference_datetime_utc_plus_08"],
                "placement_lunar": basis["placement_lunar_date"]
                == expected(case["placement_date"]),
                "civil_lunar": basis["civil_date_lunar_date"]
                == expected(case["civil_date"]),
                "reference_lunar": basis["reference_lunar_date"]
                == expected(case["reference_datetime_utc_plus_08"][:10]),
                "calculation_join": basis["placement_lunar_date"]
                == result["ziwei_birth"]["lunar_date"],
                "date_shift": basis["date_shift_days"]
                == (
                    date.fromisoformat(case["placement_date"])
                    - date.fromisoformat(case["civil_date"])
                ).days,
            }
            if not all(checks.values()):
                differences.append(
                    dict(case=case["id"], profile=profile, checks=checks)
                )
            receipts.append(dict(case=case["id"], profile=profile, checks=checks))

    # The physical civil endpoints determine age independently of the natal
    # solar-date placement label. The source does not certify this boundary rule.
    case = next(c for c in manifest["cases"] if c["id"] == "cny_east_forward")
    age_boundaries = []
    for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
        result = calculate_ziwei_horoscope(
            create_person_info(**case["input"]),
            rule_profile=profile,
            target_year=1984,
            target_month=2,
            target_day=1,
            target_hour=23,
            target_minute=59,
        )
        horoscope = result["ziwei_horoscope"]
        age_calendar = horoscope["nominal_age_calendar"]
        civil_lunar = expected(case["civil_date"])
        checks = {
            "basis": age_calendar["basis"] == "birth_civil_timezone",
            "physical_order": age_calendar["physical_order_checked"] is True,
            "birth_lunar_date": age_calendar["birth_lunar_date"] == civil_lunar,
            "target_lunar_date": age_calendar["target_lunar_date"] == civil_lunar,
            "placement_year": age_calendar["birth_placement_lunar_year"]
            == expected(case["placement_date"])["year"],
            "nominal_age": horoscope["nominal_age"] == 1,
            "classical_boundary_unverified": age_calendar[
                "age_boundary_classically_verified"
            ]
            is False,
        }
        age_boundaries.append(dict(profile=profile, case=case["id"], checks=checks))
        if not all(checks.values()):
            differences.append(
                dict(case="civil_age_boundary", profile=profile, checks=checks)
            )
    return {
        "method_id": manifest["schema_version"],
        "independent_input_cases": len(manifest["cases"]),
        "profile_receipts_checked": len(receipts),
        "receipts": receipts,
        "differences": differences,
        "civil_age_boundary_receipts": age_boundaries,
        "classical_clock_policy_verified": False,
        "full_clock_acceptance_passed": False,
        "scope": "Date-table receipt consistency only; correction magnitudes, historical clock choices and local lunations are separate",
    }
