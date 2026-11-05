"""Same-calculation natal evidence joins; not a new placement or calendar oracle."""

import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_horoscope
from fatebridge.services.metaphysics import _build_analysis_seed, _build_person_seed
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.civil_clock import utc_instant
from fatebridge.utils.timezones import parse_timezone_name

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/data/ziwei_independent"


def audit_natal_prerequisites(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest_path = fixtures / "clock_manifest.json"
    cases = json.loads(manifest_path.read_text())["cases"]
    differences = []
    checks = births = 0
    for case in cases:
        person = create_person_info(**case["input"])
        seed = _build_person_seed(person)
        birth = utc_instant(localize_datetime(seed.input_datetime, seed.timezone))
        for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
            for sihua in ("rule_profile", "naj_ming_v1"):
                chart = build_ziwei_chart(
                    seed,
                    person.gender or "未知",
                    rule_profile=profile,
                    sihua_source=sihua,
                )
                expected: dict[str, Any] = {
                    "schema_version": "ziwei_horoscope_natal_prerequisites_v1",
                    "origin": "same_calculation_internal_natal_chart",
                    "ruleset": {
                        k: deepcopy(v)
                        for k, v in chart["ruleset"].items()
                        if k in {"id", "version", "sihua_source"}
                    },
                    **{
                        k: deepcopy(chart[k])
                        for k in (
                            "lunar_date",
                            "year_stem",
                            "hour_branch",
                            "ming_gong",
                            "shen_gong",
                            "wuxing_ju",
                        )
                    },
                    "rule_trace": [],
                    "separate_birth_run": False,
                    "classical_birth_year_boundary_verified": False,
                }
                for name in (
                    "lunar_month_for_placement",
                    "ming_shen_month_hour",
                    "wuhu_dun_nayin_ju",
                ):
                    rows = [r for r in chart["rule_trace"] if r["rule_id"] == name]
                    if len(rows) != 1:
                        raise ValueError(
                            "Natal source chart does not contain a unique prerequisite step"
                        )
                    expected["rule_trace"].append(deepcopy(rows[0]))
                before = deepcopy(chart)
                for minutes in (0, 65):
                    for zone in ("UTC", "+14:00", "-12:00"):
                        target = (birth + timedelta(minutes=minutes)).astimezone(
                            parse_timezone_name(zone)
                        )
                        target_seed = _build_analysis_seed(
                            analysis_year=target.year,
                            analysis_month=target.month,
                            analysis_day=target.day,
                            analysis_hour=target.hour,
                            analysis_minute=target.minute,
                            analysis_timezone=zone,
                        )
                        h = build_ziwei_horoscope(
                            chart=chart,
                            gender=person.gender or "未知",
                            birth_seed=seed,
                            target_seed=target_seed,
                        )
                        actual = h.get("natal_prerequisites")
                        if json.dumps(
                            actual, sort_keys=True, ensure_ascii=False, allow_nan=False
                        ) != json.dumps(
                            expected,
                            sort_keys=True,
                            ensure_ascii=False,
                            allow_nan=False,
                        ):
                            differences.append(
                                dict(
                                    case=case["id"],
                                    profile=profile,
                                    sihua_source=sihua,
                                    minutes_after_birth=minutes,
                                    target_timezone=zone,
                                    kind="natal_prerequisite_receipt",
                                )
                            )
                        if chart != before:
                            differences.append(
                                dict(case=case["id"], kind="natal_chart_mutated")
                            )
                        checks += 1
                births += 1
    return dict(
        method_id="ziwei_horoscope_natal_prerequisite_joins_v1",
        declared_after_implementation=True,
        frozen_clock_manifest_sha256=hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        reused_frozen_birth_inputs=len(cases),
        profile_source_natal_charts=births,
        conditional_horoscope_receipts_checked=checks,
        differences=differences,
        new_independent_calendar_observations=0,
        new_classical_witnesses=0,
        upstream_natal_placement_independently_verified_by_this_audit=False,
        classical_birth_year_boundary_verified=False,
        live_model_blind_evaluation="not_run",
        full_acceptance_passed=False,
    )
