"""Clock-coherent age joins against the existing frozen printed date cells.

This is a declared post-implementation extension of the nine clock inputs.
Repeated zones/profiles are joins, not additional independent observations.
"""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.ziwei_age import age_source_scope
from fatebridge.services.metaphysics import calculate_ziwei_horoscope
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.timezones import parse_timezone_name


def audit_age_calendar(
    hko_reader: Callable[..., list[dict[str, Any]]], fixtures: Path
) -> dict[str, Any]:
    scope_manifest = json.loads(
        (fixtures / "age_calendar_scope_v2/manifest.json").read_text()
    )
    for entry in scope_manifest["files"]:
        if (
            hashlib.sha256((fixtures / entry["path"]).read_bytes()).hexdigest()
            != entry["sha256"]
        ):
            raise ValueError("Age source scope checksum mismatch")
    collation = json.loads(
        (fixtures / "age_calendar_scope_v2/collation.json").read_text()
    )
    manifest = json.loads((fixtures / "clock_manifest.json").read_text())
    sources = {
        s["year"]: s
        for s in json.loads((fixtures / "calendar_manifest.json").read_text())[
            "sources"
        ]
    }
    tables: dict[int, dict[str, int]] = {}

    def printed_year(d: datetime) -> int:
        if d.year not in tables:
            s = sources[d.year]
            raw = (fixtures / s["path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != s["sha256"]:
                raise ValueError("Age calendar source checksum mismatch")
            tables[d.year] = {
                r["solar"].isoformat(): r["year"]
                for r in hko_reader(raw.decode("utf-8-sig"), d.year)
            }
        return tables[d.year][d.date().isoformat()]

    receipts: list[dict[str, Any]] = []
    differences: list[dict[str, Any]] = []
    if age_source_scope() != collation:
        differences.append(dict(case="source_scope_transcription_changed"))
    for case in manifest["cases"]:
        inputs = case["input"]
        birth = localize_datetime(
            datetime(
                inputs["birth_year"],
                inputs["birth_month"],
                inputs["birth_day"],
                inputs["birth_hour"],
                inputs.get("birth_minute", 0),
            ),
            inputs["birth_timezone"],
        )
        birth_year = printed_year(birth)
        for minutes in (0, 4, 65):
            target = birth + timedelta(minutes=minutes)
            expected_age = printed_year(target) - birth_year + 1
            for zone in ("UTC", "+14:00", "-12:00"):
                display = target.astimezone(parse_timezone_name(zone))
                for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
                    result = calculate_ziwei_horoscope(
                        create_person_info(**inputs),
                        rule_profile=profile,
                        target_year=display.year,
                        target_month=display.month,
                        target_day=display.day,
                        target_hour=display.hour,
                        target_minute=display.minute,
                        target_timezone=zone,
                    )
                    h = result.get("ziwei_horoscope", {})
                    a = h.get("nominal_age_calendar", {})
                    checks = dict(
                        nominal_age=h.get("nominal_age") == expected_age,
                        birth_year=a.get("birth_lunar_year") == birth_year,
                        target_year=a.get("target_lunar_year") == printed_year(target),
                        birth_timezone=a.get("timezone") == inputs["birth_timezone"],
                        physical_order_checked=a.get("physical_order_checked") is True,
                        classical_boundary_not_claimed=a.get(
                            "age_boundary_classically_verified"
                        )
                        is False,
                    )
                    row = dict(
                        case=case["id"],
                        minutes_after_birth=minutes,
                        target_timezone=zone,
                        profile=profile,
                        expected_age=expected_age,
                        actual_age=h.get("nominal_age"),
                        checks=checks,
                    )
                    receipts.append(row)
                    if not all(checks.values()):
                        differences.append({**row, "error": result.get("error")})
    return dict(
        method_id="ziwei_coherent_age_audit_v1",
        declared_after_implementation=True,
        reused_frozen_birth_inputs=len(manifest["cases"]),
        new_independent_calendar_observations=0,
        profile_clock_receipts_checked=len(receipts),
        receipts=receipts,
        differences=differences,
        coherent_age_regression_passed=not differences,
        classical_age_boundary_verified=False,
        full_calendar_acceptance_passed=False,
        live_model_blind_evaluation="not_run",
        selected_source_pages_checked=3,
        selected_source_passages_checked=len(collation["citations"]),
        source_scope_independent_reviewers=collation["independent_reviewers"],
    )
