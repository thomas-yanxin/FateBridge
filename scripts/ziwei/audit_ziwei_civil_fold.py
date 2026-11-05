"""Check explicit civil instants against preimplementation IANA-rule inputs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.services.metaphysics import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.timezones import timezone_rules_metadata

FIXTURES = Path(__file__).resolve().parents[2] / "tests/data/ziwei_independent"


def audit_civil_fold(fixtures: Path = FIXTURES) -> dict[str, Any]:
    root = fixtures / "ziwei_civil_fold_v1"
    manifest = json.loads((root / "manifest.json").read_text())
    raw = (root / manifest["source"]["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["source"]["sha256"]:
        raise ValueError("Ziwei civil fold source checksum mismatch")
    rules = [
        line.split()
        for line in raw.decode().splitlines()
        if line.startswith("Rule\tPRC\t")
    ]
    if [
        "Rule",
        "PRC",
        "1986",
        "1991",
        "-",
        "Sep",
        "Sun>=11",
        "2:00",
        "0",
        "S",
    ] not in rules:
        raise ValueError("Missing frozen PRC autumn rule")
    if [
        "Rule",
        "PRC",
        "1987",
        "1991",
        "-",
        "Apr",
        "Sun>=11",
        "2:00",
        "1:00",
        "D",
    ] not in rules:
        raise ValueError("Missing frozen PRC spring rule")
    differences: list[dict[str, Any]] = []
    receipts, chronology = [], []
    for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
        for source in ("rule_profile", "naj_ming_v1"):
            for solar in (False, True):
                for case in manifest["cases"]:
                    wall = datetime.fromisoformat(case["wall"])
                    person = create_person_info(
                        wall.year,
                        wall.month,
                        wall.day,
                        wall.hour,
                        birth_minute=wall.minute,
                        birth_timezone=case["zone"],
                        birth_longitude=120,
                        use_true_solar_time=solar,
                        gender="男",
                    )
                    result = calculate_ziwei_birth(
                        person,
                        birth_utc_offset=case["offset"],
                        rule_profile=profile,
                        sihua_source=source,
                    )
                    if result.get("error"):
                        differences.append(dict(case=case["id"], error=result["error"]))
                        continue
                    basis = result["ziwei_birth"]["calendar_basis"]
                    clock = basis.get("civil_clock", {})
                    checks = {
                        k: clock.get(k) == v
                        for k, v in {
                            "timezone": case["zone"],
                            "instant_utc": case["expected_utc"],
                            "fold": case["expected_fold"],
                            "resolved_utc_offset": case["offset"],
                            "was_ambiguous": True,
                        }.items()
                    }
                    checks["context_join"] = (
                        result["analysis_context"].get("civil_instant_utc")
                        == case["expected_utc"]
                    )
                    checks["physical_reference"] = basis[
                        "reference_datetime_utc_plus_08"
                    ] == (
                        "1991-09-15 00:30:00"
                        if case["expected_fold"] == 0
                        else "1991-09-15 01:30:00"
                    )
                    if solar:
                        checks["dst"] = (
                            basis["time_input"]["daylight_saving_minutes"]
                            == case["expected_dst_minutes"]
                        )
                    if not all(checks.values()):
                        differences.append(
                            dict(
                                case=case["id"],
                                profile=profile,
                                source=source,
                                solar=solar,
                                checks=checks,
                            )
                        )
                    receipts.append(
                        dict(
                            case=case["id"],
                            profile=profile,
                            source=source,
                            solar=solar,
                            checks=checks,
                        )
                    )
        for case in manifest["chronology_cases"]:
            person = create_person_info(
                1991,
                9,
                15,
                1,
                birth_minute=case["birth_minute"],
                birth_timezone="Asia/Shanghai",
                gender="男",
                use_true_solar_time=False,
            )
            result = calculate_ziwei_horoscope(
                person,
                birth_utc_offset=case["birth_offset"],
                target_year=1991,
                target_month=9,
                target_day=15,
                target_hour=1,
                target_minute=case["target_minute"],
                target_utc_offset=case["target_offset"],
                rule_profile=profile,
            )
            allowed = not bool(result.get("error"))
            matches = allowed == case["expected_allowed"] and (
                allowed or "早于出生" in result.get("error", "")
            )
            if not matches:
                differences.append(
                    dict(chronology=case, profile=profile, error=result.get("error"))
                )
            chronology.append(dict(input=case, profile=profile, matches=matches))
    return dict(
        method_id=manifest["method_id"],
        independent_rule_conditioned_instants=len(manifest["cases"]),
        source_rule_records=len(rules),
        manual_readers=manifest["manual_readers"],
        birth_receipts_checked=len(receipts),
        chronology_cases_checked=len(chronology),
        differences=differences,
        receipts=receipts,
        chronology=chronology,
        source_timezone_rules_version="2025b",
        runtime_timezone_rules_version=timezone_rules_metadata("Asia/Shanghai").get(
            "iana_version"
        ),
        classical_clock_policy_verified=False,
        independent_lunar_date_vectors_added=0,
        independent_solar_correction_vectors_added=0,
        full_calendar_acceptance_passed=False,
        limits=manifest["limits"],
    )
