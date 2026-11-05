"""Offline, source-bound calendar and sky-coordinate audit; no efficacy score.

References are frozen HKO texts and NASA/JPL responses. Production output never
supplies the expected values. This report is deliberately narrower than a
historical-calendar, full-classical-text or real-world prediction acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

SOURCE_PATHS = [
    "src/fatebridge/data/sukuyo_comparative_time_units.json",
    "scripts/sukuyo/check_sukuyo_time_units.py",
    "tests/sukuyo/test_sukuyo_time_origin.py",
    "tests/data/sukuyo-comparative-time-primary.json",
    "src/fatebridge/core/sukuyo_printed_special.py",
    "src/fatebridge/data/sukuyo_wakita_special_days.json",
    "scripts/sukuyo/check_sukuyo_printed_special.py",
    "tests/sukuyo/test_sukuyo_printed_special.py",
    "tests/data/sukuyo-wakita-special-primary.json",
    "tests/sukuyo/test_sukuyo_sky_snapshot.py",
    "src/fatebridge/data/sukuyo_wakita_weekday.json",
    "src/fatebridge/data/sukuyo_t30107_calibration.json",
    "scripts/sukuyo/check_sukuyo_wakita_primary.py",
    "tests/sukuyo/test_sukuyo_wakita_primary.py",
    "tests/data/sukuyo-wakita-weekday-primary.json",
    "tests/data/sukuyo-calibration-precision-primary.json",
    "src/fatebridge/data/sukuyo_t30107_recalculation.json",
    "scripts/sukuyo/check_sukuyo_weekday_recalculation.py",
    "tests/sukuyo/test_sukuyo_weekday_recalculation.py",
    "tests/data/sukuyo-weekday-recalculation-primary.json",
    "src/fatebridge/core/sukuyo_weekday.py",
    "src/fatebridge/data/sukuyo_t30107_weekday_arithmetic.json",
    "scripts/sukuyo/check_sukuyo_weekday_arithmetic.py",
    "tests/sukuyo/test_sukuyo_weekday_arithmetic.py",
    "tests/data/sukuyo-weekday-arithmetic-primary.json",
    "src/fatebridge/core/sukuyo_clothing.py",
    "src/fatebridge/data/sukuyo_t1299_clothing.json",
    "scripts/sukuyo/audit_sukuyo_clothing_primary.py",
    "tests/sukuyo/test_sukuyo_clothing.py",
    "tests/data/sukuyo-clothing-primary.json",
    "scripts/sukuyo/check_sukuyo_historical_weekday.py",
    "tests/data/sukuyo-historical-weekday-primary.json",
    "scripts/sukuyo/check_sukuyo_documentary_dates.py",
    "tests/data/sukuyo-documentary-dates.json",
    "tests/sukuyo/test_sukuyo_day_cycle.py",
    "src/fatebridge/core/sukuyo_taibai.py",
    "src/fatebridge/data/sukuyo_t1299_taibai.json",
    "tests/sukuyo/test_sukuyo_taibai.py",
    "tests/data/sukuyo-taibai-primary.json",
    "scripts/sukuyo/audit_sukuyo_taibai_primary.py",
    "src/fatebridge/core/sukuyo_historical_calendar.py",
    "src/fatebridge/validation/sukuyo_historical_sources.py",
    "src/fatebridge/data/sukuyo_japanese_historical_v1.json",
    "scripts/sukuyo/build_sukuyo_historical_calendar.py",
    "scripts/sukuyo/fetch_sukuyo_historical_calendars.py",
    "scripts/sukuyo/check_sukuyo_historical_daily.py",
    "tests/sukuyo/test_sukuyo_historical_calendar.py",
    "tests/sukuyo/test_sukuyo_historical_sources.py",
    "tests/data/sukuyo-historical-edge-probes.json",
    "tests/data/sukuyo_historical_calendar_v1/captures.zip",
    "tests/data/sukuyo_historical_calendar_v1/manifest.json",
    "tests/data/sukuyo_historical_daily_controls_v1/captures.zip",
    "tests/data/sukuyo_historical_daily_controls_v1/manifest.json",
    "uv.lock",
    "pyproject.toml",
    "src/fatebridge/core/sukuyo.py",
    "src/fatebridge/core/sukuyo_calendar_basis.py",
    "src/fatebridge/core/sukuyo_japanese_calendar.py",
    "src/fatebridge/core/sukuyo_date_support.py",
    "src/fatebridge/core/sukuyo_profiles.py",
    "src/fatebridge/core/sukuyo_hinoo_critical.py",
    "src/fatebridge/data/sukuyo_t2465_critical.json",
    "scripts/sukuyo/check_sukuyo_hinoo_critical.py",
    "tests/sukuyo/test_sukuyo_hinoo_critical.py",
    "tests/sukuyo/test_sukuyo_boundary_receipts.py",
    "tests/data/sukuyo-t2465-kyoto-primary.json",
    "src/fatebridge/core/sukuyo_lower.py",
    "src/fatebridge/core/sukuyo_lower_methods.py",
    "src/fatebridge/core/sukuyo_padas.py",
    "src/fatebridge/core/sukuyo_sources.py",
    "src/fatebridge/core/sukuyo_activities.py",
    "src/fatebridge/core/sukuyo_calendar_text.py",
    "src/fatebridge/core/sukuyo_directions.py",
    "src/fatebridge/core/sukuyo_special_days.py",
    "src/fatebridge/core/sukuyo_sanjiu_days.py",
    "src/fatebridge/core/sukuyo_six_palaces.py",
    "src/fatebridge/core/suzhan_astronomy.py",
    "src/fatebridge/core/guolao.py",
    "src/fatebridge/core/fixed_star_paths.py",
    "src/fatebridge/core/astro/time_scales.py",
    "src/fatebridge/core/astro/birth.py",
    "src/fatebridge/core/ephemeris_runtime.py",
    "src/fatebridge/core/output_reference.py",
    "src/fatebridge/core/requests/divination.py",
    "src/fatebridge/core/requests/compatibility.py",
    "src/fatebridge/services/divination.py",
    "src/fatebridge/core/response_models.py",
    "src/fatebridge/core/local_techniques/suzhan.py",
    "src/fatebridge/validation/sukuyo_study.py",
    "src/fatebridge/validation/sukuyo.py",
    "src/fatebridge/validation/sukuyo_calendar_sources.py",
    "src/fatebridge/validation/claims.py",
    "src/fatebridge/data/agent_examples.json",
    "src/fatebridge/data/sukuyo_calendar_corrections.json",
    "src/fatebridge/data/sukuyo_japanese_daily_v1.json",
    "src/fatebridge/data/sukuyo_t1299_activities.json",
    "src/fatebridge/data/sukuyo_t1299_days.json",
    "src/fatebridge/data/sukuyo_t1299_travel_directions.json",
    "src/fatebridge/data/sukuyo_t1299_special_days.json",
    "src/fatebridge/data/sukuyo_t1299_sanjiu_days.json",
    "src/fatebridge/data/sukuyo_t1299_six_palaces.json",
    "src/fatebridge/data/sukuyo_t1299_calendar_profiles.json",
    "src/fatebridge/data/sukuyo_t1299_lower_mansions.json",
    "src/fatebridge/data/sukuyo_t1299_lower_methods.json",
    "src/fatebridge/data/sukuyo_t1299_palace_padas.json",
    "src/fatebridge/data/guolao/sefstars.txt",
    "src/fatebridge/data/guolao/sources.json",
    "tests/data/sukuyo_hko_v1/official_texts.zip",
    "tests/data/sukuyo_hutime_v1/captures.zip",
    "tests/data/sukuyo_hutime_v1/manifest.json",
    "tests/data/sukuyo_hutime_daily_v1/captures.zip",
    "tests/data/sukuyo_hutime_daily_v1/manifest.json",
    "tests/data/sukuyo-equatorial-horizons.json",
    "tests/data/sukuyo-activity-primary-excerpts.json",
    "tests/data/sukuyo-t1299-calendar-primary.json",
    "tests/data/sukuyo-fullmoon-primary.json",
    "tests/data/sukuyo-lower-primary.json",
    "tests/data/sukuyo-palace-pada-primary.json",
    "tests/data/sukuyo-rule-scope-primary.json",
    "tests/data/sukuyo-lower-methods-primary.json",
    "tests/data/sukuyo-time-gloss-primary.json",
    "tests/data/sukuyo-directions-primary.json",
    "tests/data/sukuyo-special-days-primary.json",
    "tests/data/sukuyo-hinoo-primary-cache.json",
    "tests/data/sukuyo-t2465-downloaded-primary.json",
    "tests/data/sukuyo-six-palaces-primary.json",
    "tests/data/sukuyo-sanjiu-days-primary.json",
    "tests/data/sukuyo-action-scope-primary.json",
    "tests/data/sukuyo-t1299-reference.json",
    "tests/sukuyo/test_sukuyo_profiles.py",
    "tests/sukuyo/test_sukuyo_lower.py",
    "tests/sukuyo/test_sukuyo_padas.py",
    "tests/sukuyo/test_sukuyo_rule_scope.py",
    "tests/sukuyo/test_sukuyo_lower_methods.py",
    "tests/sukuyo/test_sukuyo_transports.py",
    "tests/sukuyo/test_sukuyo_date_support.py",
    "tests/data/sukuyo_date_support_v1/reference.json",
    "tests/data/sukuyo_date_support_v1/northamerica-excerpts.txt",
    "tests/data/sukuyo_date_support_v1/asia-excerpts.txt",
    "tests/data/sukuyo_date_support_v1/australasia-excerpts.txt",
    "tests/data/sukuyo_date_support_v1/europe-excerpts.txt",
    "tests/sukuyo/test_sukuyo_calendar_text.py",
    "tests/sukuyo/test_sukuyo_time_gloss.py",
    "tests/sukuyo/test_sukuyo_directions.py",
    "tests/sukuyo/test_sukuyo_special_days.py",
    "tests/sukuyo/test_sukuyo_source_capture.py",
    "tests/sukuyo/test_sukuyo_six_palaces.py",
    "tests/sukuyo/test_sukuyo_t2465_primary.py",
    "tests/sukuyo/test_sukuyo_sanjiu_days.py",
    "tests/sukuyo/test_contract_regressions_2.py",
    "tests/sukuyo/test_sukuyo_japanese_sources.py",
    "tests/sukuyo/test_sukuyo_japanese_calendar.py",
    "tests/sukuyo/test_sukuyo_action_scope.py",
    "scripts/sukuyo/audit_sukuyo.py",
    "scripts/sukuyo/audit_sukuyo_t2465_primary.py",
    "scripts/sukuyo/fetch_sukuyo_reference.py",
    "scripts/sukuyo/audit_sukuyo_japanese_candidate.py",
    "scripts/sukuyo/freeze_sukuyo_japanese_candidate.py",
    "scripts/sukuyo/build_sukuyo_japanese_calendar.py",
    "scripts/sukuyo/check_sukuyo_wheel.py",
    "skills/_shared/sukuyo-evidence.md",
    "skills/_shared/fatebridge-engine.md",
    "skills/onda-xingpan/SKILL.md",
    "skills/onda-zhanbu/SKILL.md",
    "skills/onda-renji/SKILL.md",
]


def sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def audit() -> dict:
    # CLI runs in a fresh process. Record bytes before importing domain code,
    # so a concurrent edit cannot silently give old loaded code new file hashes.
    before = {p: sha(p) for p in SOURCE_PATHS}
    fresh_domain_import = not any(
        n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
    )
    from fatebridge.core import ephemeris_runtime
    from fatebridge.core.astro.birth import build_astro_birth_info
    from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
    from fatebridge.core.sukuyo_activities import source_bundle
    from fatebridge.core.sukuyo_calendar_text import (
        calendar_day_evidence,
        month_table_variant,
    )
    from fatebridge.core.sukuyo_calendar_text import source_bundle as day_source_bundle
    from fatebridge.core.sukuyo_date_support import local_date_support
    from fatebridge.core.sukuyo_directions import (
        source_bundle as direction_source_bundle,
    )
    from fatebridge.core.sukuyo_lower import source_bundle as lower_source_bundle
    from fatebridge.core.sukuyo_lower_methods import (
        source_bundle as method_source_bundle,
    )
    from fatebridge.core.sukuyo_padas import palace_reference, reference_cell
    from fatebridge.core.sukuyo_padas import source_bundle as pada_source_bundle
    from fatebridge.core.sukuyo_profiles import SOURCE as profile_source_path
    from fatebridge.core.sukuyo_profiles import fullmoon_calculation
    from fatebridge.core.sukuyo_profiles import source_bundle as profile_source_bundle
    from fatebridge.core.sukuyo_sanjiu_days import personal_day_witnesses
    from fatebridge.core.sukuyo_sanjiu_days import source_bundle as sanjiu_source_bundle
    from fatebridge.core.sukuyo_sources import load_source
    from fatebridge.core.sukuyo_special_days import (
        source_bundle as special_source_bundle,
    )
    from fatebridge.core.sukuyo_special_days import special_day_evidence
    from fatebridge.core.suzhan_astronomy import build_equatorial_mansions
    from fatebridge.services.divination import calculate_sukuyo_compatibility
    from fatebridge.validation.sukuyo_calendar_sources import audit_candidate
    from scripts.sukuyo.build_sukuyo_japanese_calendar import (
        normalize as normalize_japanese,
    )
    from scripts.sukuyo.build_sukuyo_japanese_calendar import (
        read_fixture as read_japanese_fixture,
    )
    from scripts.sukuyo.check_sukuyo_clock_position import verify_clock_position
    from scripts.sukuyo.check_sukuyo_documentary_primary import (
        verify_documentary_primary,
    )
    from scripts.sukuyo.check_sukuyo_guchureki_clock import verify_guchureki_clock
    from scripts.sukuyo.check_sukuyo_printed_special import verify_printed_special
    from scripts.sukuyo.check_sukuyo_time_units import verify_time_primary
    from scripts.sukuyo.fetch_sukuyo_reference import published_rows, read_sources

    official = read_sources()
    manifest = json.loads((ROOT / "tests/data/sukuyo_hko_v1/manifest.json").read_text())
    for source in manifest["sources"]:
        if hashlib.sha256(official[source["file"]]).hexdigest() != source["sha256"]:
            raise ValueError("Frozen HKO source hash mismatch")
    calendar_errors = []
    calendar_rows = published_rows(official)
    for civil, year, month, day, leap in calendar_rows:
        actual = calendar_mansion(civil)
        if [
            actual[k]
            for k in ("lunar_year", "lunar_month", "lunar_day", "is_leap_month")
        ] != [year, month, day, leap]:
            calendar_errors.append(civil)

    fixture = json.loads(
        (ROOT / "tests/data/sukuyo-equatorial-horizons.json").read_text()
    )
    outputs = {}
    errors = []
    # Audit the shipped, file-free Moshier fallback, not a local SE1 installation.
    with (
        patch.object(
            ephemeris_runtime, "_configured_path", "/tmp/fatebridge-sukuyo-audit-no-se1"
        ),
        patch.dict("os.environ", {"SE_EPHE_PATH": ""}),
    ):
        for ref in fixture["references"]:
            if (
                hashlib.sha256(ref["response"]["result"].encode()).hexdigest()
                != ref["response_sha256"]
            ):
                raise ValueError("Frozen JPL source hash mismatch")
            for row in ref["rows"]:
                utc = row["utc"]
                when = datetime.fromisoformat(utc)
                if utc not in outputs:
                    outputs[utc] = build_equatorial_mansions(
                        build_astro_birth_info(
                            birth_year=when.year,
                            birth_month=when.month,
                            birth_day=when.day,
                            birth_hour=when.hour,
                            birth_minute=when.minute,
                            birth_second=when.second,
                            birth_timezone="UTC",
                            birth_latitude=0,
                            birth_longitude=0,
                        )
                    )
                actual = next(
                    p for p in outputs[utc]["bodies"] if p["id"] == ref["body"]
                )
                ra = (
                    abs(
                        (actual["right_ascension"] - row["right_ascension"] + 180) % 360
                        - 180
                    )
                    * 3600
                )
                dec = abs(actual["declination"] - row["declination"]) * 3600
                errors.append(
                    {
                        "body": ref["body"],
                        "utc": utc,
                        "ra_arcseconds": ra,
                        "dec_arcseconds": dec,
                    }
                )
    worst = max(errors, key=lambda r: max(r["ra_arcseconds"], r["dec_arcseconds"]))
    conflict = day_evidence(calendar_mansion("2025-03-04"), "奎", "marriage")[
        "activity_assessment"
    ]
    primary_cases = json.loads(
        (ROOT / "tests/data/sukuyo-activity-primary-excerpts.json").read_text()
    )["cases"]
    calendar_primary = json.loads(
        (ROOT / "tests/data/sukuyo-t1299-calendar-primary.json").read_text()
    )
    source_cell_errors = []
    checked_cells = 0
    for day, row in enumerate(calendar_primary["printed_month_table"], 1):
        expected = row["text"].split("日", 1)[1].strip()
        for month, literal in enumerate(expected, 1):
            actual = month_table_variant(month, day, "室")
            if (
                actual["literal_mansion"] != literal
                or actual["locator"] != row["locator"]
            ):
                source_cell_errors.append([month, day])
            checked_cells += 1
    fullmoon_primary = json.loads(
        (ROOT / "tests/data/sukuyo-fullmoon-primary.json").read_text()
    )
    naoj = json.loads((ROOT / "tests/data/sukuyo-t1299-reference.json").read_text())
    aliases = str.maketrans("虛婁畢參張軫", "虚娄毕参张轸")
    fullmoon_errors = []
    for month in range(1, 13):
        start = SU27_ORDER.index(naoj["naoj_month_starts"][month - 1])
        for day in range(1, 31):
            result = fullmoon_calculation(month, day, SU27_ORDER)
            expected = SU27_ORDER[(start + day - 1) % 27]
            if (
                result["direct_mansion"] != expected
                or result["shortcut_mansion"] != expected
            ):
                fullmoon_errors.append([month, day])
    primary_example_errors = []
    for case in fullmoon_primary["examples"]:
        result = fullmoon_calculation(case["month"], case["day"], SU27_ORDER)
        expected = case["mansion"].translate(aliases)
        if (
            result["direct_mansion"] != expected
            or result["shortcut_mansion"] != expected
        ):
            primary_example_errors.append(case)
    hinoo_results = []
    hinoo_errors = []
    for civil, part, expected_status, expected_candidates, expected_mansion in [
        ("2024-08-04", None, "partial", ["星", "张"], None),
        ("2024-08-04", "first_half", "computed", [], "星"),
        ("2024-08-04", "second_half", "computed", [], "张"),
        ("2024-03-10", None, "computed", [], "奎"),
        ("1903-06-25", "first_half", "partial", ["鬼", "参"], None),
        ("1903-06-25", "second_half", "computed", [], "参"),
        ("1957-09-24", "first_half", "partial", ["角", "轸"], None),
    ]:
        result = calendar_mansion(
            civil, calendar_profile="hinoo_t1299_host27", calendar_day_part=part
        )
        values = [result["status"], result["candidate_su27s"], result["natal_su27"]]
        if values != [expected_status, expected_candidates, expected_mansion]:
            hinoo_errors.append([civil, part, values])
        hinoo_results.append(
            {
                "civil_date": civil,
                "textual_half": part,
                "status": values[0],
                "candidates": values[1],
                "natal_su27": values[2],
            }
        )
    candidate_pair = calculate_sukuyo_compatibility(
        person1_date="2024-08-04",
        person2_date="2024-08-04",
        calendar_profile="hinoo_t1299_host27",
        person2_calendar_day_part="second_half",
    )
    lower_primary = json.loads(
        (ROOT / "tests/data/sukuyo-lower-primary.json").read_text()
    )
    lower = lower_source_bundle()
    lower_refs = {r["mansion"]: r for r in lower_primary["paragraphs"]}
    lower_quote_errors = [
        r["rule_id"]
        for r in lower["rules"]
        if r["source_excerpt"] not in lower_refs[r["selectors"][0]]["text"]
    ]
    lower_examples = []
    lower_example_errors = []
    for name, activity, details, expected in [
        ("毕", "commerce", [], "conditional_only"),
        ("毕", "commerce", ["borrowing"], "caution"),
        ("毕", "commerce", ["sale"], "conditional_only"),
        ("壁", "travel", [], "conditional_only"),
        ("壁", "travel", ["southbound_journey"], "caution"),
        ("危", "commerce", [], "conditional_only"),
        ("危", "commerce", ["spending_property"], "caution"),
        ("危", "commerce", ["sale", "spending_property"], "conflicted"),
        ("女", "study", ["skill_learning"], "conditional_only"),
        ("氐", "study", [], "uncovered"),
        ("星", "relocation", [], "uncovered"),
    ]:
        result = day_evidence(
            {
                "natal_su27": name,
                "calendar_date": "2025-03-04",
                "calendar_timezone": "UTC+08:00",
                "lunar_day": 5,
            },
            activity=activity,
            activity_details=details,
        )
        state = next(
            r
            for r in result["activity_assessment"]["layers"]
            if r["layer"] == "lower_mansion"
        )["status"]
        if state != expected:
            lower_example_errors.append([name, activity, details, state, expected])
        lower_examples.append(
            {
                "mansion": name,
                "activity": activity,
                "declared_details": details,
                "lower_layer_state": state,
            }
        )
    pada_primary = json.loads(
        (ROOT / "tests/data/sukuyo-palace-pada-primary.json").read_text()
    )
    pada_bundle = pada_source_bundle()
    pada_errors = []
    pada_count = 0
    for name, ordinals in pada_primary["expected_palace_ordinals"].items():
        for foot, ordinal in enumerate(ordinals, 1):
            actual = reference_cell(name, foot)
            if actual["palace_ordinal"] != ordinal:
                pada_errors.append([name, foot, ordinal, actual["palace_ordinal"]])
            pada_count += 1
    if [p["literal_name"] for p in pada_bundle["palaces"]] != pada_primary[
        "source_names"
    ]:
        pada_errors.append("literal_palace_names")
    if [p["ruler_luminary"] for p in pada_bundle["palaces"]] != pada_primary[
        "source_lords"
    ]:
        pada_errors.append("source_luminary_lords")
    pada_partial = palace_reference(
        calendar_mansion("2024-08-04", calendar_profile="hinoo_t1299_host27")
    )
    pada_incomplete = palace_reference(calendar_mansion("2025-07-25"))
    if (
        pada_partial["selected_palace"]["name"] != "师子宫"
        or pada_incomplete["selected_palace"] is not None
    ):
        pada_errors.append("candidate_completeness_handling")
    scope_primary = json.loads(
        (ROOT / "tests/data/sukuyo-rule-scope-primary.json").read_text()
    )
    rules = [
        *source_bundle()["rules"],
        *day_source_bundle()["activity_rules"],
        *lower["rules"],
        *method_source_bundle()["rules"],
    ]
    passages = {r["rule_id"]: r for r in scope_primary["rule_passages"]}
    method_primary = json.loads(
        (ROOT / "tests/data/sukuyo-lower-methods-primary.json").read_text()
    )
    passages.update({r["rule_id"]: r for r in method_primary["rule_passages"]})
    quote_errors = []
    for rule in rules:
        ref = passages.get(rule["rule_id"])
        if (
            ref is None
            or ref["locator"] != rule["locator"]
            or any(q not in ref["text"] for q in rule.get("source_excerpts", []))
            or not rule.get("source_excerpts")
        ):
            quote_errors.append(rule["rule_id"])
    scope_errors = []
    scope_examples = []
    for civil, activity, details, rule_id, expected in [
        ("2025-03-05", "travel", [], "t1299_named_day_05", True),
        ("2025-03-05", "travel", [], "t1299_named_day_15", False),
        ("2025-03-01", "travel", [], "t1299_named_day_13", False),
        ("2025-03-13", "travel", ["journey_abroad"], "t1299_lower_mansion_18", False),
        (
            "2025-03-13",
            "travel",
            ["long_distance_journey"],
            "t1299_lower_mansion_18",
            False,
        ),
        (
            "2025-03-13",
            "travel",
            ["journey_abroad", "long_distance_journey"],
            "t1299_lower_mansion_18",
            True,
        ),
        ("2025-03-13", "study", ["learning_with_teacher"], "t1299_activity_18", True),
        ("2025-03-11", "commerce", ["borrowing"], "t1299_named_day_20", False),
        ("2025-03-11", "commerce", ["borrowing"], "t1299_named_day_21", True),
        ("2025-03-04", "commerce", ["collecting_debt"], "t1299_activity_29", True),
        ("2025-03-05", "commerce", ["borrowing"], "t1299_activity_31", True),
        ("2025-03-04", "marriage", [], "t1299_lower_method_weekday_06", True),
        (
            "2025-03-04",
            "commerce",
            ["collecting_debt"],
            "t1299_lower_method_weekday_08",
            True,
        ),
        ("2025-03-13", "commerce", ["purchase"], "t1299_lower_method_nature_06", False),
        ("2025-03-13", "commerce", ["sale"], "t1299_lower_method_nature_06", True),
        (
            "2025-03-04",
            "commerce",
            ["purchase_precious_goods"],
            "t1299_lower_method_weekday_05",
            True,
        ),
        (
            "2025-03-03",
            "commerce",
            ["purchase_precious_goods"],
            "t1299_activity_21",
            True,
        ),
        (
            "2025-03-14",
            "commerce",
            ["repaying_debt"],
            "t1299_lower_method_nature_05",
            True,
        ),
        (
            "2025-03-14",
            "commerce",
            ["returning_property"],
            "t1299_lower_method_nature_05",
            False,
        ),
        (
            "2025-03-07",
            "travel",
            ["long_distance_journey"],
            "t1299_lower_method_nature_10",
            False,
        ),
        (
            "2025-03-07",
            "travel",
            ["water_journey"],
            "t1299_lower_method_nature_10",
            True,
        ),
        ("2025-03-08", "travel", [], "t1299_lower_method_weekday_15", False),
        (
            "2025-03-08",
            "travel",
            ["long_distance_journey"],
            "t1299_lower_method_weekday_15",
            True,
        ),
    ]:
        value = day_evidence(
            calendar_mansion(civil), activity=activity, activity_details=details
        )["activity_assessment"]
        matched = rule_id in {r["rule_id"] for r in value["matched_rules"]}
        if matched != expected:
            scope_errors.append([civil, rule_id, matched, expected])
        scope_examples.append(
            {
                "civil_date": civil,
                "activity": activity,
                "details": details,
                "rule_id": rule_id,
                "matched": matched,
            }
        )
    method_errors = []
    nature_passages = {
        p["locator"]: p["text"] for p in method_primary["nature_passages"]
    }
    for group in method_source_bundle()["nature_groups"]:
        literal = nature_passages[group["locator"]].split("。此", 1)[0]
        literal = (
            literal.rsplit("。", 1)[-1]
            if group["name"] == "轻"
            else literal.split("，", 1)[1]
        )
        members = list(
            literal.replace("、", "").translate(
                str.maketrans("畢參軫張虛婁", "毕参轸张虚娄")
            )
        )
        if members != group["members"]:
            method_errors.append(["members", group["name"], members, group["members"]])
    weekday_passages = {
        p["locator"]: p["text"] for p in method_primary["weekday_passages"]
    }
    for weekday in method_source_bundle()["weekday_records"]:
        if weekday["literal_title"] not in weekday_passages[weekday["locator"]]:
            method_errors.append(["weekday_title", weekday["luminary"]])
    examples = json.loads(
        (ROOT / "src/fatebridge/data/agent_examples.json").read_text()
    )
    scoped_examples = {
        kind: {
            tool: examples[kind][tool] for tool in ("sukuyo_compatibility", "suzhan")
        }
        for kind in ("tools", "suggested_fields", "call_guidance", "evidence_views")
    }
    import pytz

    support_reference = json.loads(
        (ROOT / "tests/data/sukuyo_date_support_v1/reference.json").read_text()
    )
    for ref in support_reference["sources"]:
        path = ROOT / "tests/data/sukuyo_date_support_v1" / ref["excerpt_file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != ref["excerpt_sha256"]:
            raise ValueError("Frozen IANA excerpt hash mismatch")

    def zone_hashes():
        out = {}
        for zone in sorted(
            {
                r["zone"]
                for r in support_reference["cases"]
                + support_reference["nonexistent_dates"]
                if "/" in r["zone"]
            }
        ):
            with pytz.open_resource(zone) as resource:
                out[zone] = hashlib.sha256(resource.read()).hexdigest()
        return out

    zone_before = zone_hashes()
    support_errors = []
    support_examples = []
    for ref in support_reference["cases"]:
        actual = local_date_support(ref["local_date"], ref["zone"])
        rows = actual["utc_support_intervals"]
        expected_seconds = (
            datetime.fromisoformat(ref["end_utc_exclusive"])
            - datetime.fromisoformat(ref["start_utc_inclusive"])
        ).total_seconds()
        if (
            actual["possible_calendar_dates"] != ref["calendar_dates"]
            or rows[0]["start_utc_inclusive"] != ref["start_utc_inclusive"]
            or rows[-1]["end_utc_exclusive"] != ref["end_utc_exclusive"]
            or actual["civil_support_seconds"] != expected_seconds
            or any(
                a["end_utc_exclusive"] != b["start_utc_inclusive"]
                for a, b in zip(rows, rows[1:])
            )
        ):
            support_errors.append([ref["local_date"], ref["zone"]])
        support_examples.append(actual)
    for ref in support_reference["nonexistent_dates"]:
        try:
            local_date_support(ref["local_date"], ref["zone"])
        except ValueError as error:
            if "日期" not in str(error) or "不存在" not in str(error):
                support_errors.append(["unexpected_error", ref["zone"], str(error)])
        else:
            support_errors.append(["skipped_date_accepted", ref["zone"]])
    uncertain_pair = calculate_sukuyo_compatibility(
        person1_date="2025-01-29", person1_zone="UTC", person2_date="2025-03-04"
    )
    rows = uncertain_pair["candidate_relation_analysis"]["rows"]
    if uncertain_pair["pair"] is not None or [
        (r["person1_su27"], r["pair"]) for r in rows
    ] != [("室", "安壊"), ("壁", "危成")]:
        support_errors.append("timezone_candidate_relations")
    zone_after = zone_hashes()
    zone_changed = [z for z in zone_before if zone_before[z] != zone_after[z]]
    if zone_changed:
        support_errors.append(["timezone_files_changed", zone_changed])
    gloss_primary = json.loads(
        (ROOT / "tests/data/sukuyo-time-gloss-primary.json").read_text()
    )
    gloss_bundle = day_source_bundle()
    gloss_errors = []
    gloss_note = gloss_bundle["verse_abbreviation_resolution"]
    if (
        gloss_note["source_excerpt"] != gloss_primary["inline_note"]["text"]
        or gloss_note["locator"] != gloss_primary["inline_note"]["locator"]
        or gloss_note["literal_lunar_day"] != 1
        or gloss_note["interpreted_lunar_day"] != 11
    ):
        gloss_errors.append("source_inline_gloss")
    gloss_refs = {r["witness"]: r for r in gloss_primary["passages"]}
    for witness in gloss_bundle["timing_witnesses"]:
        ref = gloss_refs[witness["witness"]]
        if (
            witness["locator"] != ref["locator"]
            or witness["source_excerpt"] not in ref["text"]
            or witness["release_locator"] != ref["release_locator"]
            or witness["release_excerpt"] != ref["release_text"]
        ):
            gloss_errors.append(witness["witness"])
    for day in range(1, 31):
        evidence = calendar_day_evidence(day)
        generic = [
            r for r in evidence["time_restrictions"] if r["witness"] in gloss_refs
        ]
        expected_phase = (
            "night"
            if day in gloss_primary["expected_effective_night_days"]
            else (
                "daylight"
                if day in gloss_primary["expected_effective_daylight_days"]
                else None
            )
        )
        if (
            set(r["phase"] for r in generic)
            != ({expected_phase} if expected_phase else set())
            or set(r["witness"] for r in generic)
            != (set(gloss_refs) if expected_phase else set())
            or evidence["prose_verse_time_semantic_conflict"]
        ):
            gloss_errors.append(["effective_day_witnesses", day])
    direction_primary = json.loads(
        (ROOT / "tests/data/sukuyo-directions-primary.json").read_text()
    )
    direction_bundle = direction_source_bundle()
    direction_errors = []
    direction_text = "".join(p["text"] for p in direction_primary["paragraphs"])
    direction_apparatus = {r["id"]: r["text"] for r in direction_primary["apparatus"]}
    for rule in direction_bundle["rules"]:
        if any(e not in direction_text for e in rule["source_excerpts"]):
            direction_errors.append(["source_quote", rule["rule_id"]])
        for variant in rule["textual_variants"]:
            if (
                variant["literal"] != direction_apparatus[variant["apparatus_id"]]
                or variant["applied_to_selected_text"]
            ):
                direction_errors.append(["apparatus", rule["rule_id"]])
    for mansion in SU27_ORDER:
        for direction in ("north", "east", "south", "west"):
            evidence = day_evidence(
                {
                    "natal_su27": mansion,
                    "calendar_date": "2025-03-13",
                    "calendar_timezone": "UTC+08:00",
                    "lunar_day": 14,
                },
                activity="travel",
                activity_details=[direction + "bound_journey"],
            )
            actual = {
                r["assessment"]
                for r in evidence["activity_assessment"]["matched_rules"]
                if r["layer"] == "travel_direction"
            }
            expected = set()
            if mansion in direction_primary["main_text_positive"][direction]:
                expected.add("favorable")
            if mansion in direction_primary["main_text_negative"][direction]:
                expected.add("caution")
            if actual != expected:
                direction_errors.append(["direction_cell", mansion, direction])
    wall_south = day_evidence(
        {
            "natal_su27": "壁",
            "calendar_date": "2025-01-30",
            "calendar_timezone": "UTC+08:00",
            "lunar_day": 2,
        },
        activity="travel",
        activity_details=["southbound_journey"],
    )["activity_assessment"]
    if wall_south["evidence_status"] != "conflicted":
        direction_errors.append("wall_south_opposite_clauses")
    special_primary = json.loads(
        (ROOT / "tests/data/sukuyo-special-days-primary.json").read_text()
    )
    special_bundle = special_source_bundle()
    special_errors = []
    special_apparatus = {r["id"]: r["text"] for r in special_primary["apparatus"]}
    for rule in special_bundle["activity_rules"]:
        label = "甘露" if rule["selectors"] == ["甘露"] else "罗刹"
        passage = next(
            p
            for p in special_primary["paragraphs"]
            if p["volume"] == rule["volume"] and p["label"] == label
        )
        if any(excerpt not in passage["text"] for excerpt in rule["source_excerpts"]):
            special_errors.append(["activity_source_quote", rule["rule_id"]])
    for witness in special_bundle["witnesses"]:
        for row in witness["rows"]:
            original_literal = special_primary["expected_main_tables"][
                witness["volume"]
            ][row["label"]][row["source_main_weekday_index"]]
            if original_literal != row["source_main_literal"]:
                special_errors.append(
                    [
                        "source_weekday_attribution",
                        witness["id"],
                        row["label"],
                        row["weekday_index"],
                    ]
                )
            passage = next(
                p
                for p in special_primary["paragraphs"]
                if p["volume"] == witness["volume"] and p["label"] == row["label"]
            )
            if (
                row["source_clause"] not in passage["text"]
                or row["locator"] != passage["locator"]
            ):
                special_errors.append(
                    ["source_slot", witness["id"], row["label"], row["weekday_index"]]
                )
            for app in row["apparatus"]:
                if app["literal"] != special_apparatus[app["id"]]:
                    special_errors.append(
                        ["source_apparatus", witness["id"], app["id"]]
                    )
    for mansion in SU27_ORDER:
        for weekday in range(7):
            evidence = special_day_evidence(
                mansion, weekday, weekday_basis="modern_utc_plus08_civil_midnight"
            )
            for witness in [evidence["primary"], *evidence["comparisons"]]:
                tables = (
                    special_primary["expected_main_tables"]
                    if witness["edition"] == "taisho"
                    else special_primary["expected_ming_tables"]
                )
                table = tables[witness["volume"]]
                expected = [
                    label
                    for label, sequence in table.items()
                    if sequence[weekday].translate(aliases) == mansion
                ]
                unresolved = any(
                    sequence[weekday].translate(aliases) not in SU27_ORDER
                    for sequence in table.values()
                )
                if (
                    witness["matched_labels"] != expected
                    or witness["labels_complete_for_selected_day"] == unresolved
                ):
                    special_errors.append(
                        ["witness_cell", mansion, weekday, witness["witness"]]
                    )
    special_boundary_receipts = []
    for basis, civil in [
        ("chinese_hko_utc08", "2000-01-01"),
        ("japanese_hutime_1002_1_utc09", "2000-01-01"),
        ("japanese_naoj_historical_utc09", "0820-03-22"),
    ]:
        for clock, zone in [("00:30:00", "+09:00"), (None, "+00:00")]:
            context = calendar_mansion(civil, clock, zone, calendar_basis=basis)
            evidence = day_evidence(context)
            branches = evidence.get("candidate_days") or [evidence]
            rows = []
            for branch in branches:
                expected_basis = (
                    "modern_utc_plus09_civil_midnight"
                    if branch["calendar"]["calendar_timezone"] == "UTC+09:00"
                    else "modern_utc_plus08_civil_midnight"
                )
                special = branch["special_day_evidence"]
                row = {
                    "calendar_date": branch["calendar"]["calendar_date"],
                    "calendar_timezone": branch["calendar"]["calendar_timezone"],
                    "weekday_basis": branch["weekday"]["basis"],
                    "special_day_weekday_basis": special["weekday_basis"],
                    "special_day_scope": special["scope"],
                    "lower_weekday_basis": branch["lower_methods"]["weekday"]["basis"],
                    "weekday_index": branch["weekday"]["index_sunday_zero"],
                    "special_weekday_index": special["weekday_index"],
                    "classical_daybreak_accepted": special[
                        "classical_daybreak_boundary_acceptance"
                    ],
                }
                if (
                    {
                        row["weekday_basis"],
                        row["special_day_weekday_basis"],
                        row["lower_weekday_basis"],
                    }
                    != {expected_basis}
                    or row["weekday_index"] != row["special_weekday_index"]
                    or (
                        "现代UTC+09历日"
                        if expected_basis == "modern_utc_plus09_civil_midnight"
                        else "现代UTC+08历日"
                    )
                    not in row["special_day_scope"]
                    or row["classical_daybreak_accepted"]
                ):
                    special_errors.append(["weekday_boundary_receipt", basis, row])
                rows.append(row)
            special_boundary_receipts.append(
                {
                    "calendar_basis": basis,
                    "input_date": civil,
                    "input_time": clock,
                    "input_zone": zone,
                    "rows": rows,
                }
            )
    learning_rule_ids = {
        "t1299_special_upper_ganlu_learning_v1",
        "t1299_special_lower_ganlu_learning_v1",
    }
    for details, expected_match in [
        ([], False),
        (["skill_learning"], False),
        (["religious_learning"], True),
    ]:
        result = day_evidence(
            calendar_mansion("2025-04-15"), activity="study", activity_details=details
        )
        matched_ids = {
            r["rule_id"] for r in result["activity_assessment"]["matched_rules"]
        }
        if bool(learning_rule_ids <= matched_ids) != expected_match or (
            not expected_match and learning_rule_ids.intersection(matched_ids)
        ):
            special_errors.append(["religious_scope", details])
    capture_errors = []
    exposed_profile = profile_source_bundle()
    original_anchor = exposed_profile["fullmoon_anchors"][0]["fullmoon_mansion"]
    exposed_profile["fullmoon_anchors"][0]["fullmoon_mansion"] = "角"
    try:
        for month, expected_anchor in enumerate(fullmoon_primary["anchors"], 1):
            value = fullmoon_calculation(month, 15, SU27_ORDER)
            if value["direct_mansion"] != expected_anchor.translate(aliases) or value[
                "shortcut_mansion"
            ] != expected_anchor.translate(aliases):
                capture_errors.append(
                    ["returned_anchor_contaminated_later_call", month]
                )
    finally:
        exposed_profile["fullmoon_anchors"][0]["fullmoon_mansion"] = original_anchor
    profile_record = load_source(profile_source_path)
    direct_copy = profile_record.data
    direct_copy["fullmoon_anchors"][0]["fullmoon_mansion"] = "角"
    if (
        profile_record.data["fullmoon_anchors"][0]["fullmoon_mansion"]
        != fullmoon_primary["anchors"][0]
    ):
        capture_errors.append("loaded_source_data_alias")
    hinoo_cached_primary = json.loads(
        (ROOT / "tests/data/sukuyo-hinoo-primary-cache.json").read_text()
    )
    production_cached_primary = profile_source_bundle()["hinoo_addendum"][
        "cached_primary_excerpt"
    ]
    if (
        production_cached_primary != hinoo_cached_primary
        or production_cached_primary["complete_original_source_bytes_sha256"]
        is not None
        or production_cached_primary["facsimile_collation_complete"]
    ):
        capture_errors.append("hinoo_primary_excerpt_scope")
    for window in hinoo_cached_primary["windows"]:
        if (
            hashlib.sha256(window["text"].encode()).hexdigest()
            != window["normalized_excerpt_utf8_sha256"]
        ):
            capture_errors.append(["hinoo_normalized_excerpt_hash", window["locator"]])
    split_capture = calendar_mansion(
        "2024-08-04", calendar_profile="hinoo_t1299_host27"
    )["profile_calculation"]
    capture_coupled = (
        split_capture["source_bundle_sha256"]
        == split_capture["host_calculation"]["source_bundle_sha256"]
        == split_capture["short_month_assignment"]["omitted_day_calculation"][
            "source_bundle_sha256"
        ]
        == profile_record.sha256
    )
    if not capture_coupled:
        capture_errors.append("profile_branch_fingerprints_not_coupled")
    sanjiu_primary = json.loads(
        (ROOT / "tests/data/sukuyo-sanjiu-days-primary.json").read_text()
    )
    sanjiu_paragraphs = {p["id"]: p["text"] for p in sanjiu_primary["paragraphs"]}
    sanjiu_errors = []
    for label in sanjiu_primary["expected_relations"]:
        evidence = personal_day_witnesses(label)
        for row in [*evidence["witnesses"], evidence["priority_clause"]]:
            if not all(
                q in sanjiu_paragraphs[row["primary_paragraph_id"]]
                for q in row["source_excerpts"]
            ):
                sanjiu_errors.append([label, row["locator"]])
    sanjiu_bundle = sanjiu_source_bundle()
    for rule in sanjiu_bundle["activity_rules"]:
        if not any(
            all(q in text for q in rule["source_excerpts"])
            for text in sanjiu_paragraphs.values()
        ):
            sanjiu_errors.append(rule["rule_id"])
    sanjiu_examples = []
    for natal, topic, details, expected_ids in [
        ("奎", "travel", [], []),
        (
            "奎",
            "travel",
            ["long_distance_journey"],
            ["t1299_activity_03", "t1299_activity_12"],
        ),
        ("奎", "travel", ["personal_departure"], ["t1299_sanjiu_lower_18"]),
        (
            "娄",
            "travel",
            ["long_distance_traveler_entering_residence"],
            ["t1299_sanjiu_lower_16"],
        ),
        ("娄", "relocation", [], ["t1299_activity_04", "t1299_sanjiu_lower_15"]),
        ("昴", "study", [], []),
        ("昴", "study", ["religious_learning"], []),
        ("昴", "study", ["monastic_dharma_request"], ["t1299_sanjiu_lower_17"]),
    ]:
        actual_day = day_evidence(calendar_mansion("2025-03-04"), natal, topic, details)
        assessment = actual_day["activity_assessment"]
        actual_ids = sorted(
            r["rule_id"] for r in assessment["matched_rules"] if r["layer"] == "sanjiu"
        )
        if actual_ids != sorted(expected_ids):
            sanjiu_errors.append([natal, topic, details, actual_ids])
        sanjiu_examples.append(
            {
                "natal": natal,
                "activity": topic,
                "details": details,
                "matched_personal_rule_ids": actual_ids,
                "conditional_personal_rule_ids": sorted(
                    r["rule_id"]
                    for r in assessment["conditional_rules"]
                    if r["layer"] == "sanjiu"
                ),
            }
        )
    action_primary = json.loads(
        (ROOT / "tests/data/sukuyo-action-scope-primary.json").read_text()
    )
    action_errors = []
    action_examples = []
    for civil, topic, details, expected_weekday_ids in [
        ("2025-03-03", "social", [], []),
        (
            "2025-03-03",
            "social",
            ["social_gathering"],
            ["t1299_lower_method_weekday_04"],
        ),
        (
            "2025-03-03",
            "social",
            ["forming_friendship"],
            ["t1299_activity_22", "t1299_lower_method_weekday_03"],
        ),
        ("2025-03-03", "travel", ["personal_departure"], []),
        (
            "2025-03-03",
            "travel",
            ["private_journey"],
            ["t1299_lower_method_weekday_03"],
        ),
        ("2025-03-02", "travel", ["long_distance_journey"], ["t1299_activity_20"]),
        (
            "2025-03-02",
            "travel",
            ["long_distance_journey", "diplomatic_mission"],
            ["t1299_activity_20"],
        ),
        (
            "2025-03-02",
            "travel",
            ["long_distance_journey", "royal_or_official_traveler"],
            ["t1299_activity_20", "t1299_lower_method_weekday_01"],
        ),
    ]:
        selected = day_evidence(
            calendar_mansion(civil), activity=topic, activity_details=details
        )
        assessed = selected["activity_assessment"]
        actual = sorted(
            r["rule_id"]
            for r in assessed["matched_rules"]
            if r["layer"] in {"weekday", "lower_weekday"}
        )
        if actual != sorted(expected_weekday_ids):
            action_errors.append([civil, topic, details, actual])
        for row in assessed["matched_rules"]:
            if (
                row.get("applicability_status") == "matched_declared_activity_detail"
                and row["topic_condition"] not in selected["reading_text"]
            ):
                action_errors.append(
                    ["condition_missing_from_native_reading", row["rule_id"]]
                )
        action_examples.append(
            {
                "date": civil,
                "activity": topic,
                "details": details,
                "matched_weekday_rule_ids": actual,
            }
        )
    lower_sun = next(
        r
        for r in method_source_bundle()["rules"]
        if r["rule_id"] == "t1299_lower_method_weekday_01"
    )
    lower_sun_text = next(
        p["text"] for p in action_primary["selected_primary"] if p["id"] == "lower_sun"
    )
    if (
        "王公百官等東西南北遠行" not in lower_sun_text
        or "王公百官等東西南北遠行" not in lower_sun["source_excerpts"]
    ):
        action_errors.append("lower_sun_actor_qualifier_not_preserved")
    japanese_files, japanese_manifest = read_japanese_fixture(
        ROOT / "tests/data/sukuyo_hutime_daily_v1"
    )
    japanese_bundle, japanese_admission = normalize_japanese(
        japanese_files, japanese_manifest
    )
    japanese_errors = []
    if japanese_bundle != json.loads(
        (ROOT / "src/fatebridge/data/sukuyo_japanese_daily_v1.json").read_bytes()
    ):
        japanese_errors.append(
            "production_reference_differs_from_frozen_daily_derivation"
        )
    japanese_count, index = 0, 0
    for batch in japanese_manifest["daily_batches"]:
        for row in json.loads(japanese_files[batch["response"]]):
            civil = date(1872, 2, 9) + timedelta(days=index)
            index += 1
            if row is None:
                continue
            actual = calendar_mansion(
                civil.isoformat(),
                zone="+09:00",
                calendar_basis="japanese_hutime_1002_1_utc09",
            )
            printed = f"{actual['lunar_year']}|{'閏' if actual['is_leap_month'] else ''}{actual['lunar_month']}|{actual['lunar_day']}"
            if (
                printed != row["text"]
                or actual["calendar_source"] != row["uri"]
                or actual["calendar_timezone"] != "UTC+09:00"
            ):
                japanese_errors.append(civil.isoformat())
            japanese_count += 1
    from fatebridge.core.sukuyo_historical_calendar import (
        lunar_fields as historical_fields,
    )
    from fatebridge.validation.sukuyo_historical_sources import (
        normalize as normalize_historical,
    )
    from scripts.sukuyo.build_sukuyo_historical_calendar import (
        read_fixture as read_historical_fixture,
    )
    from scripts.sukuyo.check_sukuyo_documentary_dates import (
        verify_documentary_controls,
    )
    from scripts.sukuyo.check_sukuyo_historical_daily import verify_daily_controls

    historical_files, historical_manifest = read_historical_fixture(
        ROOT / "tests/data/sukuyo_historical_calendar_v1"
    )
    historical_bundle, historical_admission = normalize_historical(
        historical_files, historical_manifest
    )
    historical_errors = []
    if historical_bundle != json.loads(
        (ROOT / "src/fatebridge/data/sukuyo_japanese_historical_v1.json").read_bytes()
    ):
        historical_errors.append(
            "production_reference_differs_from_frozen_raw_derivation"
        )
    historical_count, historical_pipeline_count = 0, 0
    for ordinal, year, month, leap, length in historical_bundle["months"]:
        start, end = max(1, ordinal), ordinal + length
        for current in range(start, end):
            expected = (year, month, current - ordinal + 1, leap)
            if historical_fields(date.fromordinal(current)) != expected:
                historical_errors.append(["kernel", current])
            historical_count += 1
        for current in sorted({start, end - 1}):
            expected = (year, month, current - ordinal + 1, leap)
            actual = calendar_mansion(
                date.fromordinal(current).isoformat(),
                zone="+09:00",
                calendar_basis="japanese_naoj_historical_utc09",
            )
            if (
                tuple(
                    actual[k]
                    for k in ("lunar_year", "lunar_month", "lunar_day", "is_leap_month")
                )
                != expected
            ):
                historical_errors.append(["public_calendar_month_boundary", current])
            if actual["calendar_backend"] != "frozen_naoj_historical_month_starts":
                historical_errors.append(["wrong_backend", current])
            historical_pipeline_count += 1
    historical_daily = verify_daily_controls()
    historical_documentary = verify_documentary_controls()
    from scripts.sukuyo.check_sukuyo_historical_weekday import verify_weekday

    historical_weekday = verify_weekday()
    from fatebridge.core.sukuyo_six_palaces import six_palace_reference
    from scripts.sukuyo.audit_sukuyo_t2465_primary import verify_primary

    hinoo_downloaded_primary = verify_primary()
    from scripts.sukuyo.check_sukuyo_hinoo_critical import (
        verify_primary as verify_hinoo_critical,
    )

    hinoo_critical_primary = verify_hinoo_critical()
    primary_edition = profile_source_bundle()["hinoo_addendum"][
        "downloaded_primary_edition"
    ]
    for key in (
        "publisher_html_response_sha256",
        "downloaded_calendar_windows",
        "calendar_apparatus",
        "calendar_window_sha256",
    ):
        if primary_edition[key] != hinoo_downloaded_primary[key]:
            capture_errors.append(["hinoo_downloaded_primary_differs", key])
    six_primary = json.loads(
        (ROOT / "tests/data/sukuyo-six-palaces-primary.json").read_bytes()
    )
    six_examples = []
    six_errors = []
    for example in six_primary["explicit_primary_examples"]:
        reference = six_palace_reference(example["natal_mansion"])
        actual = next(
            r for r in reference["members"] if r["name"] == example["position"]
        )
        if (actual["mansion"], actual["inclusive_ordinal"]) != (
            example["mansion"],
            example["inclusive_ordinal"],
        ):
            six_errors.append(example)
        six_examples.append({**example, "actual_mansion": actual["mansion"]})
    for natal in SU27_ORDER:
        reference = six_palace_reference(natal)
        if (
            reference["members"][0]["mansion"] != natal
            or len({r["mansion"] for r in reference["members"]}) != 6
            or reference["seven_luminary_transits_evaluated"]
            or reference["applied_to_day_assessment"]
            or reference["joint_reading_requirement"]["evaluated"]
        ):
            six_errors.append(["counting_or_scope", natal])
        if (
            reference["counting_excerpt"] not in six_primary["paragraph"]
            or reference["joint_reading_requirement"]["source_excerpt"]
            not in six_primary["paragraph"]
        ):
            six_errors.append(["primary_quote", natal])
    from fatebridge.core.sukuyo_taibai import taibai_direction_reference
    from scripts.sukuyo.audit_sukuyo_taibai_primary import (
        verify_primary as verify_taibai_primary,
    )

    taibai_primary = json.loads(
        (ROOT / "tests/data/sukuyo-taibai-primary.json").read_bytes()
    )
    taibai_errors = []
    taibai_source_check = verify_taibai_primary()
    from fatebridge.core.sukuyo_clothing import clothing_reference
    from scripts.sukuyo.audit_sukuyo_clothing_primary import (
        verify_primary as verify_clothing_primary,
    )

    clothing_source_check = verify_clothing_primary()
    clothing_errors = []
    clothing_rows = []
    for item in json.loads(
        (ROOT / "tests/data/sukuyo-clothing-primary.json").read_bytes()
    )["verse_rows"]:
        actual = clothing_reference({"natal_su27": item["mansion"]})
        if actual["candidate_references"][0]["verse"] != item:
            clothing_errors.append(item["mansion"])
        clothing_rows.append(
            {
                "mansion": item["mansion"],
                "primary_assessment": actual["primary_assessment"],
            }
        )
    for lunar_day, location, direction in taibai_primary["manual_day_locations"]:
        reference = taibai_direction_reference(lunar_day)
        if (reference["location"], reference["horizontal_direction"]) != (
            location,
            direction,
        ):
            taibai_errors.append(["printed_day_triple", lunar_day])
        ming = reference["witnesses"][1]
        if (ming["status"] == "row_deleted_in_apparatus") != (
            lunar_day in taibai_primary["ming_missing_days"]
        ):
            taibai_errors.append(["ming_deleted_row", lunar_day])
        if (
            reference["physical_venus_position_evaluated"]
            or reference["movement_alignment_evaluated"]
            or reference["applied_to_activity_assessment"]
        ):
            taibai_errors.append(["unestablished_claim", lunar_day])
    from scripts.sukuyo.check_sukuyo_wakita_primary import verify_printed_chapter
    from scripts.sukuyo.check_sukuyo_weekday_arithmetic import verify_arithmetic
    from scripts.sukuyo.check_sukuyo_weekday_recalculation import verify_recalculation

    result = {
        "format": "sukuyo_scoped_audit_v26",
        "selected_printed_weekday_chapter": verify_printed_chapter(),
        "selected_weekday_arithmetic": verify_arithmetic(),
        "selected_weekday_recalculation": verify_recalculation(),
        "clothing_witnesses": {
            "selected_primary_check": clothing_source_check,
            "all_27_mansion_references": clothing_rows,
            "mismatches": clothing_errors,
            "literal_forecasts_scored_or_used_as_real_world_predictions": False,
            "complete_classical_work_accepted": False,
        },
        "taibai_lunar_direction_reference": {
            "source_days_checked": 30,
            "printed_main_table_rows": 10,
            "ming_apparatus_reconstructed_rows": 9,
            "ming_missing_days_preserved": taibai_primary["ming_missing_days"],
            "source_verification": taibai_source_check,
            "mismatches": taibai_errors,
            "physical_venus_position_evaluated": False,
            "movement_alignment_definition_established": False,
            "independent_scholarly_semantic_acceptance": False,
            "scope": "Printed month-day triples and explicit apparatus only; no GPS bearing, physical Venus or travel permission inferred.",
        },
        "japanese_historical_reference_calendar": {
            "runtime_backend_enabled": True,
            "calendar_basis": "japanese_naoj_historical_utc09",
            "source_months": len(historical_bundle["months"]),
            "raw_source_derived_kernel_dates_checked": historical_count,
            "full_calendar_pipeline_month_boundary_dates_checked": historical_pipeline_count,
            "mismatches": historical_errors,
            "source_admission": historical_admission,
            "direct_daily_controls": historical_daily,
            "printed_documentary_controls": historical_documentary,
            "quoted_historical_weekday_control": historical_weekday,
            "cross_source_disagreement_days_retained": historical_admission[
                "cross_source_disagreement_dates"
            ],
            "all_cross_source_disagreements_resolved": False,
            "complete_provider_advertised_historical_range": False,
            "historical_local_clock_reconstruction": False,
            "full_historical_or_independent_calendar_acceptance": False,
            "scope": "Named NAOJ reference conformance for proleptic Gregorian AD 1..1872 under fixed UTC+09. Every declared raw month-start query is retained, including year-zero context, 210 HuTime differences and the two-day legal reform month. Early reconstructed chronology, published ancient calendars and historical local clocks remain unaccepted.",
        },
        "natal_six_palace_positions": {
            "ruleset_id": six_palace_reference(None)["ruleset_id"],
            "explicit_primary_examples": six_examples,
            "all_natal_mansions_checked": len(SU27_ORDER),
            "positions_per_natal_mansion": 6,
            "mismatches": six_errors,
            "physical_luminary_transits_evaluated": False,
            "joint_sanjiu_adjudication_evaluated": False,
            "independent_scholarly_acceptance": False,
            "scope": "Original inclusive counting only. No calendar-day six-harm period, physical transit, catastrophe or prediction acceptance is inferred.",
        },
        "japanese_reference_calendar": {
            "runtime_backend_enabled": True,
            "full_calendar_pipeline_days_checked": japanese_count,
            "mismatches": japanese_errors,
            "source_admission": japanese_admission,
            "full_historical_or_independent_calendar_acceptance": False,
            "scope": "Complete source conformance inside the named HuTime LOD domain. The longer methodology claim, historical local time, whole Jingu collation and whole-range independent validation remain unaccepted.",
        },
        "action_scope": {
            "qualified_social_clauses": 18,
            "counterexamples": action_examples,
            "mismatches": action_errors,
            "new_declared_facts": [
                "forming_friendship",
                "private_journey",
                "royal_or_official_traveler",
            ],
            "upper_moon_private_reading_silently_amended": False,
            "independent_scholarly_semantic_acceptance": False,
            "scope": "Selected actor, purpose and social-action corrections; counts are inventory, not classical coverage or prediction scores.",
        },
        "japanese_calendar_source_candidate": audit_candidate(
            ROOT / "tests/data/sukuyo_hutime_v1"
        ),
        "active_goal_axes": [
            "calendar_accuracy",
            "named_classical_source_fidelity",
            "interpretation_fidelity",
            "real_world_prediction",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pyswisseph": importlib.metadata.version("pyswisseph"),
            "lunardate": importlib.metadata.version("lunardate"),
        },
        "inputs_sha256": {p: sha(p) for p in SOURCE_PATHS},
        "calendar": {
            "source": "https://www.hko.gov.hk/en/gts/time/conversion.htm",
            "range": [calendar_rows[0][0], calendar_rows[-1][0]],
            "reference_days": len(calendar_rows),
            "mismatch_dates": calendar_errors,
            "published_corrections": manifest["correction_count"],
            "scope": "Frozen modern Chinese UTC+08 lunar dates; not Tang/Japanese historical calendars or future source revisions.",
        },
        "calendar_date_uncertainty": {
            "method_id": "complete_local_date_preimage_tzif_seconds_v1",
            "iana_reference_version": support_reference["iana_version"],
            "iana_interval_cases": len(support_examples),
            "whole_skipped_date_cases": len(support_reference["nonexistent_dates"]),
            "mismatches": support_errors,
            "examples": support_examples,
            "timezone_files_sha256": zone_before,
            "timezone_files_stable_across_cases": not zone_changed,
            "scope": "Complete date support under loaded rules, not a selected birth time, probability distribution, historical source daybreak calibration or future legislation guarantee.",
        },
        "physical_coordinates": {
            "source": fixture["source"],
            "reference_positions": len(errors),
            "fixed_tolerance_arcseconds": fixture["tolerance_arcseconds"],
            "maximum_observed_error_arcseconds": max(
                worst["ra_arcseconds"], worst["dec_arcseconds"]
            ),
            "worst_case": worst,
            "within_tolerance": all(
                max(e["ra_arcseconds"], e["dec_arcseconds"])
                <= fixture["tolerance_arcseconds"]
                for e in errors
            ),
            "ephemeris_models": outputs[next(iter(outputs))]["ephemeris_models"],
            "catalogue_input_receipts": [
                {
                    "utc": instant,
                    "catalogue_sha256": output["catalogue_sha256"],
                    "catalogue_sources_sha256": output["catalogue_sources_sha256"],
                }
                for instant, output in outputs.items()
            ],
            "catalogue_hashes_match_declared_audit_inputs": all(
                output["catalogue_sha256"]
                == before["src/fatebridge/data/guolao/sefstars.txt"]
                and output["catalogue_sources_sha256"]
                == before["src/fatebridge/data/guolao/sources.json"]
                for output in outputs.values()
            ),
            "scope": "Seven geocentric physical luminaries at six fixed instants; no claim about all epochs, ancient anchor choices or real-world prediction.",
        },
        "classical_activity": {
            "source": "https://cbetaonline.dila.edu.tw/zh-tw/T1299",
            "curated_rules": len(source_bundle()["rules"]),
            "additional_named_day_rules": len(day_source_bundle()["activity_rules"]),
            "independent_primary_clause_cases": len(primary_cases),
            "danger_marriage_conflict_preserved": conflict["evidence_status"]
            == "conflicted",
            "scope": "Selected clauses and six nonharmful topics; not complete acceptance of T1299.",
            "legacy_curated_rules_with_primary_windows": len(passages),
            "selected_literal_quote_errors": quote_errors,
            "scope_predicate_examples": scope_examples,
            "scope_predicate_errors": scope_errors,
            "source_loading_policy": "Cached table data and fingerprint come from one byte read; returned source structures are copied before delivery.",
            "lower_method_clauses": len(method_source_bundle()["rules"]),
            "lower_method_groups": method_source_bundle()["nature_groups"],
            "lower_method_weekdays": method_source_bundle()["weekday_records"],
            "lower_method_table_errors": method_errors,
            "lower_named_source_entries": len(lower_refs),
            "lower_curated_clauses": len(lower["rules"]),
            "lower_conditional_clauses": sum(
                r["applicability"] == "activity_detail_required" for r in lower["rules"]
            ),
            "lower_literal_quote_errors": lower_quote_errors,
            "lower_applicability_examples": lower_examples,
            "lower_applicability_errors": lower_example_errors,
            "legacy_and_named_day_per_topic_qualifications": sum(
                len(r.get("activity_conditions", {}))
                for r in [
                    *source_bundle()["rules"],
                    *day_source_bundle()["activity_rules"],
                ]
            ),
            "independent_annotation_semantic_acceptance": False,
            "conjunction_group_counts": [
                len(g["members"]) for g in lower["conjunction_doctrine"]["groups"]
            ],
            "conjunction_scope": "Textual name classification only. Nine members are inferred from the remainder of the declared 27 order. No numerical angular shift, historical boundary or transit clock was validated.",
        },
        "sanjiu_day_witnesses": {
            "ruleset_id": sanjiu_bundle["id"],
            "relation_records": len(sanjiu_bundle["relation_witnesses"]),
            "primary_paragraphs": len(sanjiu_paragraphs),
            "additional_activity_rules": len(sanjiu_bundle["activity_rules"]),
            "mismatches": sanjiu_errors,
            "scope_examples": sanjiu_examples,
            "independent_scholarly_acceptance": False,
            "priority_clause_applied_to_aggregate": False,
            "scope": "Selected original personal-day witnesses; departure, long-distance travel and residence_entry require their own declared details. The priority passage does not silently discard conflicting layers.",
        },
        "source_capture": {
            "source_bundle_sha256": profile_record.sha256,
            "mutation_counterexample_months_checked": 12,
            "same_capture_for_host_and_omitted_day": capture_coupled,
            "mismatches": capture_errors,
            "cache_policy": "Detached public data; cached private parse and fingerprint share one byte read. One record supplies every branch inside select_profile. Not a security boundary against private-state edits.",
            "t2465_cached_primary_excerpt": hinoo_cached_primary,
            "t2465_direct_publisher_primary_quotations": hinoo_downloaded_primary,
            "t2465_selected_direct_manuscript_controls": hinoo_critical_primary,
            "t2465_manuscript_or_facsimile_collation_complete": False,
            "independent_scholarly_acceptance": False,
        },
        "special_day_witnesses": {
            "ruleset_id": special_bundle["id"],
            "source_sha256": special_bundle["source_sha256"],
            "primary_source_windows": len(special_primary["paragraphs"]),
            "source_witness_slots": sum(
                len(w["rows"]) for w in special_bundle["witnesses"]
            ),
            "mansion_weekday_witness_cells_checked": len(SU27_ORDER)
            * 7
            * len(special_bundle["witnesses"]),
            "additional_activity_clauses": len(special_bundle["activity_rules"]),
            "weekday_boundary_receipts": special_boundary_receipts,
            "mismatches": special_errors,
            "direct_printed_lower_reference": verify_printed_special(),
            "selected_primary": special_bundle["selected_primary"],
            "lower_unresolved_main_literals": ["冒", "底"],
            "ming_basis": "Same-source original apparatus reconstruction, not a separately collated print.",
            "independent_scholarly_acceptance": False,
            "physical_lunar_conjunction_evaluated": False,
            "scope": "Curated source tables and religious-learning applicability; no silent main-text normalization or physical lunar conjunction inference. Pending source readings remain conditional evidence.",
        },
        "travel_directions": {
            "ruleset_id": direction_bundle["id"],
            "source_sha256": direction_bundle["source_sha256"],
            "source_paragraphs": len(direction_primary["paragraphs"]),
            "selected_rules": len(direction_bundle["rules"]),
            "named_day_direction_cells_checked": len(SU27_ORDER) * 4,
            "mismatches": direction_errors,
            "wall_south_opposite_clauses_preserved": wall_south["evidence_status"]
            == "conflicted",
            "unparsed_literal_selectors": ["互"],
            "selected_text": direction_bundle["selected_text"],
            "physical_palace_or_bearing_inferred": False,
            "independent_scholarly_acceptance": False,
            "scope": "All sixteen selected chapter rows with original apparatus; named-day lookup only, explicit cardinal direction required. Curated clause semantics and historical clock/day boundaries still need independent review.",
        },
        "classical_calendar": {
            "selected_default_method": "t1299_lower_fullmoon27_v1",
            "independent_naoj_month_day_cases": 360,
            "fullmoon_mismatches": fullmoon_errors,
            "literal_source_examples": len(fullmoon_primary["examples"]),
            "literal_source_example_errors": primary_example_errors,
            "hinoo_modern_host_application_cases": hinoo_results,
            "hinoo_errors": hinoo_errors,
            "hinoo_scope": "Explicit research addendum on the selected host calendar; half interpretation follows Kotyk 2022. Direct SAT publisher HTML has a separate fingerprint, selected quotations and apparatus; the offline audit does not recheck the private full response. Intercalary precedence alternatives are modern reconstructions. No manuscript/facsimile collation or complete historical-calendar acceptance.",
            "printed_cells_checked": checked_cells,
            "mismatches": source_cell_errors,
            "additional_primary_clause_cases": len(calendar_primary["clauses"]),
            "named_lunar_days_generated": len(
                [calendar_day_evidence(d) for d in range(1, 31)]
            ),
            "prose_verse_literal_variant_days": [
                d
                for d in range(1, 31)
                if calendar_day_evidence(d)["prose_verse_time_variant"]
            ],
            "prose_verse_semantic_conflict_days": [
                d
                for d in range(1, 31)
                if calendar_day_evidence(d)["prose_verse_time_semantic_conflict"]
            ],
            "inline_abbreviation_resolution": gloss_note,
            "generic_timing_witnesses": len(gloss_bundle["timing_witnesses"]),
            "effective_timing_entries": sum(
                len(w["entries"]) for w in gloss_bundle["timing_witnesses"]
            ),
            "timing_gloss_errors": gloss_errors,
            "clock_evaluation": "not_computed_requires_declared_historical_day_and_solar_boundary_policy",
            "individual_named_day_time_witnesses": len(
                day_source_bundle()["individual_time_witnesses"]
            ),
            "clock_doctrine": day_source_bundle()["clock_doctrine"],
            "comparative_time_source_check": verify_time_primary(),
            "documentary_source_check": verify_documentary_primary(),
            "clock_position_source_check": verify_clock_position(),
            "guchureki_clock_source_check": verify_guchureki_clock(),
            "scope": "Literal table checks and source-located named-day clauses; complete T1299 acceptance is unproven.",
        },
        "palace_pada_reference": {
            "source_url": pada_bundle["source_url"],
            "source_sha256": pada_bundle["source_sha256"],
            "primary_allocation_clauses": len(pada_primary["clauses"]),
            "manually_annotated_cells_checked": pada_count,
            "mismatches": pada_errors,
            "pada_numbering_basis": pada_bundle["pada_numbering_basis"],
            "pada_ordinals_explicit_in_source": False,
            "birth_pada_established": False,
            "physical_longitude_origin_validated": False,
            "independent_scholarly_acceptance": False,
            "complete_calendar_candidates_same_palace_example": pada_partial,
            "incomplete_calendar_candidates_example": pada_incomplete,
            "scope": "Full 108-cell source-table lookup under a declared ordinal-foot expansion; not physical birth-foot calculation, historical zero-longitude calibration, local houses or modern zodiac inference.",
        },
        "interpretation": {
            "native_reading": "deterministic_result_bound_text_with_all_matched_activity_clauses",
            "context_quotes": "same_run_complete_context_required_not_isolated_favorable_clauses",
            "independent_free_text_semantic_acceptance": False,
            "conditional_relation_example": {
                "status": candidate_pair["status"],
                "primary_pair": candidate_pair["pair"],
                "candidate_relation_analysis": candidate_pair[
                    "candidate_relation_analysis"
                ],
            },
            "sukuyo_suzhan_example_sections_sha256": hashlib.sha256(
                json.dumps(
                    scoped_examples,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
        },
        "real_world_validation": {
            "real_world_sample_count": 0,
            "sample_count_basis": "User confirmed no real samples in this task; no outcome data are loaded by this audit.",
            "status": "prospective_workflow_prepared_not_registered",
            "performance_metrics": None,
            "part_of_active_goal": True,
        },
        "three_axis_complete": False,
        "four_axis_complete": False,
        "authority_certified": False,
        "unresolved": [
            "Tang/Japanese historical calendars; source collation and intercalary/short-month precedence",
            "Historical anchor identification, epoch and coordinate uncertainty near mansion boundaries",
            "Independent semantic assessment of real model explanations",
            "Real-world prospective outcome data, independent adjudication and replication; no real samples are currently available",
            "Complete relevant classical techniques, including historical textual-half clock mapping, physical birth-foot and palace determination, physical interpretation of conjunction groups and native planetary-hour conventions",
            "Independent scholarly review of topic mapping; unattributed 0396a15-16 paragraph and unresolved 呈學 reading",
        ],
    }

    after = {p: sha(p) for p in SOURCE_PATHS}
    changed = [p for p in SOURCE_PATHS if before[p] != after[p]]
    result["audit_input_stability"] = {
        "method": "hash_all_declared_inputs_before_domain_imports_and_after_audit",
        "fresh_domain_import": fresh_domain_import,
        "changed_inputs": changed,
        "all_declared_inputs_stable_across_run": not changed,
        "coherent_fresh_import_window": fresh_domain_import and not changed,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "calendar_mismatches": len(result["calendar"]["mismatch_dates"]),
                "retained_calibration_precision_discrepancies": result[
                    "selected_printed_weekday_chapter"
                ]["calibration_precision"]["selected_precision_discrepancies"],
                "jpl_positions": result["physical_coordinates"]["reference_positions"],
                "maximum_error_arcseconds": result["physical_coordinates"][
                    "maximum_observed_error_arcseconds"
                ],
                "real_samples": 0,
                "japanese_candidate_import_eligible": result[
                    "japanese_calendar_source_candidate"
                ]["structural_import_eligible"],
                "japanese_reference_pipeline_days": result[
                    "japanese_reference_calendar"
                ]["full_calendar_pipeline_days_checked"],
                "fresh_domain_import": result["audit_input_stability"][
                    "fresh_domain_import"
                ],
                "audit_inputs_changed": result["audit_input_stability"][
                    "changed_inputs"
                ],
            }
        )
    )
    if (
        not result["audit_input_stability"]["coherent_fresh_import_window"]
        or result["calendar"]["mismatch_dates"]
        or not result["physical_coordinates"]["within_tolerance"]
        or not result["physical_coordinates"][
            "catalogue_hashes_match_declared_audit_inputs"
        ]
        or not result["classical_activity"]["danger_marriage_conflict_preserved"]
        or result["classical_calendar"]["mismatches"]
        or result["classical_calendar"]["fullmoon_mismatches"]
        or result["classical_calendar"]["literal_source_example_errors"]
        or result["classical_calendar"]["hinoo_errors"]
        or result["classical_activity"]["lower_literal_quote_errors"]
        or result["classical_activity"]["lower_applicability_errors"]
        or result["palace_pada_reference"]["mismatches"]
        or result["classical_activity"]["selected_literal_quote_errors"]
        or result["classical_activity"]["scope_predicate_errors"]
        or result["classical_activity"]["lower_method_table_errors"]
        or result["calendar_date_uncertainty"]["mismatches"]
        or result["classical_calendar"]["timing_gloss_errors"]
        or result["travel_directions"]["mismatches"]
        or result["classical_calendar"]["comparative_time_source_check"]["errors"]
        or result["classical_calendar"]["documentary_source_check"]["errors"]
        or result["classical_calendar"]["clock_position_source_check"]["errors"]
        or result["classical_calendar"]["guchureki_clock_source_check"]["errors"]
        or result["special_day_witnesses"]["mismatches"]
        or result["special_day_witnesses"]["direct_printed_lower_reference"]["errors"]
        or result["source_capture"]["mismatches"]
        or result["sanjiu_day_witnesses"]["mismatches"]
        or result["action_scope"]["mismatches"]
        or result["japanese_reference_calendar"]["mismatches"]
        or result["natal_six_palace_positions"]["mismatches"]
        or result["taibai_lunar_direction_reference"]["mismatches"]
        or result["clothing_witnesses"]["mismatches"]
        or result["selected_weekday_arithmetic"]["printed_prefix_errors"]
        or result["selected_weekday_arithmetic"]["rational_algebra_errors"]
        or result["selected_weekday_recalculation"]["errors"]
        or result["selected_printed_weekday_chapter"][
            "implementation_or_selected_source_errors"
        ]
        or result["japanese_historical_reference_calendar"][
            "quoted_historical_weekday_control"
        ]["mismatches"]
        or result["japanese_historical_reference_calendar"]["mismatches"]
        or not result["japanese_historical_reference_calendar"]["source_admission"][
            "naoj_reference_import_eligible"
        ]
        or result["japanese_historical_reference_calendar"]["direct_daily_controls"][
            "naoj_calculation_to_daily_source_mismatches"
        ]
        or result["japanese_historical_reference_calendar"]["direct_daily_controls"][
            "naoj_daily_printed_ganzhi_mismatches"
        ]
        or result["japanese_historical_reference_calendar"][
            "printed_documentary_controls"
        ]["mismatches"]
        or result["japanese_historical_reference_calendar"]["direct_daily_controls"][
            "hutime_daily_to_retained_variant_mismatches"
        ]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
