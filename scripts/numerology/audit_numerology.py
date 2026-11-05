"""Audit named classical examples and external term instants without scoring prediction.

Exit 0 means these finite calculation checks passed. --require-four-dimensions
also requires the entire acceptance target; unvalidated layers keep that gate
closed. This command never generates predictions or outcome labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import runpy
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fatebridge.core.almanac import get_day_ganzhi, get_solar_terms_for_year
from fatebridge.core.canping import calculate as canping
from fatebridge.core.canping import compute_number
from fatebridge.core.canping_texts import collation_summary as canping_collation_summary
from fatebridge.core.canping_texts import inherited_corpus as canping_inherited_corpus
from fatebridge.core.canping_texts import lookup_record as canping_lookup_record
from fatebridge.core.canping_timing import APPENDIX
from fatebridge.core.canping_timing import SOURCE_SHA256 as CANPING_SOURCE_SHA256
from fatebridge.core.canping_timing import SOURCE_URL as CANPING_SOURCE_URL
from fatebridge.core.canping_timing import appendix_age, luck_timeline
from fatebridge.core.heluo import (
    MONTH_GUA,
    _san_cai,
)
from fatebridge.core.heluo import calculate as heluo
from fatebridge.core.heluo import (
    da_yun,
    four_pillar_number_totals,
    gua_lines,
    hexagram_najia,
)
from fatebridge.core.heluo import judge as heluo_judge
from fatebridge.core.heluo import solar_term_huagong, transform_houtian, yao_text
from fatebridge.core.heluo_body import ELEMENTS, body_evidence, element_relation
from fatebridge.core.heluo_lines import line_conditions
from fatebridge.core.heluo_months import COLLATION_PATH as MONTH_COLLATION_PATH
from fatebridge.core.heluo_months import MONTH_BRANCHES, month_affinity
from fatebridge.core.heluo_najia import annotate_positions
from fatebridge.core.heluo_najia import collation_summary as najia_collation_summary
from fatebridge.core.heluo_poems import collation_summary as poem_collation_summary
from fatebridge.core.heluo_poems import poems_for_line
from fatebridge.core.heluo_seasonal import seasonal_number_evidence
from fatebridge.core.heluo_structure import body_structure
from fatebridge.core.heluo_texts import (
    COLLATION_PATH,
    collation_summary,
    commentary_collation_summary,
)
from fatebridge.core.heluo_timing import (
    SOURCE_SHA256,
    SOURCE_URL,
    annual_sequence,
    daily_template,
    monthly_sequence,
)
from fatebridge.core.heluo_yuantang import placement as yuantang_placement
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.numerology_inputs import require_birth_clock
from fatebridge.core.numerology_pillars import (
    pillar_link_evidence,
    require_pillar_links,
)
from fatebridge.core.requests.divination import CanpingRequest, HeluoRequest
from fatebridge.core.song_clock import (
    compare_branch_window_to_term,
    source_clock_from_fraction,
    source_term_clock,
)
from fatebridge.core.song_qi import source_qi_sequence, source_term_remainder
from fatebridge.utils.timezones import parse_timezone_name
from scripts.numerology.audit_canping_extended_projection import (
    audit as canping_extended_projection_checks,
)
from scripts.numerology.audit_canping_projection import (
    audit as canping_projection_checks,
)

ROOT = Path(__file__).resolve().parents[2]

# The repository audit reads sealed test references when run as a file or module.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE_HEADER_COUNT = 156
SOURCE_PENDING_COUNT = 228


def birth_timezone_checks() -> dict:
    root = ROOT / "tests/fixtures/numerology_timezone_v1"
    reference = json.loads((root / "reference.json").read_text())
    failures = []
    source = reference["iana_source"]
    if (
        hashlib.sha256((root / source["file"]).read_bytes()).hexdigest()
        != source["sha256"]
    ):
        failures.append({"kind": "civil_zone_reference_identity"})
    for row in reference["transition_instants"]:
        at = datetime.fromisoformat(row["utc"]).astimezone(
            parse_timezone_name("Asia/Shanghai")
        )
        if (
            at.isoformat() != row["local"]
            or int(at.dst().total_seconds()) != row["daylight_saving_seconds"]
        ):
            failures.append({"kind": "historical_civil_transition", "case": row["utc"]})
    for name, model, build in (
        ("heluo", HeluoRequest, build_heluo_result),
        ("canping", CanpingRequest, build_canping_result),
    ):
        base = dict(
            date="1990-06-15",
            time="09:30",
            gender="男",
            lon="120",
            use_true_solar_time=True,
        )
        public = build(**model(**base).model_dump())
        direct = build(**base)
        null = build(**base, zone=None)
        fixed = build(**base, zone="+08:00")
        for kind, result in (
            ("public", public),
            ("direct", direct),
            ("null", null),
            ("fixed", fixed),
        ):
            clock = result["numerology_evidence"]["birth_clock"]
            if (
                result["input_normalized"]["zone"] != "+08:00"
                or clock["birth_instant_utc"] != "1990-06-15T01:30:00+00:00"
                or result["four_pillars"] != fixed["four_pillars"]
                or result["four_pillars"]["hour"] != {"stem": "癸", "branch": "巳"}
            ):
                failures.append(
                    {
                        "kind": "numerology_default_zone",
                        "tool": name,
                        "input_kind": kind,
                    }
                )
        named = build(**base, zone="Asia/Shanghai")
        dst = build(**base, zone="+09:00")
        ca, cb = [r["numerology_evidence"]["birth_clock"] for r in (named, dst)]
        if (
            ca["birth_instant_utc"] != "1990-06-15T00:30:00+00:00"
            or ca["birth_instant_utc"] != cb["birth_instant_utc"]
            or ca["calculation_wall_clock"] != cb["calculation_wall_clock"]
            or named["four_pillars"] != dst["four_pillars"]
            or named["four_pillars"]["hour"] != {"stem": "壬", "branch": "辰"}
            or ca["civil_daylight_saving_seconds"] != 3600
            or cb["civil_daylight_saving_seconds"] != 0
        ):
            failures.append({"kind": "historical_zone_explicit_offset", "tool": name})
        for zone in (" ", "UTC+08:90"):
            try:
                build(**base, zone=zone)
            except ValueError:
                pass
            else:
                failures.append(
                    {"kind": "blank_invalid_zone_defaulted", "tool": name, "zone": zone}
                )
        for case in reference["invalid_regional_clocks"]:
            args = {
                **base,
                "date": case["date"],
                "time": case["time"],
                "zone": "Asia/Shanghai",
            }
            try:
                build(**args)
            except ValueError as exc:
                if case["error"] not in str(exc):
                    failures.append(
                        {"kind": "wrong_civil_clock_rejection", "tool": name}
                    )
            else:
                failures.append(
                    {"kind": "civil_gap_or_fold_guessed", "tool": name, "case": case}
                )
    return {
        "checks_passed": not failures,
        "failures": failures,
        "reference": "numerology_timezone_v1/reference.json",
        "government_notice_access": reference["government_notice"]["access"],
        "government_original_page_bytes_preserved": False,
        "historical_transition_rules": 2,
        "utc_local_boundary_probes": len(reference["transition_instants"]),
        "default_equivalence_tool_input_comparisons": 8,
        "named_vs_fixed_offset_same_instant_tool_comparisons": 2,
        "blank_invalid_zone_rejection_probes": 4,
        "regional_gap_fold_rejection_probes": 4,
        "new_independent_solar_instants": 0,
        "new_classical_worked_horoscopes": 0,
        "full_historical_timezone_domain_verified": False,
    }


def birth_clock_checks() -> dict:
    root = ROOT / "tests/fixtures"
    reference = json.loads((root / "numerology_clock_v1/reference.json").read_text())
    path = ROOT / "tests/data" / reference["jpl_fixture"]
    jpl = json.loads(path.read_text())
    failures = []
    errors = []
    if hashlib.sha256(path.read_bytes()).hexdigest() != reference["jpl_fixture_sha256"]:
        failures.append({"kind": "clock_jpl_reference_identity"})
    for name, build in (
        ("heluo", build_heluo_result),
        ("canping", build_canping_result),
    ):
        base = dict(
            date="2000-05-15", time="09:00:00", zone="Asia/Shanghai", gender="男"
        )
        try:
            build(**base, use_true_solar_time=True)
        except ValueError:
            pass
        else:
            failures.append({"kind": "default_place_for_solar_clock", "tool": name})
        civil = build(**base, use_true_solar_time=False)
        if (
            civil["analysis_context"]["longitude"] is not None
            or civil["numerology_evidence"]["birth_clock"]["longitude"] is not None
        ):
            failures.append({"kind": "fabricated_unused_coordinate", "tool": name})
        for row in jpl["rows"]:
            instant = datetime.fromisoformat(row["instant"])
            at = instant.astimezone(ZoneInfo("Asia/Shanghai"))
            for longitude in (0, 75):
                result = build(
                    date=at.strftime("%Y-%m-%d"),
                    time=at.strftime("%H:%M:%S"),
                    zone="Asia/Shanghai",
                    gender="男",
                    gps_lon=longitude,
                    use_true_solar_time=True,
                )
                clock = result["numerology_evidence"]["birth_clock"]
                expected = instant.replace(tzinfo=None) + timedelta(
                    minutes=4 * longitude + row["equation_of_time_minutes"]
                )
                error = abs(
                    (
                        datetime.fromisoformat(clock["calculation_wall_clock"])
                        - expected
                    ).total_seconds()
                )
                errors.append(error)
                if error > jpl["tolerance_seconds"]:
                    failures.append(
                        {
                            "kind": "clock_jpl_error",
                            "tool": name,
                            "instant": row["instant"],
                            "longitude": longitude,
                            "error_seconds": error,
                        }
                    )
                if (
                    clock["birth_instant_utc"] != row["instant"]
                    or clock["longitude_source"] != "gps_lon"
                    or clock["longitude"] != longitude
                ):
                    failures.append({"kind": "clock_input_provenance", "tool": name})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "reused_independent_jpl_instants": len(jpl["rows"]),
        "new_independent_instants": 0,
        "two_longitudes_two_tools_clock_comparisons": len(errors),
        "max_clock_error_seconds": max(errors),
        "tolerance_seconds": jpl["tolerance_seconds"],
        "missing_coordinate_rejection_probes": 2,
        "unprovided_civil_coordinate_null_probes": 2,
        "full_published_domain_verified": False,
        "new_classical_worked_horoscopes": 0,
    }


def heluo_solar_context_checks() -> dict:
    from fatebridge.core import almanac
    from fatebridge.core.local_techniques.heluo import build_heluo_result
    from fatebridge.core.solar_model_policy import DE440_SOFTWARE_YEARS

    fixture = ROOT / "tests/fixtures/heluo_solar_context_v1/reference.json"
    reference = json.loads(fixture.read_text())
    failures = []
    for name, digest in reference["reused_fixture_sha256"].items():
        if (
            hashlib.sha256((ROOT / "tests/fixtures" / name).read_bytes()).hexdigest()
            != digest
        ):
            failures.append(
                {"kind": "heluo_reused_solar_reference_identity", "file": name}
            )
    for probe in reference["civil_endpoint_probes"]:
        result = build_heluo_result(
            date=probe["date"],
            time=probe["time"],
            zone=probe["zone"],
            gender="男",
            use_true_solar_time=False,
        )
        solar = result["solar_term"]
        context = solar["boundary_context"]
        seasonal = result["judge"]["seasonal_numbers"]
        if (
            context["context_local_year"] != int(probe["date"][:4])
            or context["calendar_context_match"] is not True
            or solar["term"] != probe["term"]
            or solar["yang_ling"] is not probe["yang_ling"]
            or seasonal["context_local_year"] != context["context_local_year"]
            or seasonal["context_timezone"] != context["context_timezone"]
            or context["dependencies"][0]["record"]
            != result["calendar_context"]["current_solar_term"]
        ):
            failures.append(
                {
                    "kind": "heluo_solar_context_endpoint_or_shared_source",
                    "date": probe["date"],
                }
            )
    rows = json.loads(
        (ROOT / "tests/fixtures/ren_calendar_guard_v1/reference.json").read_text()
    )["rows"]
    expected = {(r["year"], r["index"]): r for r in rows}
    errors = []
    observed = set()
    for origin in (1800, 2200):
        window = almanac._term_window(
            datetime(origin, 6, 1, tzinfo=timezone.utc), "UTC"
        )
        for term in window:
            key = (term.moment.year, almanac.SOLAR_TERM_NAMES.index(term.name))
            detail = term.solar_model_details or {}
            if key in expected and "selected_crossing_jd_tt" in detail:
                error = (
                    abs(detail["selected_crossing_jd_tt"] - expected[key]["jd_tt"])
                    * 86400
                )
                errors.append(error)
                observed.add(key)
                if error > reference["root_tolerance_seconds"]:
                    failures.append(
                        {
                            "kind": "heluo_reused_TT_root",
                            "year": key[0],
                            "index": key[1],
                            "error_seconds": error,
                        }
                    )
    if errors and len(observed) != 96:
        failures.append(
            {"kind": "heluo_incomplete_selected_TT_cohort", "observed": len(observed)}
        )
    return {
        "checks_passed": not failures,
        "failures": failures,
        "civil_endpoint_context_probes": 4,
        "reused_TT_roots_available": 96,
        "TT_roots_compared_under_current_provider": len(observed),
        "TT_comparison_status": (
            "compared_all96"
            if errors
            else "not_evaluated_provider_has_no_TT_root_receipt"
        ),
        "max_TT_error_seconds": max(errors) if errors else None,
        "root_tolerance_seconds": reference["root_tolerance_seconds"],
        "new_TT_roots": 0,
        "new_observations": 0,
        "new_original_horoscopes": 0,
        "independent_second_review_completed": False,
        "published_model_input_years_extended": list(DE440_SOFTWARE_YEARS)
        != reference["endpoint_years"],
        "registered_public_de440_input_years": list(DE440_SOFTWARE_YEARS),
        "public_range_comparison_baseline": reference["endpoint_years"],
        "this_check_extends_public_year_grid": False,
        "full_published_domain_verified": False,
        "scope": "Local civil context, shared current-term binding and declared adjacent roots. Reused TT comparisons share DE440 lineage and do not independently validate historical or future UTC, source classical calendars or complete Canping future projections.",
    }


def yuanqi_opposition_checks() -> dict:
    from fatebridge.core.heluo import _san_cai, gua_lines, lines_to_gua
    from fatebridge.core.heluo_body import body_evidence
    from fatebridge.core.heluo_opposition import (
        CONTENT_SHA256,
        SOURCE_PATH,
        opposition_evidence,
    )

    root = ROOT / "tests/fixtures/heluo_yuanqi_opposition_v1"
    reference = json.loads((root / "verified-readings.json").read_text())
    failures = []
    data = json.loads(SOURCE_PATH.read_text())
    if data != reference["runtime_source"]:
        failures.append({"kind": "yuanqi_source_content_changed"})
    for image in reference["images"]:
        if (
            hashlib.sha256((root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append({"kind": "yuanqi_native_witness_identity"})
    mappings = {
        symbol: row
        for row in reference["runtime_source"]["mappings"]
        for symbol in row["symbols"]
    }
    for i, probe in enumerate(reference["hand_derived_probes"]):
        year = probe["year"]
        yuan = {
            kind: mappings[symbol]["yuan"] for kind, symbol in zip(("tian", "di"), year)
        }
        fan = {
            kind: mappings[symbol]["fan"] for kind, symbol in zip(("tian", "di"), year)
        }
        bits = gua_lines(probe["up"], probe["low"])
        gua = lines_to_gua(bits)["name"]
        bodies = body_evidence(
            year,
            {
                phase: {"gua": gua, "trigrams": _san_cai(bits)}
                for phase in ("xian", "hou")
            },
            yuan,
        )["bodies"]
        result = opposition_evidence(year, bodies, yuan, fan)
        for phase in result["phases"]:
            row = next(r for r in phase["conditions"] if r["kind"] == probe["kind"])
            prefix = phase["phase"] + "."
            if (
                row["yuan_body_ids"] != [prefix + k for k in probe["yuan_ids"]]
                or row["fan_body_ids"] != [prefix + k for k in probe["fan_ids"]]
                or row["condition_match"] is not probe["match"]
                or row["direct_only_condition_match"] is not probe["direct_match"]
                or row["rescue_match"] is not None
            ):
                failures.append(
                    {
                        "kind": "yuanqi_absence_premise_or_scope",
                        "probe": i,
                        "phase": phase["phase"],
                    }
                )
        if (
            result["full_rescue_assessment"] is not False
            or result["content_sha256"] != CONTENT_SHA256
        ):
            failures.append({"kind": "yuanqi_incomplete_rescue_or_source_identity"})
    for row in reference["page35_full_hexagram_diagram_context"]:
        transformed = (
            [1 - b for b in row["before_bits"]]
            if row["operation"] == "complement"
            else row["before_bits"][::-1]
        )
        if (
            transformed != row["after_bits"]
            or lines_to_gua(row["after_bits"])["name"] != row["after"]
        ):
            failures.append({"kind": "yuanqi_vs_whole_hexagram_context"})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "printed_target_groups": 8,
        "printed_qian_absence_example": 1,
        "hand_derived_body_scope_probes": 6,
        "reused_pdf_pages_native_witnesses": [32, 33, 34, 35],
        "whole_hexagram_diagram_context_pairs": 4,
        "new_original_horoscopes": 0,
        "new_calendar_instants": 0,
        "independent_second_review_completed": False,
        "full_rescue_assessment": False,
        "scope": "Per-phase born-year targets and missing-original premise under a named body scope; direct-only comparison is unselected. Opposite presence does not replace absence, and no rescue or outcome is certified.",
    }


def phase_qi_checks() -> dict:
    root = ROOT / "tests/fixtures/numerology_nlc_v1"
    reference = json.loads((root / "qi-reference.json").read_text())
    manifest = json.loads((root / "qi-manifest.json").read_text())
    worked = json.loads((root / "worked-reference.json").read_text())
    failures = []
    if manifest["source_pdf_sha256"] != SOURCE_SHA256:
        failures.append({"kind": "qi_source_identity"})
    for image in manifest["images"]:
        if (
            hashlib.sha256((root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append({"kind": "qi_witness_identity", "file": image["file"]})
    for row in reference["quarter_probes"]:
        for term in row["terms"]:
            for earth in (False, True):
                actual = solar_term_huagong(term, earth)
                if actual["hg"] != row["hg"] + (
                    ["坤", "艮"] if earth else []
                ) or actual["fh"] != row["fh"] + (["乾", "兌"] if earth else []):
                    failures.append(
                        {"kind": "literal_qi_window", "term": term, "earth": earth}
                    )
    for probe in reference["source_four_pillar_phase_probes"]:
        case = next(c for c in worked["cases"] if c["id"] == probe["case_id"])
        p = dict(zip(("year", "month", "day", "hour"), case["pillars"]))
        chart = heluo(
            four_pillars=p,
            gender=case["gender"],
            birth_year=case["computational_year"],
            hour_zhi=p["hour"][1],
            month_zhi=p["month"][1],
            month_yang_ling=case["yang_ling"],
        )
        qi = heluo_judge(
            chart, p, p["month"][1], solar_term_huagong(probe["term"], False)
        )["qi_phases"]
        for phase in qi["phases"]:
            actual = phase["matches"]["huagong"]
            for kind in ("direct", "nuclear"):
                if (
                    actual[kind + "_body_ids"]
                    != probe["huagong"][phase["phase"] + "_" + kind]
                ):
                    failures.append(
                        {
                            "kind": "qi_phase_position",
                            "case_id": case["id"],
                            "phase": phase["phase"],
                        }
                    )
        if (
            next(t for t in qi["transitions"] if t["kind"] == "huagong")["change"]
            != probe["huagong"]["change"]
        ):
            failures.append({"kind": "qi_phase_transition", "case_id": case["id"]})
    disagreements = []
    for claim in reference["literal_definition_disagreements"]:
        expected = solar_term_huagong(claim["source_stated_term"], False)["hg"]
        if expected != claim["definition_huagong_trigrams"]:
            failures.append({"kind": "qi_definition_changed_to_fit_conflict"})
        if claim["literal_huagong_trigram"] not in expected:
            disagreements.append(claim)
    if disagreements != reference["literal_definition_disagreements"]:
        failures.append({"kind": "qi_literal_disagreement_lost"})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "direct_fanhua_clauses": 4,
        "direct_seasonal_earth_clause": 1,
        "rule_derived_term_and_earth_probes": 48,
        "previously_recorded_four_pillar_phase_probes": 4,
        "new_original_worked_horoscopes": 0,
        "whole_page_witnesses_including_reused_pages": len(manifest["images"]),
        "all_examined_huagong_claims_agree": not disagreements,
        "literal_definition_disagreements": disagreements,
        "independent_second_review_completed": False,
        "complete_qi_assessment": False,
    }


def song_qi_source_checks() -> dict:
    """Two printed source algorithms, not two certified historical ephemerides."""
    root = ROOT / "tests/fixtures/song_qi_v1"
    reference = json.loads((root / "reference.json").read_text())
    failures = []
    literal_differences = []
    for item in reference["images"]:
        if (
            hashlib.sha256((root / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            failures.append({"kind": "song_qi_witness_identity", "file": item["file"]})
    for name in ("prior_historical_reference", "prior_dila_excerpt"):
        if (
            hashlib.sha256(
                (ROOT / "tests/fixtures" / reference[name]).read_bytes()
            ).hexdigest()
            != reference[name + "_sha256"]
        ):
            failures.append(
                {"kind": "song_qi_prior_reference_identity", "file": reference[name]}
            )
    for row in reference["derived_remainders"]:
        result = source_qi_sequence(profile_id=row["profile"], year_label=row["year"])
        actual = result["terms"][row["term_index"]]
        if (
            actual["source_big_remainder"],
            actual["source_small_remainder"],
            actual["source_subdivision_remainder"],
            actual["ganzhi_day"],
        ) != (row["big"], row["small"], row["subdivision"], row["ganzhi"]):
            failures.append(
                {
                    "kind": "song_qi_derived_remainder",
                    "profile": row["profile"],
                    "year": row["year"],
                    "term_index": row["term_index"],
                }
            )
    dila = json.loads(
        (ROOT / "tests/fixtures" / reference["prior_dila_excerpt"]).read_text()
    )
    cycle = [
        "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
        for i in range(60)
    ]
    for profile in reference["literal_profiles"]:
        result = source_qi_sequence(
            profile_id=profile["id"], year_label=profile["base_year"]
        )
        first = result["terms"][0]
        if (
            result["source_reference_accumulated_years"] != profile["accumulated_years"]
            or result["source_pdf_sha256"]
            != reference["sources"][profile["source"]]["sha256"]
            or first["source_day_divisor"] != profile["day_divisor"]
            or first["source_subdivision_divisor"] != profile["subdivision_divisor"]
            or first["cycle_origin_ganzhi"] != profile["cycle_origin"]
        ):
            failures.append(
                {"kind": "song_qi_literal_profile", "profile": profile["id"]}
            )
        for link in reference["date_links"]:
            row = source_qi_sequence(profile_id=profile["id"], year_label=link["year"])[
                "terms"
            ][link["term_index"]]
            month = next(m for m in dila["t_month"] if m[0] == link["month_id"])
            offset = (
                cycle.index(row["ganzhi_day"]) - link["first_day_cycle_index"]
            ) % 60
            label = date.fromordinal(month[6] + offset - 1721425).isoformat()
            if not (
                offset < month[7] - month[6] + 1
                and offset + 1 == link["expected_lunar_day"]
                and label == link["expected_gregorian_date_label"]
            ):
                failures.append(
                    {
                        "kind": "song_qi_date_only_link",
                        "profile": profile["id"],
                        "year": link["year"],
                    }
                )
            agrees = offset + 1 == link["source_term_claim_lunar_day"]
            if agrees != link["literal_term_day_agrees"]:
                failures.append(
                    {
                        "kind": "song_qi_literal_claim_status_changed",
                        "profile": profile["id"],
                    }
                )
            if not agrees:
                literal_differences.append(
                    {
                        "profile": profile["id"],
                        "year": link["year"],
                        "term": row["term"],
                        "printed_lunar_day": link["source_term_claim_lunar_day"],
                        "derived_lunar_day": offset + 1,
                        "derived_gregorian_date_label": label,
                    }
                )
    return {
        "checks_passed": not failures,
        "failures": failures,
        "scope": "Exact source arithmetic and two date-only month brackets; no absolute historical birth clock, UTC or actual calendar-use certification. Worksheets are derived checks, not original printed examples.",
        "explicit_algorithm_profiles": 2,
        "source_page_witnesses": len(reference["images"]),
        "derived_remainder_rows": len(reference["derived_remainders"]),
        "date_only_comparisons": 4,
        "unique_existing_heluo_examples_compared": 2,
        "all_examined_literal_term_days_agree": not literal_differences,
        "literal_term_day_disagreements": literal_differences,
        "unique_literal_term_day_disagreements": len(
            {(r["year"], r["term"]) for r in literal_differences}
        ),
        "actual_historical_calendar_use_established": False,
        "public_four_pillar_algorithm_changed": False,
        "validated_historical_utc_instants": 0,
        "new_original_birth_examples": 0,
        "new_real_world_outcomes": 0,
        "independent_second_reviews": 0,
    }


def tongtian_source_checks() -> dict:
    """Mei's two printed calculations are distinct from historical observations."""
    root = ROOT / "tests/fixtures/song_tongtian_v1"
    reference = json.loads((root / "reference.json").read_text())
    profile = reference["literal_profile"]["id"]
    failures = []
    for item in reference["images"]:
        if (
            hashlib.sha256((root / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            failures.append({"kind": "tongtian_witness_identity", "file": item["file"]})
    for path, digest in reference["prior_fixture_hashes"].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            failures.append({"kind": "tongtian_prior_fixture_identity", "file": path})
    for row in reference["printed_worked_calculations"]:
        result = source_term_remainder(
            profile_id=profile, accumulated_years=row["accumulated"], term_index=0
        )
        trace = result["winter_correction"]
        actual = (
            result["source_big_remainder"],
            result["source_small_remainder"],
            result["ganzhi_day"],
            trace["distance_years"],
            trace["rounded_chant_source_units"],
            trace["rounded_correction_source_units"],
            trace["fan_accumulation_source_units"],
            trace["corrected_accumulation_source_units"],
            trace["reading_source"]["sha256"],
        )
        expected = (
            row["big"],
            row["small"],
            row["ganzhi"],
            row["distance"],
            row["chant"],
            row["correction"],
            row["fan"],
            row["corrected"],
            reference["sources"]["mei"]["sha256"],
        )
        if actual != expected:
            failures.append(
                {"kind": "tongtian_printed_working", "accumulated": row["accumulated"]}
            )
    for row in reference["derived_worksheets"]:
        sequence = source_qi_sequence(profile_id=profile, year_label=row["year"])
        trace = sequence["winter_correction"]
        if trace["corrected_accumulation_source_units"] != row["winter_integral_units"]:
            failures.append({"kind": "tongtian_derived_winter", "year": row["year"]})
        for expected in row["rows"]:
            actual = sequence["terms"][expected["index"]]
            if (actual["source_big_remainder"], actual["ganzhi_day"]) != (
                expected["big"],
                expected["ganzhi"],
            ):
                failures.append(
                    {
                        "kind": "tongtian_derived_term",
                        "year": row["year"],
                        "term_index": expected["index"],
                    }
                )
    link = reference["date_link"]
    sequence = source_qi_sequence(profile_id=profile, year_label=link["year_label"])
    term = sequence["terms"][link["term_index"]]
    dila = json.loads(
        (
            ROOT / "tests/fixtures/heluo_historical_calendar_v1/dila-excerpt.json"
        ).read_text()
    )
    month = next(m for m in dila["t_month"] if m[0] == link["month_id"])
    cycle = [
        "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
        for i in range(60)
    ]
    offset = (cycle.index(term["ganzhi_day"]) - link["first_day_cycle_index"]) % 60
    label = date.fromordinal(month[6] + offset - 1721425).isoformat()
    before_days = offset + 1 - link["birth_caption_lunar_day"]
    if not (
        offset < month[7] - month[6] + 1
        and offset + 1 == link["expected_lunar_day"]
        and label == link["expected_gregorian_date_label"]
        and term["source_day_fraction"] == link["source_day_fraction"]
        and term["ganzhi_day"] != link["birth_caption_ganzhi"]
        and before_days == link["derived_term_day_minus_birth_caption_day"]
        and before_days != link["printed_before_daxue_days"]
        and not sequence["applied_to_public_four_pillars"]
    ):
        failures.append({"kind": "tongtian_retained_kai_xi_conflicts"})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "scope": "Named Tongtian algorithm under Mei's three-place reading; two printed calculation worksheets, five derived year worksheets and one reused Heluo date bracket. No historical UTC or author-use certification.",
        "explicit_additional_profile": profile,
        "source_page_witnesses": len(reference["images"]),
        "printed_calculation_worksheets": len(reference["printed_worked_calculations"]),
        "derived_year_worksheets": len(reference["derived_worksheets"]),
        "reused_existing_heluo_examples": 1,
        "kai_xi_daxue": {
            "ganzhi_day": term["ganzhi_day"],
            "lunar_day": offset + 1,
            "proleptic_gregorian_label": label,
            "source_day_fraction": term["source_day_fraction"],
        },
        "printed_birth_day_ganzhi": link["birth_caption_ganzhi"],
        "birth_day_ganzhi_agrees": term["ganzhi_day"] == link["birth_caption_ganzhi"],
        "printed_before_daxue_days": link["printed_before_daxue_days"],
        "derived_term_day_minus_birth_caption_day": before_days,
        "before_daxue_claim_agrees": before_days == link["printed_before_daxue_days"],
        "actual_author_calendar_use_established": False,
        "historical_birth_clock_resolved": False,
        "validated_historical_utc_instants": 0,
        "new_original_heluo_birth_examples": 0,
        "independent_second_reviews": 0,
        "public_four_pillar_algorithm_changed": False,
    }


def song_clock_source_checks() -> dict:
    """Source notation and conditional order, without imputed historical minutes."""
    root = ROOT / "tests/fixtures/song_clock_v1"
    reference = json.loads((root / "reference.json").read_text())
    failures = []
    for item in reference["witnesses"]:
        if (
            hashlib.sha256((root / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            failures.append(
                {"kind": "song_clock_witness_identity", "file": item["file"]}
            )
    for path, digest in reference["prior_fixture_hashes"].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            failures.append({"kind": "song_clock_prior_identity", "file": path})
    for rule in reference["literal_clock_rules"]:
        result = source_clock_from_fraction(
            profile_id=rule["profile"], numerator=0, denominator=1
        )
        if any(
            result["source_clock_constants"][key] != rule[key]
            for key in result["source_clock_constants"]
        ):
            failures.append(
                {"kind": "song_clock_literal_constants", "profile": rule["profile"]}
            )
        if result["ke_per_day"] != {"numerator": 100, "denominator": 1}:
            failures.append(
                {"kind": "song_clock_ke_per_day", "profile": rule["profile"]}
            )
    for row in reference["printed_clock_captions"]:
        result = source_term_clock(
            profile_id=row["profile"],
            accumulated_years=row["prior_worked_accumulated"],
            term_index=0,
        )
        clock = result["source_clock"]
        normalized = clock["normalized_chu_zheng"]
        actual = (
            normalized["branch"],
            normalized["phase"],
            normalized["whole_ke"],
            normalized["remaining_ke_fraction"],
            result["source_term"]["ganzhi_day"],
            clock["source_day_name_advanced_at_zi_chu"],
        )
        expected = (
            row["branch"],
            row["phase"],
            row["whole_ke_after_phase"],
            row["ke_fraction_after_phase"],
            row["same_source_day_name"],
            False,
        )
        if actual != expected:
            failures.append(
                {
                    "kind": "song_clock_reused_caption",
                    "accumulated": row["prior_worked_accumulated"],
                }
            )
    for row in reference["derived_term_clock_probes"]:
        result = source_term_clock(
            profile_id=row["profile"],
            accumulated_years=row["accumulated"],
            term_index=row["term_index"],
        )
        normalized = result["source_clock"]["normalized_chu_zheng"]
        if (
            result["source_clock"]["source_day_fraction"],
            normalized["branch"],
            normalized["phase"],
            normalized["whole_ke"],
            normalized["remaining_ke_fraction"],
        ) != (
            row["fraction"],
            row["branch"],
            row["phase"],
            row["whole_ke_after_phase"],
            row["ke_fraction_after_phase"],
        ):
            failures.append(
                {"kind": "song_clock_derived_probe", "profile": row["profile"]}
            )
    link = reference["kai_xi_conditional_comparison"]
    result = compare_branch_window_to_term(
        profile_id=link["profile"],
        accumulated_years=link["accumulated"],
        term_index=link["term_index"],
        birth_day_offset_from_term_day=link["explicit_birth_day_offset_from_term_day"],
        birth_branch=link["birth_branch"],
    )
    expected_window = {
        "start_inclusive": link["start_inclusive"],
        "end_exclusive": link["end_exclusive"],
    }
    if not (
        result["relation_under_assumption"] == link["expected_relation"]
        and result["birth_windows_relative_to_term_day"] == [expected_window]
        and result["boundary_inside_birth_window"]
        and not result["single_side_determined_under_assumption"]
        and not result["birth_instant_imputed"]
        and not result["public_month_pillar_changed"]
    ):
        failures.append({"kind": "song_clock_kai_xi_uncertainty"})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "scope": "Named source-clock normalization, two reused printed calculation captions and a conditional whole-Hai-window comparison; no imputed birth minute or historical UTC.",
        "clock_profiles": len(reference["literal_clock_rules"]),
        "source_page_witnesses": len(reference["witnesses"]),
        "new_page_images": sum(w["new_image"] for w in reference["witnesses"]),
        "reused_prior_calculation_clock_captions": 2,
        "new_original_calculation_examples": 0,
        "derived_term_clock_probes": len(reference["derived_term_clock_probes"]),
        "kai_xi_daxue_source_label": result["source_clock"]["normalized_chu_zheng"][
            "label"
        ],
        "kai_xi_relation_under_shared_clock_assumption": result[
            "relation_under_assumption"
        ],
        "kai_xi_unique_month_boundary_side_determined": result[
            "single_side_determined_under_assumption"
        ],
        "original_day_and_before_daxue_conflicts_resolved": False,
        "actual_author_birth_clock_established": False,
        "birth_minute_imputed": False,
        "validated_historical_utc_instants": 0,
        "new_original_heluo_birth_examples": 0,
        "independent_second_reviews": 0,
        "public_four_pillar_algorithm_changed": False,
    }


def historical_caption_checks() -> dict:
    """Date-only evidence, retaining every variant and literal disagreement."""
    root = ROOT / "tests/fixtures/heluo_historical_calendar_v1"
    reference = json.loads((root / "reference.json").read_text())
    source = json.loads((root / "dila-excerpt.json").read_text())
    worked_path = ROOT / "tests/fixtures" / reference["source_worked_fixture"]
    worked = json.loads(worked_path.read_text())
    failures = []
    differences = []
    if (
        hashlib.sha256(worked_path.read_bytes()).hexdigest()
        != reference["source_worked_fixture_sha256"]
    ):
        failures.append({"kind": "historical_worked_fixture_identity"})
    for item in reference["images"] + reference["data_files"]:
        if (
            hashlib.sha256((root / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            failures.append(
                {"kind": "historical_reference_identity", "file": item["file"]}
            )
    for row in reference["readings"]:
        month = next(r for r in source["t_month"] if r[0] == row["month_id"])
        original = next(r for r in worked["cases"] if r["id"] == row["id"])
        d = date.fromisoformat(row["proleptic_gregorian"])
        y, m, day = map(int, row["julian"].split("-"))
        a = (14 - m) // 12
        jy, jm = y + 4800 - a, m + 12 * a - 3
        julian_jdn = day + (153 * jm + 2) // 5 + 365 * jy + jy // 4 - 32083
        cycle = (row["day_cycle_addend"] + row["day"] - 1) % 60
        book_day = (
            "甲乙丙丁戊己庚辛壬癸"[cycle % 10] + "子丑寅卯辰巳午未申酉戌亥"[cycle % 12]
        )
        era = next(r for r in source["t_era"] if r[0] == month[5])
        emperor = next(r for r in source["t_emperor"] if r[0] == era[1])
        if not (
            emperor[1] == 86  # Southern Song, not the same-named Western Liao era.
            and month[4] == 0
            and month[10] == "S"
            and month[6] + row["day"] - 1 == row["jdn"] <= month[7]
            and d.toordinal() + 1721425 == row["jdn"] == julian_jdn
            and get_day_ganzhi(d.year, d.month, d.day)
            == row["calendar_day_ganzhi"]
            == book_day
            and original["pillars"][0] == row["printed_year_ganzhi"]
            and original["pillars"][2] == row["printed_day_ganzhi"]
            and (month[8] == row["printed_year_ganzhi"]) == row["year_caption_agrees"]
        ):
            failures.append(
                {
                    "kind": "historical_date_cross_reference",
                    "case": row["id"],
                    "reading": row["reading"],
                }
            )
        if row["calendar_day_ganzhi"] != row["printed_day_ganzhi"]:
            differences.append(
                {
                    "case": row["id"],
                    "reading": row["reading"],
                    "printed": row["printed_day_ganzhi"],
                    "calendar": row["calendar_day_ganzhi"],
                }
            )
    if [(r["case"], r["reading"]) for r in differences] != [
        ("yihai_bailu", "NLC"),
        ("bingyin_kai_xi", "both"),
        ("wuzi_dongzhi", "both"),
    ]:
        failures.append({"kind": "historical_literal_disagreements_changed"})
    return {
        "checks_passed": not failures,
        "checks_scope": "Frozen witnesses, DILA era-qualified month rows, explicitly named Julian/Gregorian date labels and printed cycle arithmetic versus the day-ganzhi implementation. Known source conflicts are retained, not successful full horoscopes.",
        "failures": failures,
        "existing_worked_examples": 4,
        "caption_readings": len(reference["readings"]),
        "calendar_book_pages_read": [3, 9, 10, 12, 249, 252, 253, 264],
        "dila_southern_song_month_rows": 4,
        "same_named_western_liao_month_rows_excluded_from_birth_conversion": 1,
        "all_literal_source_days_agree": not differences,
        "literal_day_disagreements": differences,
        "year_caption_conflicts": [
            r["id"] for r in reference["readings"] if not r["year_caption_agrees"]
        ],
        "validated_historical_birth_instants": 0,
        "independent_historical_solar_term_instants": 0,
        "new_worked_births": 0,
        "new_real_world_outcomes": 0,
        "independent_second_review_completed": False,
        "sinocal_conversion_result_obtained": False,
        "solar_term_convention_resolved": False,
    }


def worked_example_checks() -> dict:
    """Keep literal source conflicts separate from supported arithmetic checks."""
    root = ROOT / "tests/fixtures/numerology_nlc_v1"
    reference = json.loads((root / "worked-reference.json").read_text())
    manifest = json.loads((root / "worked-manifest.json").read_text())
    failures = []
    disagreements = []
    if (
        reference["source_pdf_sha256"] != manifest["source_pdf_sha256"]
        or manifest["source_pdf_sha256"] != SOURCE_SHA256
    ):
        failures.append({"kind": "worked_source_identity"})
    for row in manifest["images"]:
        if (
            hashlib.sha256((root / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            failures.append({"kind": "worked_witness_identity", "file": row["file"]})

    direct_count = 0
    derived_count = 0
    for case in reference["cases"]:
        p = dict(zip(("year", "month", "day", "hour"), case["pillars"]))
        args = dict(
            four_pillars=p,
            gender=case["gender"],
            birth_year=case["computational_year"],
            hour_zhi=p["hour"][1],
            month_zhi=p["month"][1],
            month_yang_ling=case["yang_ling"],
        )
        actual = heluo(**args)
        for field, expected in case["arithmetic_totals"].items():
            if actual[field] != expected:
                failures.append(
                    {"kind": "worked_arithmetic", "case_id": case["id"], "field": field}
                )
        for field, printed in case["source_totals"].items():
            if actual[field] != printed:
                disagreements.append(
                    dict(
                        case_id=case["id"],
                        field=field,
                        printed=printed,
                        arithmetic=actual[field],
                        repeated_in_source=case["source_repeated_totals"].get(field),
                    )
                )
        for section in ("direct_expected", "rule_derived_expected"):
            for field, expected in case.get(section, {}).items():
                value = actual
                for key in field.split("."):
                    value = value[key]
                if value != expected:
                    failures.append(
                        {
                            "kind": "worked_step",
                            "case_id": case["id"],
                            "field": field,
                            "reference_kind": section,
                        }
                    )
                if section == "direct_expected":
                    direct_count += 1
                else:
                    derived_count += 1
        for field in ("direct_houtian_start_age", "rule_derived_houtian_start_age"):
            if field in case:
                timing = da_yun(actual["xian"], actual["hou"])
                if timing["hou"][0]["ageStart"] != case[field]:
                    failures.append(
                        {
                            "kind": "worked_phase_age",
                            "case_id": case["id"],
                            "reference_kind": field,
                        }
                    )
        for invalid in ("false", "true", "", 0, 1, [], {}):
            try:
                heluo(**{**args, "month_yang_ling": invalid})
            except ValueError:
                pass
            else:
                failures.append(
                    {"kind": "invalid_half_year_accepted", "case_id": case["id"]}
                )
        if actual["yangLingBasis"] != "explicit_half_year":
            failures.append({"kind": "manual_half_year_claims_astronomical_provenance"})
    if disagreements != reference["expected_source_total_disagreements"]:
        failures.append({"kind": "source_conflict_changed", "actual": disagreements})
    lines = gua_lines("坎", "震")
    for half, name, pos in ((False, "地雷復", 5), (True, "雷地豫", 2)):
        result = transform_houtian("水雷屯", lines, 5, half)
        if (result["name"], result["yuan"]) != (name, pos):
            failures.append({"kind": "half_year_counterexample", "half": half})
    return {
        "checks_passed": not failures,
        "checks_scope": "Witness identities, manually added totals, supported worked steps, separately derived steps and input guards. This is not all-literal agreement or historical calendar certification.",
        "failures": failures,
        "original_four_pillar_examples": len(reference["cases"]),
        "whole_page_witnesses": len(manifest["images"]),
        "hand_added_total_comparisons": 8,
        "direct_step_comparisons": direct_count,
        "rule_derived_step_comparisons": derived_count,
        "unambiguous_literal_phase_age_anchors": 1,
        "ambiguous_phase_age_phrases": 1,
        "all_literal_totals_agree": not disagreements,
        "literal_total_disagreements": disagreements,
        "source_issues": [
            {"case_id": c["id"], "issues": c["source_issues"]}
            for c in reference["cases"]
            if c["source_issues"]
        ],
        "date_caption_variant_cases": 1,
        "validated_historical_birth_instants": 0,
        "independent_second_review_completed": False,
        "new_real_world_outcomes": 0,
    }


def line_condition_checks() -> dict:
    root = ROOT / "tests/fixtures/heluo_line_rules_v1"
    reference = json.loads((root / "reference.json").read_text())
    failures = []
    for item in reference["images"]:
        if (
            hashlib.sha256((root / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            failures.append(
                {"kind": "line_condition_witness_identity", "file": item["file"]}
            )
    for case in reference["derived_pattern_cases"]:
        for pos in range(1, 7):
            other = (pos + 2) % 6 + 1
            chart = {
                "xian": {"name": case["gua"], "lines": case["lines"], "yuan": pos},
                "hou": {"name": case["gua"], "lines": case["lines"], "yuan": other},
            }
            actual = line_conditions(chart)
            if {
                k: actual["literal_clauses"][k] for k in reference["literal_clauses"]
            } != reference["literal_clauses"]:
                failures.append(
                    {"kind": "line_condition_literal_clause", "case": case["gua"]}
                )
            for row, selected in zip(actual["phases"], (pos, other)):
                if (
                    row["pos"] != selected
                    or row["zhongzong"]["match"]
                    is not (selected == case["minority_pos"])
                    or row["zhongzong"]["minority_pos"] != case["minority_pos"]
                    or row["ruler_minister_seat"]["match"]
                    is not (selected in reference["ruler_minister_positions"])
                    or row["position_preference_order"]
                    != reference["position_order"][selected - 1]
                ):
                    failures.append(
                        {
                            "kind": "actual_selected_line_clause",
                            "case": case["gua"],
                            "phase": row["phase"],
                            "pos": selected,
                        }
                    )
            if (
                actual["source_dangwei"]["match"] is not None
                or actual["source_dangwei"]["month_polarity"] is not None
                or actual["source_dangwei"]["line_index_parity_substituted"]
                or actual["source_dangwei"]["solstice_half_year_substituted"]
                or actual["complete_assessment"]
                or actual["ten_condition_score"] is not None
            ):
                failures.append(
                    {"kind": "unsupported_dangwei_or_synthesis", "case": case["gua"]}
                )
    return {
        "checks_passed": not failures,
        "failures": failures,
        "named_zhongzong_illustrations": len(
            reference["named_zhongzong_illustrations"]
        ),
        "named_illustrations_already_in_derived_arrangements": True,
        "derived_five_plus_one_arrangements": len(reference["derived_pattern_cases"]),
        "selected_line_inputs_with_both_phase_results_checked": 72,
        "whole_page_witnesses": len(reference["images"]),
        "literal_preference_positions": 6,
        "source_dangwei_definition_resolved": False,
        "complete_ten_condition_assessment_verified": False,
        "independent_second_review_completed": False,
        "new_complete_classical_horoscopes": 0,
        "new_independent_calendar_instants": 0,
        "new_real_world_outcomes": 0,
    }


def support_clause_checks() -> dict:
    """One primary-source clause; derived response probes are not new horoscopes."""
    root = ROOT / "tests/fixtures/heluo_support_v1"
    reference = json.loads((root / "reference.json").read_text())
    failures = []
    for witness in reference["witnesses"]:
        if (
            hashlib.sha256((root / witness["file"]).read_bytes()).hexdigest()
            != witness["sha256"]
        ):
            failures.append(
                {"kind": "support_witness_identity", "file": witness["file"]}
            )
    for path, digest in reference["prior_fixture_hashes"].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            failures.append({"kind": "support_prior_reference_identity", "file": path})
    for case in reference["derived_probes"]:
        chart = {
            "xian": {"name": case["gua"], "lines": case["lines"], "yuan": case["pos"]},
            "hou": {
                "name": case["gua"],
                "lines": case["lines"],
                "yuan": case["responding_pos"],
            },
        }
        result = line_conditions(chart)
        source = result["literal_clauses"]["support"]
        if (
            source["note"] != reference["readings"]["primary_note"]
            or source["counterpart_note"] != reference["readings"]["counterpart_note"]
            or source["reading_policy"] != reference["readings"]["reading_policy"]
            or source["required_selected_yang"] is not False
            or source["required_corresponding_yang"] is not True
        ):
            failures.append({"kind": "support_literal_reading"})
        first, second = result["phases"]
        aid = first["source_youyuan"]
        actual = (
            aid["selected_pos"],
            aid["selected_yang"],
            aid["corresponding_pos"],
            aid["corresponding_yang"],
            aid["polarity_opposed"],
            aid["clause_match"],
        )
        expected = (
            case["pos"],
            case["selected_yang"],
            case["responding_pos"],
            case["responding_yang"],
            case["opposed"],
            case["clause_match"],
        )
        if actual != expected:
            failures.append(
                {
                    "kind": "support_derived_clause",
                    "gua": case["gua"],
                    "pos": case["pos"],
                }
            )
        other = second["source_youyuan"]
        if (
            other["selected_pos"] != case["responding_pos"]
            or other["corresponding_pos"] != case["pos"]
            or other["selected_yang"] != case["responding_yang"]
            or other["corresponding_yang"] != case["selected_yang"]
            or other["clause_match"]
            is not (case["responding_yang"] is False and case["selected_yang"] is True)
        ):
            failures.append(
                {"kind": "support_other_phase", "gua": case["gua"], "pos": case["pos"]}
            )
    return {
        "checks_passed": not failures,
        "failures": failures,
        "scope": "One newly registered named primary yin-line/yang-corresponding clause, two old page witnesses and one new region of the same counterpart page. Response mapping and six probes are derived; no full ten-condition or real-world verdict.",
        "new_literal_clauses": 1,
        "derived_selected_line_probes": len(reference["derived_probes"]),
        "reused_source_pages": 2,
        "new_source_regions": 1,
        "new_source_pages": 0,
        "counterpart_yin_position_wording_retained": True,
        "selected_reading": reference["readings"]["reading_policy"],
        "generic_opposition_substituted_for_named_clause": False,
        "negative_omen_inferred_from_unmatched_clause": False,
        "full_support_terminology_certified": False,
        "complete_ten_condition_assessment_verified": False,
        "new_complete_classical_horoscopes": 0,
        "new_independent_calendar_instants": 0,
        "independent_second_reviews": 0,
    }


def body_structure_checks() -> dict:
    """One literal structural example, with a non-coinciding reversal probe."""
    root = ROOT / "tests/fixtures/heluo_structure_v1"
    reference = json.loads((root / "reference.json").read_text())
    failures = []
    for witness in reference["witnesses"]:
        if (
            hashlib.sha256((root / witness["file"]).read_bytes()).hexdigest()
            != witness["sha256"]
        ):
            failures.append(
                {"kind": "structure_witness_identity", "file": witness["file"]}
            )
    for path, digest in reference["prior_reference_hashes"].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            failures.append(
                {"kind": "structure_prior_reference_identity", "file": path}
            )
    case = reference["source_case"]
    chart = {
        "xian": {"name": case["gua"], "lines": case["lines"]},
        "hou": {"name": "乾為天", "lines": [1, 1, 1, 1, 1, 1]},
    }
    result = body_structure(chart)
    variants = json.loads((root / "variants.json").read_text())
    if result["wording_variants"] != variants["wording_variants"]:
        failures.append({"kind": "structure_wording_variants"})
    first, second = result["phases"]
    for actual, expected in zip(first["records"], case["bodies"]):
        if (
            actual["kind"],
            actual["arity"],
            actual["original_positions"],
            actual["name"],
            actual["lines"],
        ) != (
            expected["kind"],
            expected["arity"],
            expected["positions"],
            expected["name"],
            expected["bits"],
        ):
            failures.append(
                {"kind": "structure_literal_case", "body": expected["kind"]}
            )
    if (
        len(first["records"]) != 8
        or first["whole_reversal"]["name"] != case["whole_reversal"]["name"]
        or first["whole_reversal"]["lines"] != case["whole_reversal"]["bits"]
    ):
        failures.append({"kind": "structure_literal_cardinality_or_reversal"})
    if (
        second["whole_reversal"]["lines"] != [1, 1, 1, 1, 1, 1]
        or second["whole_reversal"]["name"] != "乾為天"
    ):
        failures.append({"kind": "structure_reversal_not_complement"})
    if (
        first["literal_case_match"] is not True
        or first["literal_names_reproduced"] is not True
        or second["literal_case_match"] is not False
        or second["literal_names_reproduced"] is not None
    ):
        failures.append({"kind": "structure_example_scope"})
    if (
        result["five_ming_terminology"]["symbol_readings"]
        != reference["five_ming_symbol_readings"]
        or result["five_ming_terminology"]["selected_pillar"] is not None
        or result["complete_futi_assessment"] is not False
        or result["complete_assessment"] is not False
    ):
        failures.append({"kind": "structure_terminology_or_completeness"})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "new_structural_examples": 1,
        "source_body_names_in_that_example": 8,
        "source_whole_reversal_names": 1,
        "new_witness_images": len(reference["witnesses"]),
        "five_ming_literal_symbol_groups": 5,
        "additional_rule_derived_reversal_probes": 1,
        "new_complete_natal_examples": 0,
        "new_independent_calendar_instants": 0,
        "independent_second_reviews": 0,
        "full_futi_method_certified": False,
        "nayin_or_qi_body_scope_changed": False,
        "scope": "One Jian paragraph across two editions, six selected witness images including five-ming literal symbol lists. Six trigrams and two hexagrams are not eight nuclear trigrams. Other permutations and Qian are derived software probes, not extra original examples. No natal pillar is selected for five-ming and no full deTi/Xie verdict is inferred.",
    }


def pillar_link_source_checks() -> dict:
    """Ten formula groups, derived links and one retained literal conflict."""
    root = ROOT / "tests/fixtures/numerology_pillar_links_v1"
    ref = json.loads((root / "reference.json").read_text())
    failures = []
    for image in ref["witnesses"]:
        if (
            hashlib.sha256((root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                {"kind": "pillar_link_witness_identity", "file": image["file"]}
            )
    for path, digest in ref["prior_reference_hashes"].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            failures.append(
                {"kind": "pillar_link_prior_reference_identity", "file": path}
            )
    for target, basis in (("month", "year"), ("hour", "day")):
        for group in ref[target + "_heads"]:
            for stem in group["basis_stems"]:
                for branch, expected_stem in zip(
                    ref[target + "_branch_order"], group["expected_stems"]
                ):
                    pillars = dict(year="甲子", month="丙寅", day="甲子", hour="甲子")
                    from fatebridge.core.numerology_pillars import GAN, ZHI

                    i = GAN.index(stem)
                    pillars[basis] = stem + ZHI[i]
                    if target == "hour":
                        pillars["hour"] = expected_stem + branch
                    else:
                        pillars["month"] = expected_stem + branch
                    result = pillar_link_evidence(pillars)
                    row = next(r for r in result["links"] if r["target"] == target)
                    if (
                        row["head_pillar"] != group["head"]
                        or row["expected_pillar"] != expected_stem + branch
                        or row["matches"] is not True
                    ):
                        failures.append(
                            {
                                "kind": "pillar_link_derived_steps",
                                "target": target,
                                "stem": stem,
                                "branch": branch,
                            }
                        )
    literal = ref["literal_source_conflict"]
    p = dict(zip(("year", "month", "day", "hour"), literal["pillars"]))
    result = pillar_link_evidence(p)
    if (
        result["all_links_match"] is not False
        or result["links"][0]["expected_pillar"] != literal["expected_linked_month"]
        or result["links"][1]["matches"] is not True
    ):
        failures.append({"kind": "retained_literal_pillar_link_conflict"})
    try:
        require_pillar_links(p)
    except ValueError:
        pass
    else:
        failures.append({"kind": "incompatible_literal_pillars_accepted_as_birth"})
    totals = four_pillar_number_totals(p)
    for key, value in literal["arithmetic_totals"].items():
        if totals[{"tian_num": "tianNum", "di_num": "diNum"}.get(key, key)] != value:
            failures.append({"kind": "retained_literal_arithmetic", "field": key})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "direct_formula_groups": 10,
        "derived_unique_valid_links": 240,
        "witness_images": len(ref["witnesses"]),
        "reused_witness_images": 2,
        "retained_literal_stem_link_conflicts": [literal],
        "all_examined_literal_pillars_coherent": False,
        "original_reference_rows_kept": 4,
        "stem_link_compatible_rows_in_that_reference": 3,
        "formal_arithmetic_only_rows": 1,
        "new_complete_natal_examples": 0,
        "new_independent_calendar_instants": 0,
        "independent_second_reviews": 0,
        "complete_calendar_assessment": False,
        "scope": "Month/hour stem linkage only, conditional on already selected pillars and branches. One literal introductory arithmetic list is incompatible with the appended formula; its original numbers are retained without constructing a birth chart. Does not prove month/day boundaries, historical clocks or whole-calendar accuracy.",
    }


def body_relation_checks() -> dict:
    root = ROOT / "tests/fixtures/numerology_nlc_v1"
    reference = json.loads((root / "body-reference.json").read_text())
    manifest = json.loads((root / "body-manifest.json").read_text())
    failures = []
    if manifest["source_pdf_sha256"] != SOURCE_SHA256:
        failures.append({"kind": "body_source_identity"})
    for item in manifest["images"]:
        if (
            hashlib.sha256((root / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            failures.append({"kind": "body_witness_identity", "file": item["file"]})
    for natal, expected in reference["rule_derived_relation_grid"].items():
        for trigram, relation in zip(reference["trigram_order"], expected):
            if element_relation(ELEMENTS[trigram], natal) != relation:
                failures.append(
                    {
                        "kind": "directed_relation_grid",
                        "natal": natal,
                        "trigram": trigram,
                    }
                )
    for case in reference["generating_clause_combinations"]:
        if element_relation(ELEMENTS[case["trigram"]], "水") != case["relation"]:
            failures.append({"kind": "body_generating_literal", "case": case})
    for case in reference["direct_reverse_readings"]:
        if (
            element_relation(case["source_body_element"], case["nayin"])
            != case["relation"]
        ):
            failures.append({"kind": "body_reverse_literal", "case": case})
    case = reference["direct_nuclear_reading"]
    if _san_cai(case["lines"])[1:3] != case["nuclear_trigrams"]:
        failures.append({"kind": "literal_nuclear_example"})
    bodies = {p: {"gua": "乾為天", "trigrams": ["乾"] * 4} for p in ("xian", "hou")}
    for year, targets, expected in (
        ("甲寅", {"tian": "乾", "di": "艮"}, False),
        ("乙卯", {"tian": "坤", "di": "震"}, True),
    ):
        result = body_evidence(year, bodies, targets)
        if (
            result["generating_qi"]["condition_match"] is not expected
            or result["present"] is not None
        ):
            failures.append({"kind": "yuanqi_qualifier", "year": year})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "whole_page_witnesses": len(manifest["images"]),
        "direct_generating_clauses": 1,
        "rule_derived_generating_combinations": len(
            reference["generating_clause_combinations"]
        ),
        "direct_reverse_element_pairs": len(reference["direct_reverse_readings"]),
        "direct_nuclear_partial_examples": 1,
        "rule_derived_relation_grid_probes": 40,
        "yuanqi_qualifier_probes": 2,
        "independent_second_review_completed": False,
        "complete_classical_deti": False,
        "new_classical_worked_horoscopes": 0,
    }


def month_and_clock_checks() -> dict:
    root = ROOT / "tests/fixtures/numerology_nlc_v1"
    reference = json.loads((root / "month-reference.json").read_text())
    manifest = json.loads((root / "month-manifest.json").read_text())
    collation = json.loads(MONTH_COLLATION_PATH.read_text())
    failures = []
    if (
        reference["source_pdf_sha256"] != SOURCE_SHA256
        or manifest["pdf_sha256"] != SOURCE_SHA256
    ):
        failures.append({"kind": "month_source_identity"})
    if (
        collation["source_pdf_sha256"] != SOURCE_SHA256
        or collation["assigned_months"] != reference["assigned_months"]
        or len(collation["windows"]) != reference["additional_month_clauses"]
    ):
        failures.append({"kind": "month_collation_reference_disagreement"})
    for page in manifest["images"]:
        if (
            hashlib.sha256((root / page["file"]).read_bytes()).hexdigest()
            != page["sha256"]
        ):
            failures.append({"kind": "month_image_identity", "case": page["file"]})

    def chart(name):
        return {phase: {"name": name} for phase in ("xian", "hou")}

    for case in reference["assigned_months"]:
        result = month_affinity(chart(case["gua"]), case["branch"], MONTH_GUA)
        if any(
            (
                r["assigned_month_number"],
                r["source_pdf_page"],
                r["assigned_month_match"],
            )
            != (case["month"], case["page"], True)
            for r in result["phases"]
        ):
            failures.append({"kind": "original_assigned_month", "case": case})
    migrations = {
        ("離為火", 3, 0),
        ("雷水解", 5, 0),
        ("水風井", 2, 0),
        ("風水渙", 3, 0),
    }
    for case in reference["window_cases"]:
        result = month_affinity(
            chart(case["gua"]), MONTH_BRANCHES[case["month"] - 1], MONTH_GUA
        )
        index = case.get("window_index", 0)
        migrated = (case["gua"], case["month"], index) in migrations
        for row in result["phases"]:
            window = row["additional_windows"][index]
            correct = (
                case["match"] is False
                and window["month_label_match"] is False
                and window["match"] is None
                and window["status"] == "additional_condition_unresolved"
                if migrated
                else window["match"] is case["match"]
            )
            if not correct:
                failures.append({"kind": "additional_month_window", "case": case})
    invalid_clocks = [None, "", " ", "未知", "24:00", "09:33:00Z", False]
    for value in invalid_clocks:
        try:
            require_birth_clock(value)
        except ValueError:
            pass
        else:
            failures.append(
                {"kind": "clock_invented_or_invalid_accepted", "case": value}
            )
    if require_birth_clock("0:0") != "00:00:00":
        failures.append({"kind": "explicit_midnight_rejected"})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "source_pdf_sha256": SOURCE_SHA256,
        "collation_sha256": hashlib.sha256(
            MONTH_COLLATION_PATH.read_bytes()
        ).hexdigest(),
        "source_pdf_pages": sorted(
            {p["pdf_page"] for p in manifest["images"]} | {141, 142, 143}
        ),
        "new_lu_headers_verified_separately": 6,
        "direct_assigned_month_readings": len(reference["assigned_months"]),
        "reviewed_hexagram_introductions": reference["reviewed_hexagram_introductions"],
        "additional_month_clauses": reference["additional_month_clauses"],
        "rule_derived_window_probes": len(reference["window_cases"]),
        "qualified_false_month_verdicts_corrected": len(migrations),
        "invalid_clock_domain_probes": len(invalid_clocks),
        "new_classical_worked_horoscopes": 0,
        "qian_endpoint_month_resolved": False,
        "yi_ninth_month_endpoint_resolved": False,
        "sui_first_month_conflict_resolved": False,
        "month_lunar_vs_solar_boundary_resolved": False,
        "complete_detime_or_deti_assessment": False,
    }


def yaoci_collation_checks() -> dict:
    """Check the installed overlay and witnesses; not independent second review."""
    root = ROOT / "tests/fixtures/numerology_nlc_v1"
    manifest = json.loads((root / "yaoci-manifest.json").read_text())
    data = json.loads(COLLATION_PATH.read_text())
    summary = collation_summary()
    failures = []
    if (
        manifest["pdf_sha256"] != SOURCE_SHA256
        or data["source_pdf_sha256"] != SOURCE_SHA256
    ):
        failures.append({"kind": "yaoci_source_identity"})
    for page in manifest["images"]:
        if (
            hashlib.sha256((root / page["file"]).read_bytes()).hexdigest()
            != page["sha256"]
        ):
            failures.append({"kind": "yaoci_image_identity", "case": page["file"]})
    for entry in data["entries"]:
        actual = yao_text(entry["hexagram"], entry["line"])
        if not actual or (
            actual["yaoci"],
            actual["text_provenance"].get("pdf_page"),
        ) != (entry["yaoci"], entry["pdf_page"]):
            failures.append({"kind": "yaoci_overlay_selection", "case": entry})
    for gua, pos, word in (
        ("坤為地", 4, "括囊"),
        ("水雷屯", 2, "邅如"),
        ("天水訟", 4, "命渝"),
        ("天水訟", 6, "鞶帶"),
        ("地水師", 1, "否臧"),
    ):
        actual = yao_text(gua, pos)
        if not actual or word not in actual["yaoci"]:
            failures.append({"kind": "yaoci_correction", "case": [gua, pos]})
    return {
        **summary,
        "checks_passed": not failures,
        "failures": failures,
        "source_pdf_pages": sorted(
            {p["pdf_page"] for p in manifest["images"]} | {141, 142, 143}
        ),
        "new_lu_headers_verified_separately": 6,
        "independent_second_review_completed": False,
        "new_classical_worked_horoscopes": 0,
        "complete_commentary_collation": False,
    }


def jiehou_source_checks() -> dict:
    """Selected labels and two explicit reconstructions; no selected hou date."""
    from fatebridge.core import heluo_jiehou as jh

    root = ROOT / "tests/fixtures/heluo_jiehou_v1"
    reference = json.loads((root / "reference.json").read_text())
    models = json.loads((root / "nominal-models.json").read_text())
    failures = []
    for image in reference["images"]:
        if (
            hashlib.sha256((root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(dict(kind="heluo_jiehou_witness", file=image["file"]))
    for row in reference["term_rows"]:
        actual = jh.term_assignment(row["term"])
        if {k: actual[k] for k in row} != row:
            failures.append(dict(kind="heluo_jiehou_term_row", term=row["term"]))
    actual_rows = jh.literal_hou_table()
    if [
        {k: r[k] for k in reference["hou_rows"][i]} for i, r in enumerate(actual_rows)
    ] != reference["hou_rows"]:
        failures.append(dict(kind="heluo_jiehou_literal_table"))
    conflicts = [
        dict(
            term=r["term"],
            entry_in_group=r["entry_in_group"],
            gua=r["gua"],
            raw=r["raw_yao"],
            canonical=r["canonical_yao"],
        )
        for r in actual_rows
        if not r["yao_polarity_agrees"]
    ]
    if conflicts != reference["expected_yao_polarity_conflicts"]:
        failures.append(dict(kind="heluo_jiehou_literal_polarity_differences"))
    for probe in models["probes"]:
        for model, key in zip(models["models"], ("continuous", "caption_first")):
            row = jh.nominal_hou_day(probe["offset"], model=model)
            if (row["gua"], row["position"]) != (probe[key]["gua"], probe[key]["pos"]):
                failures.append(
                    dict(
                        kind="heluo_jiehou_nominal_slot",
                        model=model,
                        offset=probe["offset"],
                    )
                )
    # Synthetic existing-term context: these are label/source checks, not24 new
    # astronomical instants or an independent check of the term solver.
    p = jh.jiehou_evidence(
        dict(
            term="冬至",
            quarter="坎",
            anchor_utc="2026-12-22T00:00:00+00:00",
            precision="birth_instant",
        )
    )
    if [c["model"] for c in p["reconstruction_models"]] != models["models"]:
        failures.append(dict(kind="heluo_jiehou_model_coverage"))
    if (
        p["selected_hou"] is not None
        or p["huagong_assessment"] is not None
        or p["selected_reconstruction_model"] is not None
        or p["historical_term_instants_established"] is not False
        or p["hou_physical_date_mapping_complete"] is not False
    ):
        failures.append(dict(kind="heluo_jiehou_unestablished_model_or_date"))
    for comparison in p["reconstruction_models"]:
        model = comparison["model"]
        expected = models["expected_counts"][model]
        caption = comparison["caption_comparison"]
        if [r["printed"] for r in caption] != reference["caption"]["rows"]:
            failures.append(dict(kind="heluo_jiehou_printed_caption", model=model))
        for field, key in [
            ("caption_difference_count", "caption_differences"),
            ("term_start_position_difference_count", "term_position_differences"),
            ("term_start_gua_difference_count", "term_gua_differences"),
        ]:
            if comparison[field] != expected[key]:
                failures.append(
                    dict(kind="heluo_jiehou_model_comparison", model=model, field=field)
                )
        if any(
            r["derived"]["physical_date_applied"] is not False
            or r["derived"]["extra_ke_applied"] is not False
            for r in caption
        ):
            failures.append(
                dict(kind="heluo_jiehou_nominal_promoted_to_date", model=model)
            )
    return dict(
        checks_passed=not failures,
        failures=failures,
        source_pdf_pages=[41, 42, 43, 44],
        direct_term_assignments=24,
        literal_hou_labels=72,
        distinct_hou_gua=60,
        retained_yao_polarity_differences=4,
        explicit_nominal_models=models["models"],
        derived_model_slot_probes=28,
        reused_caption_rows=6,
        per_model_counts=models["expected_counts"],
        selected_model=None,
        complete_hou_physical_date_mapping=False,
        complete_huagong_assessment=False,
        new_classical_horoscopes=0,
        new_calendar_instants=0,
        independent_second_reviews=0,
        scope="Four term-gua bases,72 literal labels and60 hou gua are distinct. Two named nominal reconstructions preserve different caption/table agreements without fitting or selecting a physical calendar. Primary literal polarity disagreements and ambiguous364-yao wording remain; no phenological-gloss or song collation claimed.",
    )


def source_clock_checks() -> dict:
    """Literal counts and conditional arithmetic; no historical clock epoch."""
    from fatebridge.core.heluo_clock import (
        compare_daily_extra,
        source_branch_partition,
        source_clock_evidence,
        source_six_day_blocks,
    )
    from fatebridge.core.heluo_timing import HeluoYearContextError, build_heluo_timing

    root = ROOT / "tests/fixtures/heluo_clock_v1"
    reference = json.loads((root / "reference.json").read_text())
    failures = []
    for image in reference["images"]:
        if (
            hashlib.sha256((root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                dict(kind="heluo_clock_witness_identity", file=image["file"])
            )
    branch_reference = json.loads((root / "branch-shift-reference.json").read_text())
    blocks = source_six_day_blocks(origin_branch="未", blocks=12)
    if [
        {k: row[k] for k in ("branch", "next_branch", "start_ke", "end_ke", "extra_ke")}
        for row in blocks
    ] != branch_reference["origin_wei_first_twelve"]:
        failures.append(dict(kind="heluo_clock_six_day_branch_shifts"))
    for origin in "子丑寅卯辰巳午未申酉戌亥":
        if (
            source_six_day_blocks(origin_branch=origin, blocks=60)[-1]["end_ke"]
            != branch_reference["total_ke"]
        ):
            failures.append(dict(kind="heluo_clock_full_cycle_total", origin=origin))
    profile = source_clock_evidence()
    shift = profile["branch_shift_projection"]
    if (
        shift["year_blocks"] != branch_reference["whole_year_blocks"]
        or shift["extra_shi"] != branch_reference["extra_shi"]
        or shift["extra_ke"] != branch_reference["extra_ke"]
        or [
            shift["total_source_days"]["numerator"],
            shift["total_source_days"]["denominator"],
        ]
        != branch_reference["total_source_days"]
        or shift["branch_start_only"] is not True
        or shift["derived_only"] is not True
        or shift["source_fen_scale_selected"] is not False
        or shift["daily_internal_distribution_resolved"] is not False
    ):
        failures.append(dict(kind="heluo_clock_branch_projection_scope"))
    if profile["source_pdf_sha256"] != reference["source_pdf_sha256"]:
        failures.append(dict(kind="heluo_clock_source_identity"))
    rows = source_branch_partition(origin_branch="子")
    if [{k: r[k] for k in ["branch", "start_ke", "end_ke"]} for r in rows] != reference[
        "cyclic_partition_from_zi"
    ]:
        failures.append(dict(kind="heluo_clock_branch_partition"))
    for case in reference["equal_shi_projection"]["assumed_scale_comparisons"]:
        result = compare_daily_extra(fen_per_ke=case["fen_per_ke"])
        for key, expected_key in [
            ("extra_ke_per_day", "extra_ke_per_day"),
            ("year_days", "year_days"),
            ("difference_from_printed_year_days", "difference_from365_days"),
        ]:
            if [result[key]["numerator"], result[key]["denominator"]] != case[
                expected_key
            ]:
                failures.append(
                    dict(
                        kind="heluo_clock_conditional_arithmetic",
                        scale=case["fen_per_ke"],
                        field=key,
                    )
                )
        if (
            result["source_fen_scale_verified"] is not False
            or result["physical_clock_applied"] is not False
        ):
            failures.append(
                dict(
                    kind="heluo_clock_assumption_promoted_to_source",
                    scale=case["fen_per_ke"],
                )
            )
    if (
        profile["physical_origin_branch"] is not None
        or profile["daily_extra_literal"]["fen_per_ke"] is not None
        or profile["physical_clock_applied"] is not False
        or profile["calendar_mapping_complete"] is not False
    ):
        failures.append(dict(kind="heluo_clock_unestablished_epoch_or_scale"))
    chart = heluo(
        four_pillars=dict(year="甲子", month="丁卯", day="庚申", hour="庚辰"),
        gender="男",
        birth_year=1924,
        month_zhi="卯",
        hour_zhi="辰",
    )
    rejected = False
    try:
        build_heluo_timing(chart, "乙丑", analysis_year=1924)
    except HeluoYearContextError:
        rejected = True
    if not rejected:
        failures.append(dict(kind="heluo_timing_mixed_year_context"))
    good = build_heluo_timing(chart, "甲子", analysis_year=1924)
    if (
        good["selected_annual"]["gua"] != "天風姤"
        or good["selected_annual"]["ganzhi"] != "甲子"
    ):
        failures.append(dict(kind="heluo_timing_valid_year_context"))
    return dict(
        checks_passed=not failures,
        failures=failures,
        source_pdf_pages=[39, 40, 41],
        witness_images=3,
        derived_branch_partitions=12,
        derived_six_day_block_boundaries=12,
        full_cycle_origin_invariants=12,
        conditional_scale_comparisons=4,
        reused_daily_example=reference["reused_timing_anchor"],
        source_fen_scale_verified=False,
        physical_clock_epoch_established=False,
        complete_timing_calendar_mapping=False,
        wrong_valid_ganzhi_context_rejected=rejected,
        new_original_horoscopes=0,
        new_calendar_instants=0,
        independent_second_reviews=0,
        scope="Printed count cycle, branch-start six-day shifts and explicit year-context binding. Sixty unequal branch shifts add500ke to360 source days without selecting a fen scale. Scale18 belongs only to a separate uniform-allocation comparison. Neither construction supplies daily interpolation, a physical epoch or actual date/birth-clock conversion.",
    )


def xusong_commentary_checks() -> dict:
    """Twelve new line readings and content identity, not a second reviewer."""
    from fatebridge.core import heluo_texts as ht

    root = ROOT / "tests/fixtures/heluo_xusong_v1"
    reference = json.loads((root / "reference.json").read_text())
    verified = json.loads((root / "verified-readings.json").read_text())
    failures = []
    for name, key in [
        ("reference.json", "draft_sha256"),
        ("amendments.json", "amendments_sha256"),
    ]:
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != verified[key]:
            failures.append(dict(kind="xusong_draft_identity", file=name))
    for w in reference["images"]:
        if hashlib.sha256((root / w["file"]).read_bytes()).hexdigest() != w["sha256"]:
            failures.append(dict(kind="xusong_witness_identity", file=w["file"]))
    for e in verified["entries"]:
        t = yao_text(e["hexagram"], e["line"])
        if t is None or (
            t["detail"] != "".join(s["text"] for s in e["sections"])
            or t["commentary_sections"]
            != [dict(s, applicability=None) for s in e["sections"]]
            or t["text_provenance"]["commentary_pdf_pages"] != e["pdf_pages"]
            or t["text_provenance"]["commentary_reading_notes"] != e["reading_notes"]
            or t["commentary_branch_selection"]["selected_section_ids"]
        ):
            failures.append(
                dict(kind="xusong_complete_commentary", case=[e["hexagram"], e["line"]])
            )
    rejected = []
    for layer, path, expected in [
        ("header", ht.COLLATION_PATH, ht.HEADER_CONTENT_SHA256),
        ("commentary", ht.COMMENTARY_PATH, ht.COMMENTARY_CONTENT_SHA256),
    ]:
        d = json.loads(path.read_text())
        summary = (
            ht.collation_summary()
            if layer == "header"
            else ht.commentary_collation_summary()
        )
        if (
            summary["content_sha256"] != expected
            or summary["sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()
        ):
            failures.append(dict(kind="heluo_text_content_identity", layer=layer))
        # Nonempty, well-formed data used to retain a false collated status.
        if layer == "header":
            d["entries"][0]["yaoci"] = "非原典标题"
        else:
            s = d["entries"][0]["sections"]
            s[1]["text"], s[2]["text"] = s[2]["text"], s[1]["text"]
        try:
            ht._pin_content(d, expected)
        except ValueError:
            rejected.append(layer)
        else:
            failures.append(
                dict(kind="heluo_nonempty_text_tamper_accepted", layer=layer)
            )
    return dict(
        checks_passed=not failures,
        failures=failures,
        source_pdf_pages=list(range(129, 135)),
        native_witness_images=6,
        reused_previous_context_page=129,
        new_complete_line_commentaries=12,
        previous_commentaries_preserved=24,
        withdrawn_draft_groups=6,
        nonempty_tamper_layers_rejected=rejected,
        header_content_sha256=ht.HEADER_CONTENT_SHA256,
        commentary_content_sha256=ht.COMMENTARY_CONTENT_SHA256,
        independent_second_review_completed=False,
        new_original_horoscopes=0,
        new_calendar_instants=0,
        scope="Twelve single-reader Xu/Song line commentaries; full conditions and unusual literal forms retained. Canonical content pinning detects exchanged nonempty branches and forged headers; it does not certify source readings, free explanations or real-world predictions.",
    )


def shibi_commentary_checks() -> dict:
    """Twelve primary readings and one conditional link; no new horoscope."""
    from fatebridge.core import heluo_texts as ht

    root = ROOT / "tests/fixtures/heluo_shibi_v1"
    draft = json.loads((root / "reference.json").read_text())
    verified = json.loads((root / "verified-readings.json").read_text())
    failures = []
    for name, key in (
        ("reference.json", "draft_sha256"),
        ("amendments.json", "amendments_sha256"),
    ):
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != verified[key]:
            failures.append(dict(kind="shibi_draft_identity", file=name))
    for witness in draft["images"]:
        if (
            hashlib.sha256((root / witness["file"]).read_bytes()).hexdigest()
            != witness["sha256"]
        ):
            failures.append(
                dict(kind="shibi_native_image_identity", file=witness["file"])
            )
    for e in verified["entries"]:
        t = yao_text(e["hexagram"], e["line"])
        if t is None or (
            t["detail"] != "".join(s["text"] for s in e["sections"])
            or t["commentary_sections"]
            != [dict(s, applicability=None) for s in e["sections"]]
            or t["text_provenance"]["commentary_pdf_pages"] != e["pdf_pages"]
            or t["text_provenance"]["commentary_reading_notes"] != e["reading_notes"]
            or t["commentary_branch_selection"]["selected_section_ids"]
        ):
            failures.append(
                dict(kind="shibi_complete_commentary", case=[e["hexagram"], e["line"]])
            )
    ref = verified["conditional_reference"]
    expected = {k: v for k, v in ref.items() if k != "comparison_normal_houtian"}
    if yao_text("地水師", 3).get("commentary_cross_references") != [expected]:
        failures.append(dict(kind="shibi_conditional_reference"))
    hou = transform_houtian("地水師", ref["source_lines"], 3, True)
    normal = ref["comparison_normal_houtian"]
    if hou != dict(name=normal["hexagram"], lines=normal["lines"], yuan=normal["line"]):
        failures.append(dict(kind="shibi_reference_replaced_houtian"))
    bi2 = yao_text("水地比", 2)
    if (
        "戊戌" in bi2["detail"]
        or "戊戌" not in bi2["text_provenance"]["inherited_detail"]
    ):
        failures.append(dict(kind="bi2_whole_gua_condition_mixed_into_line"))
    summary = ht.commentary_collation_summary()
    if (
        summary["collated_line_commentaries"],
        summary["pending_line_commentaries"],
    ) != (SOURCE_HEADER_COUNT, SOURCE_PENDING_COUNT):
        failures.append(dict(kind="shibi_coverage_count"))
    return dict(
        checks_passed=not failures,
        failures=failures,
        source_pdf_pages=verified["source_commentary_pages"],
        native_witness_images=len(draft["images"]),
        context_only_page=139,
        new_complete_line_commentaries=12,
        previous_commentaries_preserved=36,
        withdrawn_draft_groups=15,
        conditional_quotation_links=1,
        independent_second_review_completed=False,
        new_original_horoscopes=0,
        new_calendar_instants=0,
        new_real_world_outcomes=0,
        scope="Shi/Bi complete line commentaries from the same printing; page139 is context only. Draft corrections are not inherited defects. Shi3 single-line flip agrees with its conditional Sheng3 quotation without swapping trigrams or replacing natal/timing charts; applicability is unknown. Bi2 excludes misplaced whole-gua Najia text; that separate condition is retained in the month/Najia layer. No complete-book or prediction certification.",
    )


def xiaochuli_commentary_checks() -> dict:
    """Native text, absent label and same-name/different-line reference checks."""
    from fatebridge.core import heluo_texts as ht

    root = ROOT / "tests/fixtures/heluo_xiaochuli_v1"
    draft = json.loads((root / "reference.json").read_text())
    verified = json.loads((root / "verified-readings.json").read_text())
    failures = []
    for name, key in (
        ("reference.json", "draft_sha256"),
        ("amendments.json", "amendments_sha256"),
    ):
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != verified[key]:
            failures.append(dict(kind="xiaochuli_draft_identity", file=name))
    for w in draft["images"]:
        if hashlib.sha256((root / w["file"]).read_bytes()).hexdigest() != w["sha256"]:
            failures.append(dict(kind="xiaochuli_image_identity", file=w["file"]))
    for e in verified["entries"]:
        t = yao_text(e["hexagram"], e["line"])
        if t is None or (
            t["detail"] != "".join(s["text"] for s in e["sections"])
            or t["commentary_sections"]
            != [dict(s, applicability=None) for s in e["sections"]]
            or t["text_provenance"]["commentary_pdf_pages"] != e["pdf_pages"]
            or t["text_provenance"]["commentary_reading_notes"] != e["reading_notes"]
            or t["commentary_branch_selection"]["selected_section_ids"]
        ):
            failures.append(
                dict(
                    kind="xiaochuli_complete_commentary",
                    case=[e["hexagram"], e["line"]],
                )
            )
    for e in verified["headers"]:
        t = yao_text(e["hexagram"], e["line"])
        if t is None or (t["yaoci"], t["text_provenance"].get("pdf_page")) != (
            e["yaoci"],
            e["pdf_page"],
        ):
            failures.append(dict(kind="lu_new_header", case=e["line"]))
    three = yao_text("風天小畜", 3)
    if [s["section_id"] for s in three["commentary_sections"]] != verified[
        "source_section_exception"
    ]["section_ids"] or three["commentary_branch_selection"].get(
        "condition_labels_not_separately_printed"
    ) != [
        "不葉者"
    ]:
        failures.append(dict(kind="xiaochu3_unprinted_condition_label"))
    ref = verified["conditional_reference"]
    if yao_text("風天小畜", 1).get("commentary_cross_references") != [
        {k: v for k, v in ref.items() if k != "comparison_normal_houtian"}
    ]:
        failures.append(dict(kind="xiaochu1_conditional_reference"))
    normal = ref["comparison_normal_houtian"]
    if transform_houtian("風天小畜", ref["source_lines"], 1, True) != dict(
        name=normal["hexagram"], lines=normal["lines"], yuan=normal["line"]
    ):
        failures.append(dict(kind="xiaochu1_reference_replaced_houtian"))
    if yao_text("天澤履", 6).get("commentary_cross_references"):
        failures.append(dict(kind="lu6_literal_phrase_improperly_became_transform"))
    return dict(
        checks_passed=not failures,
        failures=failures,
        source_pdf_pages=list(range(139, 144)),
        context_only_page=144,
        native_witness_images=6,
        new_complete_line_commentaries=12,
        new_line_headers=6,
        previous_commentaries_preserved=48,
        previous_headers_preserved=54,
        withdrawn_draft_groups=8,
        source_section_layout_exceptions=1,
        new_conditional_quotation_links=1,
        independent_second_review_completed=False,
        new_original_horoscopes=0,
        new_calendar_instants=0,
        new_real_world_outcomes=0,
        scope="Xiao Chu/Lu complete commentaries and six Lu headers from one named printing. Xiao Chu3 has no separately printed Buxie label; absence is not false. Xiao Chu1's conditional Xun1 quotation and normal Houtian Xun4 share the name but not the selected line. Lu6 引兌 remains literal, not an automatic transform. No prediction or full-book certification.",
    )


def taipi_commentary_checks() -> dict:
    """Same-printing text coverage and conditional parents; no branch verdict."""
    from fatebridge.core import heluo_texts as ht

    root = ROOT / "tests/fixtures/heluo_taipi_v1"
    draft = json.loads((root / "reference.json").read_text())
    verified = json.loads((root / "verified-readings.json").read_text())
    failures = []
    for name, key in (
        ("reference.json", "draft_sha256"),
        ("amendments.json", "amendments_sha256"),
    ):
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != verified[key]:
            failures.append(dict(kind="taipi_draft_identity", file=name))
    for w in draft["images"]:
        if hashlib.sha256((root / w["file"]).read_bytes()).hexdigest() != w["sha256"]:
            failures.append(dict(kind="taipi_image_identity", file=w["file"]))
    for e in verified["entries"]:
        t = yao_text(e["hexagram"], e["line"])
        if t is None or (
            t["detail"] != "".join(s["text"] for s in e["sections"])
            or t["commentary_sections"]
            != [dict(s, applicability=None) for s in e["sections"]]
            or t["text_provenance"]["commentary_pdf_pages"] != e["pdf_pages"]
            or t["text_provenance"]["commentary_reading_notes"] != e["reading_notes"]
            or t["commentary_branch_selection"]["selected_section_ids"]
        ):
            failures.append(
                dict(kind="taipi_complete_commentary", case=[e["hexagram"], e["line"]])
            )
    for e in verified["headers"]:
        t = yao_text(e["hexagram"], e["line"])
        if t is None or (t["yaoci"], t["text_provenance"].get("pdf_page")) != (
            e["yaoci"],
            e["pdf_page"],
        ):
            failures.append(dict(kind="taipi_header", case=[e["hexagram"], e["line"]]))
    for r in verified["conditional_references"]:
        if yao_text(r["source_hexagram"], r["source_line"]).get(
            "commentary_cross_references"
        ) != [r]:
            failures.append(
                dict(
                    kind="taipi_conditional_parent",
                    case=[r["source_hexagram"], r["source_line"]],
                )
            )
    if yao_text("天地否", 6).get("commentary_cross_references"):
        failures.append(dict(kind="pi6_unnamed_target_invented"))
    return dict(
        checks_passed=not failures,
        failures=failures,
        source_pdf_pages=list(range(144, 149)),
        native_witness_images=5,
        previously_archived_page_reused=144,
        new_complete_line_commentaries=12,
        new_line_headers=12,
        previous_commentaries_preserved=60,
        previous_headers_preserved=60,
        withdrawn_draft_groups=3,
        new_conditional_quotation_links=3,
        independent_second_review_completed=False,
        new_original_horoscopes=0,
        new_calendar_instants=0,
        new_real_world_outcomes=0,
        scope="Tai/Pi single-reader commentary and header coverage of one printing, including doubtful lexical readings with explicit notes. Pi4's Guan quotation belongs to xie, not annual; Tai2 and Pi5 references retain annual conditions. Single flips do not replace natal Houtian or certify complete target texts. Pi6 does not name a target. Reused page144 and rereading are not independent witnesses or reviews; no full-book or reality certification.",
    )


def commentary_collation_checks() -> dict:
    """Finite source excerpts and conditional preservation, not second review."""
    root = ROOT / "tests/fixtures/numerology_nlc_v1"
    reference = json.loads((root / "commentary-reference.json").read_text())
    summary = commentary_collation_summary()
    failures = []
    if reference["source_pdf_sha256"] != summary["source_pdf_sha256"]:
        failures.append({"kind": "commentary_source_identity"})
    for witness in reference["images"]:
        if (
            hashlib.sha256((root / witness["file"]).read_bytes()).hexdigest()
            != witness["sha256"]
        ):
            failures.append(
                {"kind": "commentary_witness_identity", "case": witness["file"]}
            )
    for case in reference["cases"]:
        text = yao_text(case["hexagram"], case["line"])
        if text is None or (
            any(e not in text["detail"] for e in case["source_excerpts"])
            or any(e in text["detail"] for e in case["inherited_errors"])
            or text["text_provenance"]["commentary_pdf_pages"] != case["pdf_pages"]
        ):
            failures.append({"kind": "commentary_literal_excerpt", "case": case})
    for gua in ("乾為天", "坤為地"):
        for pos in range(1, 7):
            text = yao_text(gua, pos)
            if text is None or (
                text["commentary_branch_selection"]["selected_section_ids"]
                or any(
                    s["applicability"] is not None for s in text["commentary_sections"]
                )
                or text["text_provenance"]["automatic_branch_selection"]
                or text["text_provenance"]["poem_presence_in_reviewed_sections"]
                is not False
            ):
                failures.append(
                    {"kind": "commentary_branch_preservation", "case": [gua, pos]}
                )
    extension_root = ROOT / "tests/fixtures/heluo_tunmeng_v1"
    extension = json.loads((extension_root / "reference.json").read_text())
    verified = json.loads((extension_root / "verified-readings.json").read_text())
    for name, digest in (
        ("reference.json", verified["draft_sha256"]),
        ("amendments.json", verified["amendments_sha256"]),
    ):
        if hashlib.sha256((extension_root / name).read_bytes()).hexdigest() != digest:
            failures.append({"kind": "tunmeng_reference_identity", "file": name})
    if (
        hashlib.sha256((root / "commentary-reference.json").read_bytes()).hexdigest()
        != extension["previous_reference_sha256"]
    ):
        failures.append({"kind": "original_commentary_reference_changed"})
    for witness in extension["images"]:
        if (
            hashlib.sha256((extension_root / witness["file"]).read_bytes()).hexdigest()
            != witness["sha256"]
        ):
            failures.append(
                {"kind": "tunmeng_native_witness_identity", "file": witness["file"]}
            )
    for case in verified["entries"]:
        text = yao_text(case["hexagram"], case["line"])
        if text is None or (
            text["detail"] != "".join(s["text"] for s in case["sections"])
            or text["commentary_sections"]
            != [dict(s, applicability=None) for s in case["sections"]]
            or text["text_provenance"]["commentary_pdf_pages"] != case["pdf_pages"]
            or text["text_provenance"]["commentary_reading_notes"]
            != case["reading_notes"]
            or text["commentary_branch_selection"]["selected_section_ids"]
            or text["text_provenance"]["automatic_branch_selection"]
        ):
            failures.append(
                {
                    "kind": "tunmeng_complete_commentary",
                    "case": [case["hexagram"], case["line"]],
                }
            )
    if (
        summary["collated_line_commentaries"] != SOURCE_HEADER_COUNT
        or summary["pending_line_commentaries"] != SOURCE_PENDING_COUNT
    ):
        failures.append({"kind": "commentary_coverage_count"})
    return {
        **summary,
        "checks_passed": not failures,
        "failures": failures,
        "source_pdf_pages": list(range(119, 129)),
        "selected_literal_excerpt_cases": len(reference["cases"]),
        "tunmeng_native_witness_images": len(extension["images"]),
        "witness_image_scope": "Reused round39 Tun/Meng native-page references, with page129 retained as that earlier batch's context. Current source coverage additionally requires the separate Xu/Song, Shi/Bi, Xiao Chu/Lu, Tai/Pi, Tongren, Dayou and Qian15 checks; no new independent source or reviewer counted.",
        "reused_witness_images": len(reference["images"]),
        "tunmeng_complete_line_commentaries": len(verified["entries"]),
        "withdrawn_initial_transcription_groups": 8,
        "independent_second_review_completed": False,
        "new_classical_worked_horoscopes": 0,
        "complete_commentary_collation": False,
    }


def yuantang_scan_checks() -> dict:
    root = ROOT / "tests/fixtures/numerology_nlc_v1"
    reference = json.loads((root / "yuantang-reference.json").read_text())
    failures = []
    comparisons = 0
    if reference["source_pdf_sha256"] != SOURCE_SHA256:
        failures.append({"kind": "yuantang_source_identity"})
    for row in reference["images"]:
        if (
            hashlib.sha256((root / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            failures.append({"kind": "yuantang_witness_identity", "case": row["file"]})
    for row in reference["mixed_tables"]:
        for hour, position in zip(row["hours"], row["positions"]):
            result = yuantang_placement(row["lines"], hour, True, None)
            comparisons += 1
            if (
                result["selected_pos"] != position
                or result["slot_positions"] != row["positions"]
            ):
                failures.append(
                    {
                        "kind": "yuantang_literal_mixed_position",
                        "case": [row["id"], hour],
                    }
                )
    for row in reference["pure_tables"]:
        halves = (False, True) if row["half_year"] == "any" else (row["half_year"],)
        bit = int(row["hexagram"] == "乾為天")
        for half in halves:
            for hour, position in zip(row["hours"], row["positions"]):
                comparisons += 1
                if (
                    yuantang_placement([bit] * 6, hour, row["is_male"], half)[
                        "selected_pos"
                    ]
                    != position
                ):
                    failures.append(
                        {
                            "kind": "yuantang_literal_pure_position",
                            "case": [row["id"], half, hour],
                        }
                    )
    for clause in reference["pure_reuse_clauses"]:
        row = next(
            r for r in reference["pure_tables"] if r["id"] == clause["reuse_table"]
        )
        bit = int(clause["hexagram"] == "乾為天")
        for hour, position in zip(row["hours"], row["positions"]):
            comparisons += 1
            if (
                yuantang_placement(
                    [bit] * 6, hour, clause["sex"] == "male", clause["half_year"]
                )["selected_pos"]
                != position
            ):
                failures.append(
                    {
                        "kind": "yuantang_reuse_clause",
                        "case": [clause["hexagram"], hour],
                    }
                )
    for row in reference["modern_selection_probes"]:
        pillars = dict(zip(("year", "month", "day", "hour"), row["pillars"]))
        args = dict(
            four_pillars=pillars,
            gender=row["gender"],
            birth_year=row["year"],
            hour_zhi=pillars["hour"][1],
            month_zhi=pillars["month"][1],
        )
        try:
            heluo(**args)
        except ValueError as exc:
            if "跨至点" not in str(exc):
                failures.append(
                    {"kind": "yuantang_wrong_guard_error", "case": row["date"]}
                )
        else:
            failures.append(
                {"kind": "yuantang_guessed_boundary_half", "case": row["date"]}
            )
        result = heluo(**args, month_yang_ling=row["half_year"])
        if (result["xian"]["yuan"], result["hou"]["name"], result["hou"]["yuan"]) != (
            row["yuan"],
            row["hou"],
            row["hou_yuan"],
        ):
            failures.append({"kind": "yuantang_explicit_probe", "case": row["date"]})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "source_pdf_sha256": reference["source_pdf_sha256"],
        "source_pdf_pages": list(range(26, 33)),
        "direct_mixed_diagram_positions": reference["direct_mixed_position_count"],
        "direct_pure_diagram_positions": reference[
            "direct_pure_diagram_position_count"
        ],
        "pure_reuse_rule_derived_positions": reference[
            "pure_reuse_rule_derived_positions"
        ],
        "half_insensitive_repeated_comparisons": 24,
        "runtime_position_comparisons": comparisons,
        "modern_selection_probes": 2,
        "new_worked_birth_examples": 0,
        "new_independent_calendar_instants": 0,
        "independent_second_review_completed": False,
    }


def canping_text_checks() -> dict:
    root = ROOT / "tests/fixtures/canping_texts_v1"
    reference = json.loads((root / "reference.json").read_text())
    summary = canping_collation_summary()
    failures = []
    header_root = ROOT / "tests/fixtures/canping_header_evidence_v1"
    header_reference = json.loads((header_root / "reference.json").read_text())
    for file, expected in (
        (header_reference["literal_file"], header_reference["literal_sha256"]),
        (
            header_reference["source_manifest_file"],
            header_reference["source_manifest_sha256"],
        ),
    ):
        if hashlib.sha256((header_root / file).read_bytes()).hexdigest() != expected:
            failures.append({"kind": "canping_header_fixture_identity", "case": file})
    header_witness = summary.get("number_reading_witness", {})
    # Runtime provenance omits local fixture names, canvas IDs and byte sizes.
    # Compare every published source coordinate, URL and digest explicitly.
    expected_header_pages = [
        {
            **{
                k: page[k]
                for k in ("pdf_page", "image_service_url", "canvas_dimensions")
            },
            "regions": [
                {k: region[k] for k in ("region", "url", "sha256")}
                for region in page["regions"]
            ],
        }
        for page in header_reference["pages"]
    ]
    if (
        header_witness.get("headers") != header_reference["headers"]
        or header_witness.get("pages") != expected_header_pages
        or header_witness.get("source_manifest_sha256")
        != header_reference["source_manifest_sha256"]
        or len(header_reference["headers"]) != 6
        or len(header_reference["cells"]) != 18
        or len(header_reference["pages"]) != 5
        or header_witness.get("headers_resolved") != 0
        or header_witness.get("headers_still_uncertain") != 6
        or any(
            header_reference[k] != 0
            for k in (
                "new_confirmed_cells",
                "new_numbered_cells_examined",
                "new_independent_reviews",
                "new_classical_birth_examples",
                "new_independent_calendar_instants",
                "new_real_world_outcomes",
            )
        )
    ):
        failures.append({"kind": "canping_header_scope"})
    for page in header_reference["pages"]:
        if {tuple(r["region"]) for r in page["regions"]} != {
            (0, 0, 2950, 2200),
            (2950, 0, 2950, 2200),
            (0, 2200, 2950, 2200),
            (2950, 2200, 2950, 2200),
        }:
            failures.append(
                {"kind": "canping_header_region_coverage", "case": page["pdf_page"]}
            )
        for region in page["regions"]:
            if (
                hashlib.sha256((header_root / region["file"]).read_bytes()).hexdigest()
                != region["sha256"]
            ):
                failures.append(
                    {"kind": "canping_header_region_identity", "case": region["file"]}
                )
    for cell in header_reference["cells"]:
        result = canping_lookup_record(cell["element"], cell["number"], cell["kind"])
        selected = result["selection"]
        evidence = selected.get("number_reading_evidence", {})
        if (
            result["text"] != cell["text"]
            or selected.get("body_reading_status") != cell["body_reading_status"]
            or selected.get("cell_status") != "source_reading_uncertain"
            or selected.get("number_attribution_status") != "provisional_inherited_key"
            or evidence.get("resolution_status") != "unresolved"
            or evidence.get("provisional_number") != cell["number"]
            or evidence.get("pdf_page") != cell["pdf_page"]
            or evidence.get("body_evidence_basis") != cell["body_evidence_basis"]
            or not isinstance(evidence.get("observed_header"), str)
            or "□" not in evidence["observed_header"]
        ):
            failures.append(
                {
                    "kind": "canping_header_body_separation",
                    "case": [cell["element"], cell["number"], cell["kind"]],
                }
            )
    for image in reference["images"]:
        if (
            hashlib.sha256((root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                {"kind": "canping_text_witness_identity", "case": image["file"]}
            )
    if summary["source_pdf_sha256"] != reference["source_pdf_sha256"]:
        failures.append({"kind": "canping_text_source_identity"})
    count = 0
    for row in reference["literal_reference"]:
        for kind, text in row["cells"].items():
            count += 1
            actual = canping_lookup_record(row["element"], row["number"], kind)
            if (
                actual["text"] != text
                or actual["selection"].get("source_pdf_page") != row["pdf_page"]
            ):
                failures.append(
                    {
                        "kind": "canping_literal_cell",
                        "case": [row["element"], row["number"], kind],
                    }
                )
    unreachable = []
    active_invalid = []
    special_unreachable = []
    raw = canping_inherited_corpus()
    prior_comparison_text = raw["parts"]["火"]["3838"]["male"]
    try:
        raw["parts"]["火"]["3838"]["male"] = "audit caller mutation"
        inherited_cache_isolated = (
            canping_lookup_record("火", 2838, "male")["selection"]["inherited_text"]
            == prior_comparison_text
            and canping_inherited_corpus()["parts"]["火"]["3838"]["male"]
            == prior_comparison_text
        )
    finally:
        raw["parts"]["火"]["3838"]["male"] = prior_comparison_text
    if not inherited_cache_isolated:
        failures.append({"kind": "canping_inherited_source_cache_exposed"})
    for element, part in raw["parts"].items():
        reachable = {
            compute_number(d, h, element)[k]
            for d in "子丑寅卯辰巳午未申酉戌亥"
            for h in "子丑寅卯辰巳午未申酉戌亥"
            for k in ("numShun", "numNi")
        }
        active = {int(n) for n in part}
        unreachable.extend(
            {"element": element, "number": n} for n in sorted(active - reachable)
        )
        for correction in summary["corrected_number_headers"]:
            if correction["element"] == element:
                active.discard(correction["inherited"])
                active.add(correction["corrected"])
        active_invalid.extend(
            {"element": element, "number": n} for n in sorted(active - reachable)
        )
        if 2869 not in reachable:
            special_unreachable.append(element)
        for kind in ("male", "female", "luck"):
            if canping_lookup_record(element, 2869, kind)["text"]:
                failures.append(
                    {
                        "kind": "canping_unresolved_special_applied",
                        "case": [element, kind],
                    }
                )
    failures.extend(
        {"kind": "canping_active_header_unreachable", "case": case}
        for case in active_invalid
    )
    for alias in ("female", "FEMALE", "F", " f "):
        result = canping(
            year_gz="甲子",
            month_branch="寅",
            day_branch="子",
            hour_branch="子",
            gender=alias,
            include_luck=False,
        )
        if result["kindMain"] != "female":
            failures.append({"kind": "canping_gender_column", "case": alias})
    missing = canping(
        year_gz="甲子",
        month_branch="寅",
        day_branch="子",
        hour_branch="子",
        include_luck=False,
    )
    if missing["kindMain"] is not None or missing["benming"]["verses"]["textShun"]:
        failures.append({"kind": "canping_missing_gender_selected_column"})
    rereading_root = ROOT / "tests/fixtures/canping_rereading_v1"
    rereading_reference = json.loads((rereading_root / "reference.json").read_text())
    rereading_cells = {
        (r["number"], r["kind"]): r for r in rereading_reference["cells"]
    }
    for file, expected in (
        (rereading_reference["literal_file"], rereading_reference["literal_sha256"]),
        (
            rereading_reference["source_manifest_file"],
            rereading_reference["source_manifest_sha256"],
        ),
    ):
        if hashlib.sha256((rereading_root / file).read_bytes()).hexdigest() != expected:
            failures.append({"kind": "canping_rereading_identity", "case": file})
    for page in rereading_reference["pages"]:
        regions = page["regions"]
        if {tuple(r["region"]) for r in regions} != {
            (0, 0, 2950, 2200),
            (2950, 0, 2950, 2200),
            (0, 2200, 2950, 2200),
            (2950, 2200, 2950, 2200),
        }:
            failures.append(
                {"kind": "canping_native_region_coverage", "case": page["pdf_page"]}
            )
        for region in regions:
            if (
                hashlib.sha256(
                    (rereading_root / region["file"]).read_bytes()
                ).hexdigest()
                != region["sha256"]
            ):
                failures.append(
                    {"kind": "canping_native_region_identity", "case": region["file"]}
                )
    if (
        len(rereading_cells) != 40
        or rereading_reference["resolved_cells"] != 30
        or rereading_reference["still_uncertain_cells"] != 10
        or rereading_reference["new_numbered_cells_examined"] != 0
        or rereading_reference["new_independent_reviews"] != 0
        or summary["rereading_witness"]["source_manifest_sha256"]
        != rereading_reference["source_manifest_sha256"]
    ):
        failures.append({"kind": "canping_rereading_scope"})
    water_root = ROOT / "tests/fixtures/canping_water_v1"
    water_reference = json.loads(
        (water_root / "reference.json").read_text(encoding="utf-8")
    )
    literal_path = water_root / water_reference["literal_file"]
    if (
        hashlib.sha256(literal_path.read_bytes()).hexdigest()
        != water_reference["literal_sha256"]
    ):
        failures.append({"kind": "canping_water_literal_identity"})
    for image in water_reference["images"]:
        if (
            hashlib.sha256((water_root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                {"kind": "canping_water_page_identity", "case": image["file"]}
            )
    special_states = {
        (r["number"], r["kind"]): r["state"]
        for r in water_reference["expected_special_states"]
    }
    water_rows = list(
        csv.DictReader(literal_path.open(encoding="utf-8"), delimiter="\t")
    )
    uncertain_cells = 0
    for row in water_rows:
        for kind in ("male", "female", "luck"):
            number = int(row["number"])
            revision = rereading_cells.get((number, kind))
            expected = (
                revision["state"]
                if revision
                else special_states.get((number, kind), "source_cell_visually_collated")
            )
            uncertain_cells += expected == "source_reading_uncertain"
            selected = canping_lookup_record("水", number, kind)
            if revision:
                history = selected["selection"].get("reading_revision", {})
                if (
                    history.get("previous_text") != row[kind]
                    or history.get("previous_cell_status") != "source_reading_uncertain"
                ):
                    failures.append(
                        {"kind": "canping_rereading_history", "case": [number, kind]}
                    )
            if (
                selected["text"] != (revision["text"] if revision else row[kind])
                or selected["selection"]["cell_status"] != expected
                or selected["selection"].get("source_pdf_page") != int(row["pdf_page"])
            ):
                failures.append({"kind": "canping_water_cell", "case": [number, kind]})
    witness_root = ROOT / "tests/fixtures/canping_witness_v1"
    witness_reference = json.loads(
        (witness_root / "reference.json").read_text(encoding="utf-8")
    )
    witness_literal = witness_root / witness_reference["literal_file"]
    if (
        hashlib.sha256(witness_literal.read_bytes()).hexdigest()
        != witness_reference["literal_sha256"]
    ):
        failures.append({"kind": "canping_witness_literal_identity"})
    for image in witness_reference["images"]:
        if (
            hashlib.sha256((witness_root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                {"kind": "canping_witness_page_identity", "case": image["file"]}
            )
    witness_rows = list(
        csv.DictReader(witness_literal.open(encoding="utf-8"), delimiter="\t")
    )
    for row in witness_rows:
        selected = canping_lookup_record("水", int(row["number"]), row["kind"])
        witness = selected["selection"].get("witnesses", [{}])[0]
        if (
            witness.get("text") != row["text"]
            or witness.get("body_pdf_page") != int(row["body_pdf_page"])
            or witness.get("replaces_selected_text") is not False
        ):
            failures.append(
                {"kind": "canping_witness_cell", "case": [row["number"], row["kind"]]}
            )
    witness_summary = summary["comparison_witness"]
    water_witness = witness_summary["part_coverage"]["水"]
    if (
        len(witness_rows) != 36
        or water_witness["cells_examined"] != 36
        or water_witness["clear_readings"] != 34
        or water_witness["uncertain_readings"] != 2
    ):
        failures.append({"kind": "canping_witness_coverage"})
    if (
        len(water_rows) != 78
        or uncertain_cells != 10
        or summary["part_coverage"]["水"]["collated_cells"] != 224
    ):
        failures.append({"kind": "canping_water_coverage"})
    gold_root = ROOT / "tests/fixtures/canping_gold_v1"
    gold_reference = json.loads((gold_root / "reference.json").read_text())
    gold_literal = gold_root / gold_reference["literal_file"]
    if (
        summary["source_pdf_sha256"] != gold_reference["source_pdf_sha256"]
        or hashlib.sha256(gold_literal.read_bytes()).hexdigest()
        != gold_reference["literal_sha256"]
    ):
        failures.append({"kind": "canping_gold_source_identity"})
    for image in gold_reference["images"]:
        if (
            hashlib.sha256((gold_root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                {"kind": "canping_gold_page_identity", "case": image["file"]}
            )
    gold_states = {
        (int(r["number"]), r["kind"]): r["state"]
        for r in gold_reference["expected_special_states"]
    }
    gold_rows = list(
        csv.DictReader(gold_literal.open(encoding="utf-8"), delimiter="\t")
    )
    gold_native_root = ROOT / "tests/fixtures/canping_gold_rereading_v1"
    gold_native_reference = json.loads(
        (gold_native_root / "reference.json").read_text()
    )
    gold_native_cells = {
        (c["number"], c["kind"]): c for c in gold_native_reference["cells"]
    }
    for file, digest in (
        (
            gold_native_reference["literal_file"],
            gold_native_reference["literal_sha256"],
        ),
        (
            gold_native_reference["source_manifest_file"],
            gold_native_reference["source_manifest_sha256"],
        ),
    ):
        if hashlib.sha256((gold_native_root / file).read_bytes()).hexdigest() != digest:
            failures.append({"kind": "canping_gold_native_identity", "case": file})
    gold_native_witnesses = [
        w
        for w in summary["additional_rereading_witnesses"]
        if w["fixture_id"] == gold_native_reference["fixture_id"]
    ]
    expected_gold_pages = [
        {
            **{k: p[k] for k in ("pdf_page", "image_service_url", "canvas_dimensions")},
            "regions": [
                {k: r[k] for k in ("region", "url", "sha256")} for r in p["regions"]
            ],
        }
        for p in gold_native_reference["pages"]
    ]
    if (
        len(gold_native_witnesses) != 1
        or gold_native_witnesses[0]["pages"] != expected_gold_pages
        or gold_native_witnesses[0]["resolved_cells"] != 4
        or gold_native_witnesses[0]["still_uncertain_cells"] != 11
        or len(gold_native_cells) != 15
        or gold_native_reference["native_region_count"] != 28
        or gold_native_reference["reused_region_count"] != 0
        or gold_native_reference["new_stored_region_count"] != 28
        or set(gold_native_cells)
        != {
            (int(r["number"]), r["kind"])
            for r in gold_reference["expected_special_states"]
            if r["state"] == "source_reading_uncertain"
        }
        or any(
            gold_native_reference[k] != 0
            for k in (
                "new_numbered_cells_examined",
                "new_independent_reviews",
                "new_classical_birth_examples",
                "new_independent_calendar_instants",
                "new_real_world_outcomes",
            )
        )
    ):
        failures.append({"kind": "canping_gold_native_scope"})
    for page in gold_native_reference["pages"]:
        if {tuple(r["region"]) for r in page["regions"]} != {
            (0, 0, 2950, 2200),
            (2950, 0, 2950, 2200),
            (0, 2200, 2950, 2200),
            (2950, 2200, 2950, 2200),
        }:
            failures.append(
                {
                    "kind": "canping_gold_native_region_coverage",
                    "case": page["pdf_page"],
                }
            )
        for region in page["regions"]:
            if (
                hashlib.sha256(
                    (gold_native_root / region["file"]).read_bytes()
                ).hexdigest()
                != region["sha256"]
                or region["reused_prior_region"] is not False
            ):
                failures.append(
                    {
                        "kind": "canping_gold_native_region_identity",
                        "case": region["file"],
                    }
                )
    gold_uncertain = 0
    for row in gold_rows:
        for kind in ("male", "female", "luck"):
            number = int(row["number"])
            revision = gold_native_cells.get((number, kind))
            expected = (
                revision["state"]
                if revision
                else gold_states.get((number, kind), "source_cell_visually_collated")
            )
            gold_uncertain += expected == "source_reading_uncertain"
            selected = canping_lookup_record("金", number, kind)
            s = selected["selection"]
            if revision and (
                s.get("reading_revision", {}).get("previous_text") != row[kind]
                or s["reading_revision"].get("previous_collation_version") != "1.9.0"
                or s["reading_revision"].get("rereading_id")
                != gold_native_reference["fixture_id"]
                or s["reading_revision"].get("source_pdf_page") != int(row["pdf_page"])
            ):
                failures.append(
                    {"kind": "canping_gold_native_revision", "case": [number, kind]}
                )
            if (
                selected["text"] != (revision["text"] if revision else row[kind])
                or selected["selection"]["number"] != number
                or selected["selection"]["cell_status"] != expected
                or selected["selection"].get("source_pdf_page") != int(row["pdf_page"])
            ):
                failures.append({"kind": "canping_gold_cell", "case": [number, kind]})
    for row in gold_reference["numbered_content_correspondence"]:
        for kind in ("male", "female", "luck"):
            number = row["source_number"]
            selected = canping_lookup_record("金", number, kind)["selection"]
            if (
                selected.get("inherited_text") != raw["parts"]["金"][str(number)][kind]
                or selected.get("inherited_number") is not None
                or selected["source_pdf_page"] != row["source_pdf_page"]
            ):
                failures.append(
                    {"kind": "canping_gold_number_body_pairing", "case": [number, kind]}
                )
    if (
        len(gold_rows) != 78
        or gold_uncertain != 11
        or summary["part_coverage"]["金"]["collated_cells"] != 223
    ):
        failures.append({"kind": "canping_gold_coverage"})
    fire_root = ROOT / "tests/fixtures/canping_fire_v1"
    fire_reference = json.loads((fire_root / "reference.json").read_text())
    fire_literal = fire_root / fire_reference["literal_file"]
    if (
        summary["source_pdf_sha256"] != fire_reference["source_pdf_sha256"]
        or hashlib.sha256(fire_literal.read_bytes()).hexdigest()
        != fire_reference["literal_sha256"]
    ):
        failures.append({"kind": "canping_fire_source_identity"})
    for image in fire_reference["images"]:
        if (
            hashlib.sha256((fire_root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                {"kind": "canping_fire_page_identity", "case": image["file"]}
            )
    fire_rows = list(
        csv.DictReader(fire_literal.open(encoding="utf-8"), delimiter="\t")
    )
    fire_states = {
        (r["number"], r["kind"]): r["state"]
        for r in fire_reference["expected_special_states"]
    }
    fire_headers = {r["number"] for r in fire_reference["number_reading_uncertainties"]}
    fire_native_root = ROOT / "tests/fixtures/canping_fire_rereading_v1"
    fire_native_reference = json.loads(
        (fire_native_root / "reference.json").read_text()
    )
    fire_native_cells = {
        (c["number"], c["kind"]): c for c in fire_native_reference["cells"]
    }
    for file, digest in (
        (
            fire_native_reference["literal_file"],
            fire_native_reference["literal_sha256"],
        ),
        (
            fire_native_reference["source_manifest_file"],
            fire_native_reference["source_manifest_sha256"],
        ),
    ):
        if hashlib.sha256((fire_native_root / file).read_bytes()).hexdigest() != digest:
            failures.append({"kind": "canping_fire_native_identity", "case": file})
    fire_native_witnesses = [
        w
        for w in summary["additional_rereading_witnesses"]
        if w["fixture_id"] == fire_native_reference["fixture_id"]
    ]
    expected_fire_pages = [
        {
            **{k: p[k] for k in ("pdf_page", "image_service_url", "canvas_dimensions")},
            "regions": [
                {k: r[k] for k in ("region", "url", "sha256")} for r in p["regions"]
            ],
        }
        for p in fire_native_reference["pages"]
    ]
    if (
        len(fire_native_witnesses) != 1
        or fire_native_witnesses[0]["pages"] != expected_fire_pages
        or fire_native_witnesses[0]["resolved_cells"] != 6
        or fire_native_witnesses[0]["still_uncertain_cells"] != 5
        or len(fire_native_cells) != 11
        or fire_native_reference["native_region_count"] != 24
        or fire_native_reference["reused_region_count"] != 8
        or fire_native_reference["new_stored_region_count"] != 16
        or set(fire_native_cells)
        != {
            (r["number"], r["kind"])
            for r in fire_reference["uncertain_cells"]
            if r["number"] not in fire_headers
        }
        or any(
            fire_native_reference[k] != 0
            for k in (
                "new_numbered_cells_examined",
                "new_independent_reviews",
                "new_classical_birth_examples",
                "new_independent_calendar_instants",
                "new_real_world_outcomes",
            )
        )
    ):
        failures.append({"kind": "canping_fire_native_scope"})
    for page in fire_native_reference["pages"]:
        if {tuple(r["region"]) for r in page["regions"]} != {
            (0, 0, 2950, 2200),
            (2950, 0, 2950, 2200),
            (0, 2200, 2950, 2200),
            (2950, 2200, 2950, 2200),
        }:
            failures.append(
                {
                    "kind": "canping_fire_native_region_coverage",
                    "case": page["pdf_page"],
                }
            )
        for region in page["regions"]:
            if hashlib.sha256(
                (fire_native_root / region["file"]).read_bytes()
            ).hexdigest() != region["sha256"] or region["reused_prior_region"] != (
                page["pdf_page"] in (77, 80)
            ):
                failures.append(
                    {
                        "kind": "canping_fire_native_region_identity",
                        "case": region["file"],
                    }
                )
    fire_uncertain = 0
    for row in fire_rows:
        for kind in ("male", "female", "luck"):
            number = int(row["number"])
            revision = fire_native_cells.get((number, kind))
            expected = (
                revision["state"]
                if revision
                else fire_states.get((number, kind), "source_cell_visually_collated")
            )
            fire_uncertain += expected == "source_reading_uncertain"
            selected = canping_lookup_record("火", number, kind)
            s = selected["selection"]
            if revision and (
                s.get("reading_revision", {}).get("previous_text") != row[kind]
                or s["reading_revision"].get("previous_collation_version") != "1.7.0"
                or s["reading_revision"].get("rereading_id")
                != fire_native_reference["fixture_id"]
            ):
                failures.append(
                    {"kind": "canping_fire_native_revision", "case": [number, kind]}
                )
            if (
                selected["text"] != (revision["text"] if revision else row[kind])
                or s["number"] != number
                or s["cell_status"] != expected
                or s.get("source_pdf_page") != int(row["pdf_page"])
                or (
                    number in fire_headers
                    and (
                        s.get("number_attribution_status")
                        != "provisional_inherited_key"
                        or not s.get("number_reading_uncertainties")
                        or expected != "source_reading_uncertain"
                    )
                )
            ):
                failures.append({"kind": "canping_fire_cell", "case": [number, kind]})
    if (
        len(fire_rows) != 78
        or fire_uncertain != 11
        or len(fire_headers) != 2
        or summary["part_coverage"]["火"]["collated_cells"] != 223
    ):
        failures.append({"kind": "canping_fire_coverage"})
    wood_root = ROOT / "tests/fixtures/canping_wood_v1"
    wood_reference = json.loads((wood_root / "reference.json").read_text())
    wood_literal = wood_root / wood_reference["literal_file"]
    if (
        summary["source_pdf_sha256"] != wood_reference["source_pdf_sha256"]
        or hashlib.sha256(wood_literal.read_bytes()).hexdigest()
        != wood_reference["literal_sha256"]
    ):
        failures.append({"kind": "canping_wood_source_identity"})
    for image in wood_reference["images"]:
        if (
            hashlib.sha256((wood_root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                {"kind": "canping_wood_page_identity", "case": image["file"]}
            )
    wood_rows = list(
        csv.DictReader(wood_literal.open(encoding="utf-8"), delimiter="\t")
    )
    wood_states = {
        (r["number"], r["kind"]): r["state"]
        for r in wood_reference["expected_special_states"]
    }
    wood_headers = {r["number"] for r in wood_reference["number_reading_uncertainties"]}
    wood_native_root = ROOT / "tests/fixtures/canping_wood_rereading_v1"
    wood_native_reference = json.loads(
        (wood_native_root / "reference.json").read_text()
    )
    wood_native_cells = {
        (c["number"], c["kind"]): c for c in wood_native_reference["cells"]
    }
    for file, digest in (
        (
            wood_native_reference["literal_file"],
            wood_native_reference["literal_sha256"],
        ),
        (
            wood_native_reference["source_manifest_file"],
            wood_native_reference["source_manifest_sha256"],
        ),
    ):
        if hashlib.sha256((wood_native_root / file).read_bytes()).hexdigest() != digest:
            failures.append({"kind": "canping_wood_native_identity", "case": file})
    wood_native_witnesses = [
        w
        for w in summary["additional_rereading_witnesses"]
        if w["fixture_id"] == wood_native_reference["fixture_id"]
    ]
    expected_wood_pages = [
        {
            **{k: p[k] for k in ("pdf_page", "image_service_url", "canvas_dimensions")},
            "regions": [
                {k: r[k] for k in ("region", "url", "sha256")} for r in p["regions"]
            ],
        }
        for p in wood_native_reference["pages"]
    ]
    if (
        len(wood_native_witnesses) != 1
        or wood_native_witnesses[0]["pages"] != expected_wood_pages
        or wood_native_witnesses[0]["resolved_cells"] != 3
        or wood_native_witnesses[0]["still_uncertain_cells"] != 1
        or len(wood_native_cells) != 4
        or wood_native_reference["native_region_count"] != 16
        or wood_native_reference["reused_region_count"] != 8
        or wood_native_reference["new_stored_region_count"] != 8
        or set(wood_native_cells)
        != {
            (r["number"], r["kind"])
            for r in wood_reference["uncertain_cells"]
            if r["number"] not in wood_headers
        }
        or any(
            wood_native_reference[k] != 0
            for k in (
                "new_numbered_cells_examined",
                "new_independent_reviews",
                "new_classical_birth_examples",
                "new_independent_calendar_instants",
                "new_real_world_outcomes",
            )
        )
    ):
        failures.append({"kind": "canping_wood_native_scope"})
    for page in wood_native_reference["pages"]:
        if {tuple(r["region"]) for r in page["regions"]} != {
            (0, 0, 2950, 2200),
            (2950, 0, 2950, 2200),
            (0, 2200, 2950, 2200),
            (2950, 2200, 2950, 2200),
        }:
            failures.append(
                {
                    "kind": "canping_wood_native_region_coverage",
                    "case": page["pdf_page"],
                }
            )
        for region in page["regions"]:
            if hashlib.sha256(
                (wood_native_root / region["file"]).read_bytes()
            ).hexdigest() != region["sha256"] or region["reused_prior_region"] != (
                page["pdf_page"] in (84, 86)
            ):
                failures.append(
                    {
                        "kind": "canping_wood_native_region_identity",
                        "case": region["file"],
                    }
                )
    wood_uncertain = 0
    for row in wood_rows:
        for kind in ("male", "female", "luck"):
            number = int(row["number"])
            revision = wood_native_cells.get((number, kind))
            expected = (
                revision["state"]
                if revision
                else wood_states.get((number, kind), "source_cell_visually_collated")
            )
            wood_uncertain += expected == "source_reading_uncertain"
            selected = canping_lookup_record("木", number, kind)
            s = selected["selection"]
            if revision and (
                s.get("reading_revision", {}).get("previous_text") != row[kind]
                or s["reading_revision"].get("previous_collation_version") != "1.8.0"
                or s["reading_revision"].get("rereading_id")
                != wood_native_reference["fixture_id"]
            ):
                failures.append(
                    {"kind": "canping_wood_native_revision", "case": [number, kind]}
                )
            if (
                selected["text"] != (revision["text"] if revision else row[kind])
                or s["number"] != number
                or s["cell_status"] != expected
                or s.get("source_pdf_page") != int(row["pdf_page"])
                or (
                    number in wood_headers
                    and (
                        s.get("number_attribution_status")
                        != "provisional_inherited_key"
                        or not s.get("number_reading_uncertainties")
                        or expected != "source_reading_uncertain"
                    )
                )
            ):
                failures.append({"kind": "canping_wood_cell", "case": [number, kind]})
    if (
        len(wood_rows) != 78
        or wood_uncertain != 13
        or len(wood_headers) != 4
        or summary["part_coverage"]["木"]["collated_cells"] != 221
    ):
        failures.append({"kind": "canping_wood_coverage"})
    earth_root = ROOT / "tests/fixtures/canping_earth_v1"
    earth_reference = json.loads((earth_root / "reference.json").read_text())
    earth_literal = earth_root / earth_reference["literal_file"]
    if (
        summary["source_pdf_sha256"] != earth_reference["source_pdf_sha256"]
        or hashlib.sha256(earth_literal.read_bytes()).hexdigest()
        != earth_reference["literal_sha256"]
    ):
        failures.append({"kind": "canping_earth_source_identity"})
    for image in earth_reference["images"]:
        if (
            hashlib.sha256((earth_root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                {"kind": "canping_earth_page_identity", "case": image["file"]}
            )
    earth_rows = list(
        csv.DictReader(earth_literal.open(encoding="utf-8"), delimiter="\t")
    )
    earth_states = {
        (r["number"], r["kind"]): r["state"]
        for r in earth_reference["expected_special_states"]
    }
    earth_headers = {
        r["number"] for r in earth_reference["number_reading_uncertainties"]
    }
    earth_native_root = ROOT / "tests/fixtures/canping_earth_rereading_v1"
    earth_native_reference = json.loads(
        (earth_native_root / "reference.json").read_text()
    )
    earth_native_cells = {
        (c["number"], c["kind"]): c for c in earth_native_reference["cells"]
    }
    for file, digest in (
        (
            earth_native_reference["literal_file"],
            earth_native_reference["literal_sha256"],
        ),
        (
            earth_native_reference["glyph_reference_file"],
            earth_native_reference["glyph_reference_sha256"],
        ),
        (
            earth_native_reference["source_manifest_file"],
            earth_native_reference["source_manifest_sha256"],
        ),
    ):
        if (
            hashlib.sha256((earth_native_root / file).read_bytes()).hexdigest()
            != digest
        ):
            failures.append({"kind": "canping_earth_native_identity", "case": file})
    earth_native_witnesses = [
        w
        for w in summary["additional_rereading_witnesses"]
        if w["fixture_id"] == earth_native_reference["fixture_id"]
    ]
    expected_earth_pages = [
        {
            **{k: p[k] for k in ("pdf_page", "image_service_url", "canvas_dimensions")},
            "regions": [
                {k: r[k] for k in ("region", "url", "sha256")} for r in p["regions"]
            ],
        }
        for p in earth_native_reference["pages"]
    ]
    if (
        len(earth_native_witnesses) != 1
        or earth_native_witnesses[0]["pages"] != expected_earth_pages
        or earth_native_witnesses[0]["resolved_cells"] != 1
        or earth_native_witnesses[0]["still_uncertain_cells"] != 2
        or len(earth_native_cells) != 3
        or earth_native_reference["native_region_count"] != 12
        or earth_native_reference["reused_region_count"] != 0
        or earth_native_reference["new_stored_region_count"] != 12
        or set(earth_native_cells)
        != {
            (int(r["number"]), r["kind"])
            for r in earth_reference["expected_special_states"]
            if r["state"] == "source_reading_uncertain"
        }
        or any(
            earth_native_reference[k] != 0
            for k in (
                "new_numbered_cells_examined",
                "new_independent_reviews",
                "new_classical_birth_examples",
                "new_independent_calendar_instants",
                "new_real_world_outcomes",
            )
        )
    ):
        failures.append({"kind": "canping_earth_native_scope"})
    for page in earth_native_reference["pages"]:
        if {tuple(r["region"]) for r in page["regions"]} != {
            (0, 0, 2950, 2200),
            (2950, 0, 2950, 2200),
            (0, 2200, 2950, 2200),
            (2950, 2200, 2950, 2200),
        }:
            failures.append(
                {
                    "kind": "canping_earth_native_region_coverage",
                    "case": page["pdf_page"],
                }
            )
        for region in page["regions"]:
            if (
                hashlib.sha256(
                    (earth_native_root / region["file"]).read_bytes()
                ).hexdigest()
                != region["sha256"]
                or region["reused_prior_region"] is not False
            ):
                failures.append(
                    {
                        "kind": "canping_earth_native_region_identity",
                        "case": region["file"],
                    }
                )
    for comparison in earth_native_reference["comparison_cells"]:
        result = canping_lookup_record(
            comparison["element"], comparison["number"], comparison["kind"]
        )
        if (
            result["text"] != comparison["text"]
            or result["selection"]["cell_status"] != comparison["state"]
            or "reading_revision" in result["selection"]
            or comparison["text_changed"]
            or comparison["prior_state_changed"]
        ):
            failures.append({"kind": "canping_earth_comparison_unchanged"})
    if (
        earth_native_reference["reviewed_previous_clear_cells"] != 1
        or earth_native_reference["corrected_previously_clear_cells"] != 0
        or len(earth_native_reference["withdrawn_draft_readings"]) != 1
    ):
        failures.append({"kind": "canping_earth_draft_withdrawal"})
    earth_uncertain = 0
    for row in earth_rows:
        for kind in ("male", "female", "luck"):
            number = int(row["number"])
            revision = earth_native_cells.get((number, kind))
            expected = (
                revision["state"]
                if revision
                else earth_states.get((number, kind), "source_cell_visually_collated")
            )
            earth_uncertain += expected == "source_reading_uncertain"
            selected = canping_lookup_record("土", number, kind)
            s = selected["selection"]
            if revision and (
                s.get("reading_revision", {}).get("previous_text") != row[kind]
                or s["reading_revision"].get("previous_cell_status")
                != "source_reading_uncertain"
                or s["reading_revision"].get("previous_collation_version") != "1.10.0"
                or s["reading_revision"].get("rereading_id")
                != earth_native_reference["fixture_id"]
                or s["reading_revision"].get("source_pdf_page") != int(row["pdf_page"])
            ):
                failures.append(
                    {"kind": "canping_earth_native_revision", "case": [number, kind]}
                )
            if (
                selected["text"] != (revision["text"] if revision else row[kind])
                or s["number"] != number
                or s["cell_status"] != expected
                or s.get("source_pdf_page") != int(row["pdf_page"])
                or (
                    number in earth_headers
                    and (
                        s.get("number_attribution_status")
                        != "provisional_inherited_key"
                        or not s.get("number_reading_uncertainties")
                        or expected != "source_reading_uncertain"
                    )
                )
            ):
                failures.append({"kind": "canping_earth_cell", "case": [number, kind]})
    if (
        len(earth_rows) != 78
        or earth_uncertain != 2
        or len(earth_headers) != 0
        or summary["part_coverage"]["土"]["collated_cells"] != 232
    ):
        failures.append({"kind": "canping_earth_coverage"})
    if (
        summary["collated_cells"] != 1123
        or summary["unresolved_reading_cells"] != 47
        or summary["unexamined_cells"] != 0
        or summary["pending_cells"] != 47
        or summary["numbered_table_visual_review_complete"] is not True
        or summary["numbered_table_clear_readings_complete"] is not False
    ):
        failures.append({"kind": "canping_global_coverage_and_completion"})
    return {
        **summary,
        "checks_passed": not failures,
        "failures": failures,
        "primary_witness_pages": sorted(
            {
                page["pdf_page"]
                for ref in (
                    reference,
                    water_reference,
                    gold_reference,
                    fire_reference,
                    wood_reference,
                    earth_reference,
                )
                for page in ref["images"]
            }
        ),
        "literal_cells_compared": count,
        "water_cells_examined": len(water_rows) * 3,
        "water_cells_with_unambiguous_readings": 224,
        "water_cells_with_unresolved_readings": uncertain_cells,
        "water_previously_collated_cells_reused": 6,
        "water_initial_review_new_unambiguous_cells": 188,
        "water_rereading_previously_uncertain_cells": 40,
        "water_rereading_resolved_cells": 30,
        "water_rereading_still_uncertain_cells": 10,
        "water_rereading_new_numbered_cells": 0,
        "water_rereading_new_independent_reviews": 0,
        "water_native_region_count": 28,
        "native_number_headers_reexamined": 6,
        "native_number_headers_resolved": 0,
        "native_number_headers_still_uncertain": 6,
        "native_header_regions": 20,
        "native_header_review_new_confirmed_cells": 0,
        "native_header_review_new_independent_reviews": 0,
        "provisional_header_bodies_readable": 14,
        "provisional_header_bodies_printed_blank": 1,
        "provisional_header_bodies_printed_partial_blank": 1,
        "provisional_header_bodies_still_uncertain": 2,
        "gold_cells_examined": len(gold_rows) * 3,
        "gold_cells_with_unambiguous_readings": 223,
        "gold_cells_with_unresolved_readings": gold_uncertain,
        "gold_initial_review_new_unambiguous_cells": 219,
        "gold_native_previously_uncertain_cells": 15,
        "gold_native_resolved_cells": 4,
        "gold_native_still_uncertain_cells": 11,
        "gold_native_regions": 28,
        "gold_native_reused_regions": 0,
        "gold_native_new_numbered_cells": 0,
        "gold_native_new_independent_reviews": 0,
        "gold_number_body_pairing_differences": len(
            gold_reference["numbered_content_correspondence"]
        ),
        "gold_pairing_difference_cause_established": False,
        "gold_computational_numbers_remapped": False,
        "gold_review_is_blind_or_independent": False,
        "fire_cells_examined": len(fire_rows) * 3,
        "fire_cells_with_unambiguous_readings": 223,
        "fire_cells_with_unresolved_readings": fire_uncertain,
        "fire_previously_collated_cells_reused": 4,
        "fire_initial_review_new_unambiguous_cells": 213,
        "fire_native_previously_uncertain_cells": 11,
        "fire_native_resolved_cells": 6,
        "fire_native_still_uncertain_cells": 5,
        "fire_native_regions": 24,
        "fire_native_reused_regions": 8,
        "fire_native_new_numbered_cells": 0,
        "fire_native_new_independent_reviews": 0,
        "fire_provisional_number_headers": sorted(fire_headers),
        "fire_cells_under_provisional_headers": len(fire_headers) * 3,
        "fire_review_is_blind_or_independent": False,
        "wood_cells_examined": len(wood_rows) * 3,
        "wood_cells_with_unambiguous_readings": 221,
        "wood_cells_with_unresolved_readings": wood_uncertain,
        "wood_previously_collated_cells_reused": 0,
        "wood_initial_review_new_unambiguous_cells": 218,
        "wood_native_previously_uncertain_cells": 4,
        "wood_native_resolved_cells": 3,
        "wood_native_still_uncertain_cells": 1,
        "wood_native_regions": 16,
        "wood_native_reused_regions": 8,
        "wood_native_new_numbered_cells": 0,
        "wood_native_new_independent_reviews": 0,
        "wood_provisional_number_headers": sorted(wood_headers),
        "wood_cells_under_provisional_headers": len(wood_headers) * 3,
        "wood_review_is_blind_or_independent": False,
        "inherited_corpus_reader_isolated": inherited_cache_isolated,
        "earth_cells_examined": len(earth_rows) * 3,
        "earth_cells_with_unambiguous_readings": 232,
        "earth_cells_with_unresolved_readings": earth_uncertain,
        "earth_previously_collated_cells_reused": 3,
        "earth_initial_review_new_unambiguous_cells": 228,
        "earth_native_previously_uncertain_cells": 3,
        "earth_native_resolved_cells": 1,
        "earth_native_still_uncertain_cells": 2,
        "earth_native_clear_comparison_cells_unchanged": 1,
        "earth_native_corrected_previously_clear_cells": 0,
        "earth_native_regions": 12,
        "earth_native_reused_regions": 0,
        "earth_native_new_numbered_cells": 0,
        "earth_native_new_independent_reviews": 0,
        "earth_review_is_blind_or_independent": False,
        "comparison_cells_examined": witness_summary["cells_examined"],
        "comparison_clear_readings": witness_summary["clear_readings"],
        "comparison_uncertain_readings": witness_summary["uncertain_readings"],
        "comparison_water_cells_examined": len(witness_rows),
        "comparison_water_clear_readings": water_witness["clear_readings"],
        "comparison_water_uncertain_readings": water_witness["uncertain_readings"],
        "comparison_registered_counterpart_cells": witness_summary[
            "registered_counterpart_cells"
        ],
        "comparison_registered_counterpart_keys": witness_summary[
            "registered_counterpart_keys"
        ],
        "comparison_ambiguous_counterpart_keys": witness_summary[
            "ambiguous_counterpart_keys"
        ],
        "comparison_unmatched_observed_cells": witness_summary[
            "unmatched_observed_cells"
        ],
        "comparison_primary_count_increase": 0,
        "water_review_is_blind_or_independent": False,
        "unreachable_inherited_part_headers": unreachable,
        "active_headers_arithmetically_reachable": not active_invalid,
        "unresolved_printed_special_number": 2869,
        "special_unreachable_in_elements": special_unreachable,
        "all_printed_numbers_reachable": not active_invalid
        and len(special_unreachable) < len(raw["parts"]),
        "independent_second_review_completed": False,
        "new_classical_birth_examples": 0,
        "new_independent_calendar_instants": 0,
    }


def seasonal_conditions_checks() -> dict:
    root = ROOT / "tests/fixtures/numerology_nlc_v1"
    manifest = json.loads((root / "seasonal-manifest.json").read_text())
    reference = json.loads((root / "seasonal-reference.json").read_text())
    failures = []
    if (
        manifest["pdf_sha256"] != SOURCE_SHA256
        or reference["source_pdf_sha256"] != SOURCE_SHA256
    ):
        failures.append({"kind": "seasonal_source_identity"})
    for page in manifest["images"]:
        if (
            hashlib.sha256((root / page["file"]).read_bytes()).hexdigest()
            != page["sha256"]
        ):
            failures.append(
                {"kind": "seasonal_source_image_identity", "case": page["file"]}
            )
    for case in reference["pattern_cases"]:
        result = seasonal_number_evidence(case["tian"], case["di"], None)
        if result["matched_pattern_ids"] != case["ids"]:
            failures.append({"kind": "literal_numerical_pattern", "case": case})
    for case in reference["season_cases"]:
        result = seasonal_number_evidence(
            case["tian"], case["di"], datetime.fromisoformat(case["at"])
        )
        active = {
            w["rule_id"]: w["numeric_band_match"]
            for w in result["seasonal_windows"]
            if w["active"]
        }
        declared = [
            (w["rule_id"], w["start_term"], w["end_term"])
            for w in result["seasonal_windows"]
        ]
        if active != case["active"] or declared != [
            (w["id"], w["start"], w["end"]) for w in reference["windows"]
        ]:
            failures.append({"kind": "seasonal_source_window", "case": case})
    hko = json.loads(
        (ROOT / "tests/fixtures/calendar_hko_v1/reference.json").read_text()
    )
    boundary_count = 0
    for window in reference["windows"]:
        for term, states in (
            (window["start"], [False, True]),
            (window["end"], [True, False]),
        ):
            for case in hko["cases"]:
                if case["term"] != term:
                    continue
                anchor = datetime.fromisoformat(case["at"])
                observed = []
                for minutes in (-2, 2):
                    result = seasonal_number_evidence(
                        31, 34, anchor + timedelta(minutes=minutes)
                    )
                    observed.append(
                        next(
                            w["active"]
                            for w in result["seasonal_windows"]
                            if w["rule_id"] == window["id"]
                        )
                    )
                boundary_count += 1
                if observed != states:
                    failures.append(
                        {
                            "kind": "seasonal_hko_boundary",
                            "rule": window["id"],
                            "case": case,
                        }
                    )
    return {
        "checks_passed": not failures
        and len(manifest["images"]) == 11
        and len(reference["formulas"]) == 11
        and len(reference["pattern_cases"]) == 22
        and len(reference["season_cases"]) == 7
        and boundary_count == 36,
        "failures": failures,
        "source_pdf_pages": list(range(64, 75)),
        "literal_numerical_rules": 11,
        "rule_derived_pattern_probes": 22,
        "rule_derived_season_probes": 7,
        "seasonal_window_count": 6,
        "hko_external_boundary_brackets": boundary_count,
        "new_classical_worked_horoscopes": 0,
        "overlaps_resolved": False,
        "complete_seasonal_judgment": False,
    }


def canping_luck_checks() -> dict:
    root = ROOT / "tests/fixtures/canping_najda_v1"
    manifest = json.loads((root / "manifest.json").read_text())
    reference = json.loads((root / "reference.json").read_text())
    failures = []
    if (
        manifest["pdf_sha256"] != CANPING_SOURCE_SHA256
        or reference["source_pdf_sha256"] != CANPING_SOURCE_SHA256
    ):
        failures.append({"kind": "canping_source_identity"})
    for witness in manifest["images"]:
        if (
            hashlib.sha256((root / witness["file"]).read_bytes()).hexdigest()
            != witness["sha256"]
        ):
            failures.append(
                {"kind": "canping_source_image_identity", "case": witness["file"]}
            )
    birth = datetime(2000, 1, 15, 12, tzinfo=timezone.utc)
    for case in reference["rounding"]:
        if (
            appendix_age(birth, birth + timedelta(days=case["days"]))["whole_years"]
            != case["years"]
        ):
            failures.append({"kind": "canping_appendix_rounding", "case": case})
    for case in reference["directions"]:
        at = datetime.fromisoformat(
            "1990-06-15T09:33:00+08:00"
            if case["year"] == "庚午"
            else "1991-09-15T09:33:00+08:00"
        )
        timeline = luck_timeline(
            at, case["gender"], tuple(case["month"]), "Asia/Shanghai", APPENDIX
        )
        if (
            timeline["start_details"]["forward_direction"] != case["forward"]
            or timeline["periods"][0]["pillar"] != case["first"]
        ):
            failures.append({"kind": "canping_appendix_direction", "case": case})
    anchor = reference["modern_hko_anchor"]
    at = datetime.fromisoformat(anchor["birth"])
    args = dict(
        date=at.date().isoformat(),
        time=at.time().isoformat(),
        zone="Asia/Shanghai",
        gender=anchor["gender"],
        use_true_solar_time=False,
    )
    result = build_canping_result(**args)
    if (
        result["canping_timing"]["start_at"] != anchor["start_at"]
        or result["dayun"][0]["pillar"] != anchor["first"]
    ):
        failures.append({"kind": "canping_hko_rule_derived_anchor"})
    for case in reference["query_cases"]:
        selected = build_canping_result(**args, analysis_datetime=case["at"])[
            "canping_timing"
        ]["selected"]
        if (
            selected["dayun_pillar"],
            selected["ganzhi"],
            selected["numShun"],
            selected["numNi"],
        ) != (case["dayun_pillar"], case["ganzhi"], case["num_shun"], case["num_ni"]):
            failures.append({"kind": "canping_actual_boundary_query", "case": case})
    return {
        "checks_passed": not failures
        and len(reference["rounding"]) == 10
        and len(reference["directions"]) == 4
        and len(reference["query_cases"]) == 2
        and len(manifest["images"]) == 3,
        "failures": failures,
        "source_pdf_sha256": CANPING_SOURCE_SHA256,
        "source_url": CANPING_SOURCE_URL,
        "source_pages": [50, 105, 106],
        "rule_derived_rounding_cases": 10,
        "rule_derived_direction_cases": 4,
        "rule_derived_query_cases": 2,
        "hko_calendar_anchor_count": 1,
        "new_classical_worked_horoscopes": 0,
        "scope": "Named Zi Ping appendix bridge; civil date counting is declared, volume-six unique schedule attribution remains open.",
    }


def najia_checks() -> dict:
    root = ROOT / "tests/fixtures/numerology_nlc_v1"
    source = json.loads((root / "najia-manifest.json").read_text())
    reference = json.loads((root / "najia-reference.json").read_text())
    failures = []
    if (
        source["pdf_sha256"] != SOURCE_SHA256
        or reference["source_pdf_sha256"] != SOURCE_SHA256
    ):
        failures.append({"kind": "najia_source_identity"})
    for witness in source["images"]:
        if (
            hashlib.sha256((root / witness["file"]).read_bytes()).hexdigest()
            != witness["sha256"]
        ):
            failures.append({"kind": "najia_image_identity", "case": witness["file"]})
    qualifier_reference = json.loads(
        (ROOT / "tests/fixtures/heluo_najia_qualifiers_v1/reference.json").read_text()
    )
    foundation_reference = json.loads(
        (ROOT / "tests/fixtures/heluo_najia_foundations_v1/reference.json").read_text()
    )
    cases = (
        reference["cases"]
        + qualifier_reference["najia_cases"]
        + foundation_reference["new_hexagram_entries"]
    )
    for case in cases:
        rows = hexagram_najia(case["lines"])
        if [r["direct"] for r in rows] != case["direct"] or [
            r["borrowed"] for r in rows
        ] != case["borrowed"]:
            failures.append({"kind": "najia_original_assignments", "case": case["gua"]})
    return {
        "checks_passed": len(reference["cases"]) == 5
        and len(qualifier_reference["najia_cases"]) == 3
        and len(foundation_reference["new_hexagram_entries"]) == 5
        and len(source["images"]) == 5
        and not failures,
        "failures": failures,
        "direct_assignments_compared": sum(len(c["direct"]) for c in cases),
        "borrowed_assignments_compared": sum(
            len(r) for c in cases for r in c["borrowed"]
        ),
        "hexagrams_directly_collated": [c["gua"] for c in cases],
        "source_pdf_pages": [c.get("pdf_page", c.get("page")) for c in cases],
        "new_direct_assignments_compared": 30,
        "other_hexagrams_not_individually_collated": 51,
        "other_hexagrams_status": "rule_derived_not_individually_collated",
    }


def natal_najia_clause_checks() -> dict:
    """Literal witnesses plus derived phase probes; no connector adjudication."""
    root = ROOT / "tests/fixtures/heluo_najia_qualifiers_v1"
    reference = json.loads((root / "reference.json").read_text())
    collation = json.loads(MONTH_COLLATION_PATH.read_text())
    failures = []
    if reference["source_pdf_sha256"] != SOURCE_SHA256:
        failures.append({"kind": "natal_najia_source_identity"})
    foundation = json.loads(
        (ROOT / "tests/fixtures/heluo_najia_foundations_v1/reference.json").read_text()
    )
    if (
        collation["natal_najia_clauses"]
        != reference["literal_clauses"] + foundation["new_month_najia_clauses"]
    ):
        failures.append({"kind": "natal_najia_literal_binding"})
    for image in reference["images"]:
        if (
            hashlib.sha256((root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                {"kind": "natal_najia_image_identity", "case": image["file"]}
            )
    for clause in reference["literal_clauses"]:
        chart = {phase: {"name": clause["gua"]} for phase in ("xian", "hou")}
        for month in range(1, 13):
            result = month_affinity(chart, MONTH_BRANCHES[month - 1], MONTH_GUA)
            for phase in result["phases"]:
                actual = phase["natal_najia_clause"]
                if (
                    actual["literal"] != clause["literal"]
                    or actual["source_pdf_page"] != clause["page"]
                    or actual["month_label_match"] != (month in clause["month_numbers"])
                    or actual["najia"] is not None
                    or actual["match"] is not None
                    or actual["qualifier_status"] != "not_evaluated_missing_najia"
                ):
                    failures.append(
                        {
                            "kind": "natal_najia_month_probe",
                            "case": clause["id"],
                            "month": month,
                        }
                    )
    for case in reference["najia_cases"]:
        pillars = dict(year=case["direct"][0], month="丁卯", day="庚申", hour="庚辰")
        chart = heluo(
            four_pillars={**pillars, "year": "甲子"},
            gender="男",
            birth_year=1924,
            month_zhi="卯",
            hour_zhi="辰",
        )
        # Only these three source-transcribed six-line tables are injected.
        for phase in ("xian", "hou"):
            chart[phase].update(name=case["gua"], lines=case["lines"])
        actual = heluo_judge(chart, pillars, "酉")
        for phase in actual["month_affinity"]["phases"]:
            clause = phase["natal_najia_clause"]
            if (
                clause["najia"]["matches"] != [{"pos": 1, "kind": "direct"}]
                or clause["match"] is not None
            ):
                failures.append(
                    {"kind": "natal_najia_actual_phase_probe", "case": case["gua"]}
                )
    zero_keys = (
        "new_independent_calendar_instants",
        "new_classical_birth_examples",
        "new_real_world_outcomes",
        "new_independent_reviews",
        "new_source_images",
        "new_borrowed_assignments_collated",
    )
    if any(reference[k] != 0 for k in zero_keys):
        failures.append({"kind": "natal_najia_inflated_evidence_counts"})
    return {
        "checks_passed": len(reference["literal_clauses"]) == 9
        and len(reference["najia_cases"]) == 3
        and not failures,
        "failures": failures,
        "literal_clauses_registered": len(reference["literal_clauses"]),
        "total_literal_clauses_registered": len(collation["natal_najia_clauses"]),
        "previous_window_clauses_reused": reference["previous_window_clauses_reused"],
        "newly_registered_clause_contexts": reference[
            "newly_registered_clause_contexts"
        ],
        "rule_derived_month_label_probes": 108,
        "actual_najia_phase_context_probes": 6,
        "new_direct_assignments_collated": reference["new_direct_assignments_collated"],
        "reused_source_images": len(reference["images"]),
        **{k: reference[k] for k in zero_keys},
        "connector_scope_resolved": False,
        "jie_natal_month_exception_resolved": False,
        "unresolved_source_order": reference["unresolved_source_order"],
        "complete_detime_or_xie_assessment": False,
    }


def najia_foundation_checks() -> dict:
    root = ROOT / "tests/fixtures/heluo_najia_foundations_v1"
    reference = json.loads((root / "reference.json").read_text())
    summary = najia_collation_summary()
    failures = []
    if reference["source_pdf_sha256"] != SOURCE_SHA256:
        failures.append({"kind": "najia_foundation_source_identity"})
    for image in reference["images"]:
        if (
            hashlib.sha256((root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                {"kind": "najia_foundation_image_identity", "case": image["file"]}
            )
    manifest = reference["najda_manifest"]
    if (
        hashlib.sha256((root / manifest["file"]).read_bytes()).hexdigest()
        != manifest["sha256"]
    ):
        failures.append({"kind": "najia_foundation_manifest_identity"})
    for case in reference["hexagram_entries"]:
        actual = annotate_positions(
            case["gua"], case["lines"], hexagram_najia(case["lines"])
        )
        if any(
            r["source"]["basis"] != "hexagram_entry"
            or r["source"]["source_pdf_page"] != case["page"]
            for r in actual["lines"]
        ):
            failures.append(
                {"kind": "najia_direct_source_binding", "case": case["gua"]}
            )
    bases = {tuple(p["bits"]): p for p in reference["pure_tables"]}
    from itertools import product

    from fatebridge.core.heluo import lines_to_gua

    for bits in product((0, 1), repeat=6):
        lines = list(bits)
        actual = annotate_positions(
            lines_to_gua(lines)["name"], lines, hexagram_najia(lines)
        )
        for row in actual["lines"]:
            pos = row["pos"]
            base = bases[tuple(lines[:3] if pos <= 3 else lines[3:])]
            if (
                row["direct"] != base["direct"][pos - 1]
                or row["borrowed"] != base["borrowed"][pos - 1]
            ):
                failures.append(
                    {"kind": "najia_component_application", "case": lines, "pos": pos}
                )
    for output_key, expected in (
        ("pure_trigram_tables", 8),
        ("pure_table_assignment_slots", 48),
        ("pure_table_borrowed_slots", 12),
        ("directly_collated_hexagrams", 13),
        ("direct_assignment_observations", 78),
        ("borrowed_assignment_observations", 18),
        ("other_hexagrams_not_individually_collated", 51),
    ):
        if summary[output_key] != expected:
            failures.append({"kind": "najia_evidence_counts", "case": output_key})
    if (
        summary["source_order_issues"] != reference["order_issues"]
        or summary["complete_assessment"] is not False
    ):
        failures.append({"kind": "najia_order_issue_or_complete_claim"})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "collation": summary,
        "new_direct_assignment_observations": 30,
        "new_borrowed_assignment_observations": 0,
        "rule_derived_hexagram_applications": 64,
        "rule_derived_positional_comparisons": 384,
        "new_named_month_najia_clauses": 4,
        "unquantified_timing_najia_clauses": reference[
            "unquantified_timing_najia_clauses"
        ],
        "new_primary_source_images": 1,
        "new_independent_reviews": 0,
        "new_classical_birth_examples": 0,
        "new_calendar_instants": 0,
        "new_real_world_outcomes": 0,
    }


def hko_calendar_checks() -> dict:
    root = ROOT / "tests/fixtures/calendar_hko_v1"
    reference = json.loads((root / "reference.json").read_text())
    failures = []
    for source in reference["sources"]:
        if (
            hashlib.sha256((root / source["file"]).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            failures.append({"kind": "hko_source_identity", "case": source["file"]})
    terms = {
        year: {
            t.name: t.moment
            for t in get_solar_terms_for_year(year, reference["timezone"])
        }
        for year in {c["year"] for c in reference["cases"]}
    }
    errors = []
    for case in reference["cases"]:
        error = abs(
            (
                terms[case["year"]][case["term"]] - datetime.fromisoformat(case["at"])
            ).total_seconds()
        )
        errors.append(error)
        if error > reference["tolerance_seconds"]:
            failures.append(
                {"kind": "hko_calendar", "case": case, "error_seconds": error}
            )
    return {
        "checks_passed": len(errors) == 72 and not failures,
        "failures": failures,
        "years": sorted(terms),
        "term_count": len(errors),
        "max_error_seconds": max(errors) if errors else None,
        "tolerance_seconds": reference["tolerance_seconds"],
        "source_page": reference["source_page"],
    }


def timing_checks() -> dict:
    root = ROOT / "tests/fixtures/numerology_nlc_v1"
    source = json.loads((root / "manifest.json").read_text())
    reference = json.loads((root / "timing-reference.json").read_text())
    failures = []
    direct_count = 0
    derived_count = 0
    if source["pdf_sha256"] != SOURCE_SHA256:
        failures.append({"kind": "source_pdf_identity"})
    for witness in source["images"]:
        if (
            hashlib.sha256((root / witness["file"]).read_bytes()).hexdigest()
            != witness["sha256"]
        ):
            failures.append({"kind": "source_image_identity", "case": witness["file"]})
    for case in reference["annual"]:
        rows = annual_sequence(
            case["base_lines"], case["period_pos"], case["start_yang"]
        )
        direct_count += len(case["names"])
        if (
            [r["gua"] for r in rows] != case["names"]
            or [r["pos"] for r in rows] != case["positions"]
            or [r["changed_pos"] for r in rows] != case["changed_positions"]
        ):
            failures.append({"kind": "annual_sequence", "case": case["id"]})
    case = reference["monthly"]
    rows = monthly_sequence(case["annual_lines"], case["annual_pos"])
    direct_count += len(case["names"])
    if [r["gua"] for r in rows] != case["names"] or [r["pos"] for r in rows] != case[
        "positions"
    ]:
        failures.append({"kind": "monthly_sequence"})
    case = reference["daily"]
    rows = daily_template(case["month_lines"], case["month_pos"])
    for group in ("explicit_blocks", "rule_derived_blocks"):
        for block in case[group]:
            selected = rows[block["slots"][0] - 1 : block["slots"][1]]
            count = block["slots"][1] - block["slots"][0] + 1
            if group == "explicit_blocks":
                direct_count += count
            else:
                derived_count += count
            if (
                len(selected) != count
                or {r["gua"] for r in selected} != {block["name"]}
                or {r["changed_pos"] for r in selected} != {block["changed_pos"]}
                or [r["pos"] for r in selected] != case["daily_positions_per_block"]
            ):
                failures.append(
                    {"kind": "daily_template", "case": block["slots"], "basis": group}
                )
    nonempty = direct_count == 54 and derived_count == 12 and len(source["images"]) == 4
    return {
        "checks_passed": nonempty and not failures,
        "failures": failures,
        "direct_original_rows_compared": direct_count,
        "rule_derived_rows_compared": derived_count,
        "source_pdf_sha256": source["pdf_sha256"],
    }


def poem_collation_checks() -> dict:
    """Image-backed line groups and poem counts are not birth examples."""
    root = ROOT / "tests/fixtures/heluo_poem_source_v1"
    reference = json.loads((root / "reference.json").read_bytes())
    verified = json.loads((root / "verified-readings.json").read_bytes())
    amendments = json.loads((root / "amendments.json").read_bytes())
    summary = poem_collation_summary()
    extension_root = ROOT / "tests/fixtures/heluo_kuntun_poems_v1"
    extension = json.loads((extension_root / "verified-readings-v2.json").read_bytes())
    extended_notes = json.loads((extension_root / "amendments.json").read_bytes())
    failures = []
    for name, digest in (
        ("verified-readings.json", extension["previous_verified_readings_sha256"]),
        ("printed-boundaries.json", extension["printed_boundaries_sha256"]),
        ("punctuation-amendment.json", extension["punctuation_amendment_sha256"]),
        ("draft-transcription.json", extension["draft_sha256"]),
        ("amendments.json", extension["amendments_sha256"]),
        *((w["file"], w["sha256"]) for w in extension["images"]),
    ):
        if hashlib.sha256((extension_root / name).read_bytes()).hexdigest() != digest:
            failures.append({"kind": "kuntun_poem_witness_identity", "file": name})
    for name, digest in (
        ("reference.json", verified["source_reference_sha256"]),
        ("draft-transcription.json", verified["draft_sha256"]),
        *((w["file"], w["sha256"]) for w in reference["images"]),
    ):
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            failures.append({"kind": "poem_witness_identity", "file": name})
    if (
        summary["source_pdf_sha256"] != reference["source_pdf_sha256"]
        or summary["source_pdf_sha256"] == SOURCE_SHA256
        or (
            summary["collated_line_poem_groups"],
            summary["pending_line_poem_groups"],
            summary["collated_individual_poems"],
            summary["total_individual_poems"],
        )
        != (48, 336, 117, None)
    ):
        failures.append({"kind": "poem_source_or_count_units"})
    for entry in [*verified["entries"], *extension["entries"]]:
        text = yao_text(entry["hexagram"], entry["line"])
        if text is None or (
            text["poem_sections"]
            != [dict(p, applicability=None) for p in entry["poems"]]
            or text["shige"] != "\n".join(p["text"] for p in entry["poems"])
            or text["text_provenance"]["poem_pdf_pages"] != entry["pdf_pages"]
            or text["text_provenance"]["poem_status"]
            != "source_poems_visually_collated"
            or text["poem_selection"]["selected_poem_indices"] != []
            or text["poem_selection"]["automatic_selection"] is not False
            or "unverified" not in text["inherited_xiang_reference"]["status"]
        ):
            failures.append({"kind": "poem_group_fidelity", "line": entry["line"]})
    for entry in amendments["source_specific_lexical_differences"]:
        text = yao_text("乾為天", entry["line"])
        if text is None or (
            entry["adopted"] not in text["shige"]
            or entry["inherited"] not in text["text_provenance"]["inherited_shige"]
        ):
            failures.append({"kind": "poem_source_difference", "entry": entry})
    for entry in extended_notes["source_specific_differences"]:
        text = yao_text(entry["hexagram"], entry["line"])
        if text is None or (
            entry["adopted"] not in text["shige"]
            or entry["inherited"] not in text["text_provenance"]["inherited_shige"]
        ):
            failures.append({"kind": "kuntun_poem_source_difference", "entry": entry})
    boundaries = json.loads((extension_root / "printed-boundaries.json").read_bytes())
    for entry in extension["entries"]:
        text = yao_text(entry["hexagram"], entry["line"])
        if text is None:
            failures.append(
                {
                    "kind": "poem_printed_boundary_missing",
                    "case": [entry["hexagram"], entry["line"]],
                }
            )
            continue
        for index, poem in enumerate(text["poem_sections"]):
            expected = boundaries["clause_lengths"][entry["hexagram"]][
                entry["line"] - 1
            ][index]
            if [len(clause) for clause in poem["printed_clauses"]] != expected:
                failures.append(
                    {
                        "kind": "poem_printed_boundary",
                        "case": [entry["hexagram"], entry["line"], index + 1],
                    }
                )
    from fatebridge.core.heluo import _tiaowen

    # The retained literal poem readings come from the reviewed source pages.
    CURRENT_POEMS = json.loads(
        (ROOT / "tests/data/heluo/poem-collation-v1.json").read_bytes()
    )
    reviewed = {(e["hexagram"], e["line"]) for e in CURRENT_POEMS["entries"]}
    pending_count = 0
    for gua in _tiaowen():
        for pos in range(1, 7):
            if (gua, pos) in reviewed:
                continue
            pending = yao_text(gua, pos)
            if (
                pending["text_provenance"]["poem_status"]
                != "inherited_poem_source_unverified"
                or "poem_sections" in pending
            ):
                failures.append(dict(kind="poem_unreviewed_control", gua=gua, line=pos))
            pending_count += 1
    if len(reviewed) != 48 or len(_tiaowen()) != 64 or pending_count != 336:
        failures.append(dict(kind="poem_reviewed_and_pending_control_scope"))
    return {
        **summary,
        "checks_passed": not failures,
        "failures": failures,
        "pending_poem_controls_checked": pending_count,
        "source_specific_lexical_differences": len(
            amendments["source_specific_lexical_differences"]
        )
        + len(extended_notes["source_specific_differences"]),
        "new_batch_draft_withdrawals": len(extended_notes["draft_withdrawals"]),
        "independent_second_reviews": 0,
        "original_birth_examples_added": 0,
        "astronomical_reference_instants_added": 0,
        "real_world_observations_added": 0,
    }


def birth_fold_checks() -> dict:
    """One reused HKO minute anchor plus two region/offset occurrences."""
    root = ROOT / "tests/fixtures/numerology_birth_fold_v1"
    reference = json.loads((root / "reference.json").read_bytes())
    failures = []
    for source in reference["source_files"]:
        if (
            hashlib.sha256((root / source["path"]).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            failures.append(
                {"kind": "birth_fold_source_identity", "path": source["path"]}
            )
    anchor = reference["anchor"]
    at = next(
        t.moment for t in get_solar_terms_for_year(2021, "+08:00") if t.name == "立冬"
    )
    error = abs(
        (
            at.astimezone(timezone.utc)
            - datetime.fromisoformat(anchor["at"]).astimezone(timezone.utc)
        ).total_seconds()
    )
    if error > anchor["tolerance_seconds"]:
        failures.append(
            {"kind": "birth_fold_reused_hko_anchor", "error_seconds": error}
        )
    base = {
        k: reference[k]
        for k in ("date", "time", "zone", "gender", "use_true_solar_time")
    }
    rows = []
    for name, build in (
        ("heluo", build_heluo_result),
        ("canping", build_canping_result),
    ):
        for case in reference["cases"]:
            result = build(**base, birth_utc_offset=case["birth_utc_offset"])
            clock = result["numerology_evidence"]["birth_clock"]
            actual = {
                "tool": name,
                "requested_utc_offset": case["birth_utc_offset"],
                "utc": clock["birth_instant_utc"],
                "fold": clock["civil_fold"],
                "month": "".join(
                    result["four_pillars"]["month"][k] for k in ("stem", "branch")
                ),
                "zone": clock["timezone_spec"],
            }
            if (actual["utc"], actual["fold"], actual["month"], actual["zone"]) != (
                case["utc"],
                case["fold"],
                case["month"],
                base["zone"],
            ):
                failures.append({"kind": "birth_fold_occurrence", "actual": actual})
            if name == "canping":
                timing = result["canping_timing"]
                actual.update(
                    start_at=timing["start_at"],
                    whole_years=timing["calendar_offset"]["whole_years"],
                )
                if (actual["start_at"], actual["whole_years"]) != (
                    case["appendix_start_at"],
                    case["appendix_whole_years"],
                ):
                    failures.append(
                        {"kind": "birth_fold_luck_boundary", "actual": actual}
                    )
            rows.append(actual)
        for change in (
            {},
            {"birth_utc_offset": "-03:00"},
            {
                "date": "1990-04-15",
                "time": "02:30",
                "zone": "Asia/Shanghai",
                "birth_utc_offset": "+09:00",
            },
        ):
            try:
                build(**{**base, **change})
            except ValueError:
                continue
            failures.append(
                {
                    "kind": "birth_fold_invalid_clock_accepted",
                    "tool": name,
                    "change": change,
                }
            )
    return {
        "checks_passed": len(rows) == 4 and not failures,
        "failures": failures,
        "occurrences_per_tool": 2,
        "rows": rows,
        "hko_error_seconds": error,
        "reused_published_minute_anchors": 1,
        "astronomical_reference_instants_added": 0,
        "new_original_birth_examples": 0,
        "real_world_observations_added": 0,
        "whole_history_accuracy_established": False,
        "scope": "Confirmed offsets select birth instants under retained regional rules; unknown folds and gaps remain invalid. Future boundaries use archived rules, not a promise of future legislation.",
    }


def canping_schedule_basis_checks() -> dict:
    """Bounded source excerpts and profile-specific application, not outcomes."""
    from fatebridge.core.canping_schedule_basis import source_readings

    root = ROOT / "tests/fixtures/canping_schedule_basis_v1"
    reference = json.loads((root / "reference.json").read_bytes())
    readings = json.loads((root / "verified-readings.json").read_bytes())
    runtime = source_readings()
    runtime.pop("_file_sha256")
    failures = []
    if runtime != readings:
        failures.append({"kind": "canping_schedule_readings_mismatch"})
    for witness in reference["source_files"]:
        if (
            hashlib.sha256((root / witness["file"]).read_bytes()).hexdigest()
            != witness["sha256"]
        ):
            failures.append(
                {"kind": "canping_schedule_image_identity", "file": witness["file"]}
            )
    rows = []
    for profile, applied in (
        ("bazi_appendix_v1", ["appendix_month_order", "appendix_integer_rounding"]),
        ("bazi_continuous_v1", ["appendix_month_order"]),
        ("legacy_minggong_v1", []),
    ):
        value = build_canping_result(
            date="2021-11-07",
            time="00:30",
            zone="America/Havana",
            birth_utc_offset="-05:00",
            gender="男",
            use_true_solar_time=False,
            dayun_method=profile,
        )
        timing = value["canping_timing"]
        basis = timing["schedule_basis"]
        if basis["applied_clause_ids"] != applied or any(
            (c["role"] == "applied_rule") != (c["id"] in applied)
            for c in basis["clauses"]
        ):
            failures.append(
                {"kind": "canping_schedule_source_application", "profile": profile}
            )
        if profile == "legacy_minggong_v1":
            coherent = (
                timing["first_period"] is None and not basis["has_actual_date_mapping"]
            )
        else:
            coherent = (
                timing["first_period"] == value["dayun"][0]
                and basis["actual_start_at"] == timing["start_at"]
                and len(value["liunian_series"]["year_boundaries"]) == 121
            )
        if not coherent:
            failures.append(
                {"kind": "canping_schedule_actual_context", "profile": profile}
            )
        rows.append(
            {
                "profile": profile,
                "applied_clause_ids": basis["applied_clause_ids"],
                "has_actual_date_mapping": basis["has_actual_date_mapping"],
            }
        )
    return {
        "checks_passed": len(rows) == 3
        and len(readings["clauses"]) == 6
        and not failures,
        "failures": failures,
        "bounded_source_excerpts": 6,
        "target_appendix_excerpts": 4,
        "supplementary_book_excerpts": 2,
        "target_excerpt_ten_year_step_explicitly_collated": False,
        "profile_rows": rows,
        "new_original_birth_examples": 0,
        "new_independent_second_reviews": 0,
        "new_astronomical_observations": 0,
        "real_world_observations_added": 0,
        "whole_book_alignment_established": False,
        "scope": "Supplementary Zi Ping wording does not replace missing explicit wording in the target appendix. Modern dates and inherited legacy scheduling are separately attributed.",
    }


def canping_legacy_year_label_checks() -> dict:
    """Reuse a published minute to test labels, without certifying UTC mapping."""
    root = ROOT / "tests/fixtures/canping_legacy_year_labels_v1"
    reference = json.loads((root / "reference.json").read_bytes())
    source = reference["reused_calendar_source"]
    failures = []
    if (
        hashlib.sha256((root / source["file"]).read_bytes()).hexdigest()
        != source["sha256"]
    ):
        failures.append({"kind": "legacy_year_calendar_source_identity"})
    rows = []
    for case in reference["cases"]:
        arguments = {
            k: v for k, v in case.items() if k not in {"id", "year", "year_pillar"}
        }
        value = build_canping_result(
            **arguments, gender="男", dayun_method="legacy_minggong_v1"
        )
        series = value["liunian_series"]
        first = series["rows"][0]
        pillar = value["four_pillars"]["year"]
        if (
            pillar["stem"] + pillar["branch"] != case["year_pillar"]
            or (first["year"], first["ganzhi"], first["taisuiBranch"])
            != (case["year"], case["year_pillar"], case["year_pillar"][1])
            or series["birth_pillar_year"] != case["year"]
            or series["year_boundary"] != "lichun_year_labels_only"
            or [row["year"] for row in series["rows"]]
            != list(range(case["year"], case["year"] + 120))
            or any("start_at" in row or "end_at" in row for row in series["rows"])
            or value["canping_timing"]["first_period"] is not None
            or value["canping_timing"]["schedule_basis"]["has_actual_date_mapping"]
        ):
            failures.append({"kind": "legacy_year_label_coherence", "case": case["id"]})
        if case["id"] == "january":
            expected = reference["january_manual_number"]
            if (first["numShun"], first["numNi"]) != (
                expected["num_shun"],
                expected["num_ni"],
            ):
                failures.append({"kind": "legacy_year_hand_derived_numbers"})
        rows.append(
            {
                "case": case["id"],
                "first_year": first["year"],
                "ganzhi": first["ganzhi"],
                "num_shun": first["numShun"],
                "num_ni": first["numNi"],
            }
        )
    return {
        "checks_passed": len(rows) == 6 and not failures,
        "failures": failures,
        "rows": rows,
        "calendar_source_reused": True,
        "new_original_birth_examples": 0,
        "new_independent_astronomical_observations": 0,
        "new_independent_source_reviews": 0,
        "new_real_world_observations": 0,
        "legacy_utc_mapping_certified": False,
        "scope": "First-year Tai Sui and 120 nominal year labels follow the already declared Li Chun birth year. Inherited luck ages and UTC intervals remain unverified.",
    }


def canping_relative_year_checks() -> dict:
    """Relative Tai Sui and explicit age slots; no invented Gregorian epoch."""
    from fatebridge.core.canping import liunian_series

    root = ROOT / "tests/fixtures/canping_relative_years_v1"
    reference = json.loads((root / "reference.json").read_bytes())
    failures = []
    for image in (reference["image"], reference["previous_verse_image"]):
        if (
            hashlib.sha256((root / image["file"]).read_bytes()).hexdigest()
            != image["sha256"]
        ):
            failures.append(
                {"kind": "canping_substitution_source_image", "file": image["file"]}
            )
    relative = liunian_series(**reference["fixed_pillars"])
    anchored = liunian_series(**reference["fixed_pillars"], birth_year=1984)
    for age, expected in reference["relative_years"].items():
        row = relative["rows"][int(age) - 1]
        if (row["year"], row["ganzhi"], row["taisuiBranch"]) != (
            None,
            expected,
            expected[1],
        ):
            failures.append({"kind": "canping_relative_year", "age": age})
    for row in relative["rows"][:2]:
        if row["status"] != "not_started" or any(
            k in row for k in ("numShun", "numNi", "verses", "dayunBranch")
        ):
            failures.append(
                {"kind": "canping_relative_before_start", "age": row["age"]}
            )
    for expected in reference["manual_numbers"]:
        row = relative["rows"][expected["age"] - 1]
        if (row["numShun"], row["numNi"]) != (expected["num_shun"], expected["num_ni"]):
            failures.append(
                {"kind": "canping_relative_manual_number", "age": expected["age"]}
            )
    if any(
        {k: v for k, v in a.items() if k != "year"}
        != {k: v for k, v in b.items() if k != "year"}
        for a, b in zip(relative["rows"], anchored["rows"])
    ):
        failures.append({"kind": "canping_relative_anchor_disagreement"})
    extension = json.loads((root / "extension-control.json").read_bytes())["control"]
    extended = liunian_series(
        **reference["fixed_pillars"],
        start_age=extension["age"],
        end_age=extension["age"],
    )["rows"][0]
    if (
        extended["year"],
        extended["ganzhi"],
        extended["numShun"],
        extended["numNi"],
    ) != (None, extension["ganzhi"], extension["num_shun"], extension["num_ni"]):
        failures.append({"kind": "canping_relative_extension"})
    actual = build_canping_result(
        date="2021-11-07",
        time="00:30",
        zone="America/Havana",
        birth_utc_offset="-05:00",
        gender="男",
        dayun_method="legacy_minggong_v1",
        use_true_solar_time=False,
    )
    trace = next(
        r["facts"]
        for r in actual["numerology_evidence"]["rule_trace"]
        if r["rule_id"] == "canping_luck_substitution_v1"
    )
    if (
        trace["bounded_excerpts"] != reference["bounded_excerpts"]
        or trace["source_pdf_page"] != 64
        or trace["source_pdf_sha256"] != reference["source_pdf"]["sha256"]
        or trace["query_pair"] is not None
    ):
        failures.append({"kind": "canping_substitution_explanation_receipt"})
    return {
        "checks_passed": not failures,
        "failures": failures,
        "relative_rows": len(relative["rows"]),
        "newly_archived_primary_page_images": 1,
        "bounded_source_excerpts": 2,
        "default_horizon_and_explicit_relative_extension_preserved": True,
        "new_original_birth_examples": 0,
        "new_independent_astronomical_observations": 0,
        "new_independent_source_reviews": 0,
        "new_real_world_observations": 0,
        "scope": "The selected book's explanatory paragraph supports the annual Tai Sui/luck-branch pair. Fixed-pillar relative cycles and explicit age-slot consistency are tested without choosing a Gregorian century or certifying the inherited schedule or UTC intervals.",
    }


def month_source_profile_checks() -> dict:
    """Keep reproduction and literal within-edition disagreement separate."""
    module = runpy.run_path(
        str(ROOT / "scripts/numerology/audit_heluo_month_profiles.py")
    )
    return module["audit"]()


def sui17_meng4_source_checks() -> dict:
    """Reproduce the selected printings without certifying uncertain glyphs."""
    from fatebridge.core import heluo_poems as hp
    from fatebridge.core import heluo_texts as ht
    from fatebridge.services.knowledge import calculate_knowledge_read

    root = ROOT / "tests/fixtures/heluo_sui17_meng4_v1"
    verified = json.loads((root / "verified-readings.json").read_bytes())
    freeze = json.loads((root / "source-reading-freeze.json").read_bytes())
    failures = []

    if (
        hashlib.sha256((root / "verified-readings.json").read_bytes()).hexdigest()
        != freeze["final_verified_sha256"]
    ):
        failures.append(dict(kind="sui_meng_final_reading_identity"))
    first = json.loads((root / "first-draft-freeze.json").read_bytes())
    if first["inherited_target_text_exposed"] is not False:
        failures.append(dict(kind="sui_meng_first_draft_exposure"))
    for name, expected in first["files"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            failures.append(dict(kind="sui_meng_first_draft_identity", file=name))
    for entry in verified["commentaries"]:
        text = yao_text("澤雷隨", entry["line"])
        sections = [
            dict(section, text=section["text"].replace("无", "無"), applicability=None)
            for section in entry["sections"]
        ]
        if (
            text["yaoci"] != entry["yaoci"]
            or text["commentary_sections"] != sections
            or text["detail"] != "".join(section["text"] for section in sections)
            or text["commentary_branch_selection"]["selected_section_ids"]
        ):
            failures.append(dict(kind="sui17_complete_conditions", line=entry["line"]))
        if [sections[i]["condition_label"] for i in [1, 2]] != ["叶者", "不叶者"]:
            failures.append(dict(kind="sui17_original_ye_form", line=entry["line"]))
    poem_notes = {
        (2, 1): [
            "所選詩訣底本原字納婿，繼承稿作納婦；這是具名底本讀文，不據性別自動代選詩或婚配條款。"
        ],
        (2, 2): ["原像素讀作牛途，未按熟語改半途；所指未裁定。"],
        (4, 1): ["有河開按所見保留，未用另一熟語改舟開。"],
        (6, 1): [
            "原字尋清楚，四八尋所指未定，不改四八春，不據此生成具體年齡或日期；繼承稿此句本已作尋，不計生產修復。"
        ],
    }
    for entry in verified["poems"]:
        text = yao_text("山水蒙", entry["line"])
        expected_poems = []
        for poem in entry["poems"]:
            expected = dict(poem, applicability=None)
            if (entry["line"], poem["index"]) in poem_notes:
                expected["reading_notes"] = poem_notes[(entry["line"], poem["index"])]
            expected_poems.append(expected)
        if (
            text["poem_sections"] != expected_poems
            or text["shige"] != "\n".join(poem["text"] for poem in entry["poems"])
            or text["poem_selection"]["selected_poem_indices"]
        ):
            failures.append(dict(kind="meng4_complete_poems", line=entry["line"]))
    for key, label in [
        ("雷地豫:2", "注文"),
        ("雷地豫:4", "爻辞"),
        ("澤雷隨:6", "注文"),
        ("澤雷隨:5", None),
    ]:
        lines = "\n".join(calculate_knowledge_read(domain="heluo", key=key)["lines"])
        if ("字形未决" in lines) != (label is not None) or (
            label and f"{label}字形未决：" not in lines
        ):
            failures.append(dict(kind="knowledge_summary_uncertainty_scope", key=key))
    initial = json.loads((root / "case-selection-result.json").read_bytes())
    extension = json.loads((root / "case-selection-extension-result.json").read_bytes())
    if (
        len(initial["all_target_keys_found"]) != 11
        or initial["candidates_evaluated"] != 4320
        or not extension["original_failed_plan_retained"]
    ):
        failures.append(dict(kind="sui_meng_initial_search_failure_lost"))
    return dict(
        checks_passed=not failures,
        failures=failures,
        new_examined_headers=6,
        new_examined_commentaries=6,
        new_poem_groups=6,
        new_individual_poems=13,
        unresolved_new_prose_glyphs=1,
        independent_second_review_completed=False,
        new_original_horoscopes=0,
        new_calendar_instants=0,
        new_real_world_outcomes=0,
        scope="Selected printing readings by the main reader only. Old prefixes preserved. Initial 11/12 search failure retained; extension gives12 composite engineering cases. Glyph uncertainty remains in full record and summary, personal applicability unassessed.",
    )


def audit() -> dict:
    """Run current bounded source/arithmetic checks without historical source replay."""
    checks = {
        "birth_timezone_checks": birth_timezone_checks(),
        "birth_clock_checks": birth_clock_checks(),
        "heluo_solar_context_checks": heluo_solar_context_checks(),
        "yuanqi_opposition_checks": yuanqi_opposition_checks(),
        "phase_qi_checks": phase_qi_checks(),
        "song_qi_source_checks": song_qi_source_checks(),
        "tongtian_source_checks": tongtian_source_checks(),
        "song_clock_source_checks": song_clock_source_checks(),
        "historical_caption_checks": historical_caption_checks(),
        "worked_example_checks": worked_example_checks(),
        "line_condition_checks": line_condition_checks(),
        "support_clause_checks": support_clause_checks(),
        "body_structure_checks": body_structure_checks(),
        "pillar_link_source_checks": pillar_link_source_checks(),
        "body_relation_checks": body_relation_checks(),
        "month_and_clock_checks": month_and_clock_checks(),
        "yaoci_collation_checks": yaoci_collation_checks(),
        "jiehou_source_checks": jiehou_source_checks(),
        "source_clock_checks": source_clock_checks(),
        "xusong_commentary_checks": xusong_commentary_checks(),
        "shibi_commentary_checks": shibi_commentary_checks(),
        "xiaochuli_commentary_checks": xiaochuli_commentary_checks(),
        "taipi_commentary_checks": taipi_commentary_checks(),
        "commentary_collation_checks": commentary_collation_checks(),
        "yuantang_scan_checks": yuantang_scan_checks(),
        "canping_text_checks": canping_text_checks(),
        "seasonal_conditions_checks": seasonal_conditions_checks(),
        "canping_luck_checks": canping_luck_checks(),
        "najia_checks": najia_checks(),
        "natal_najia_clause_checks": natal_najia_clause_checks(),
        "najia_foundation_checks": najia_foundation_checks(),
        "hko_calendar_checks": hko_calendar_checks(),
        "timing_checks": timing_checks(),
        "poem_collation_checks": poem_collation_checks(),
        "birth_fold_checks": birth_fold_checks(),
        "canping_schedule_basis_checks": canping_schedule_basis_checks(),
        "canping_legacy_year_label_checks": canping_legacy_year_label_checks(),
        "canping_relative_year_checks": canping_relative_year_checks(),
        "month_source_profile_checks": month_source_profile_checks(),
        "sui17_meng4_source_checks": sui17_meng4_source_checks(),
    }
    return {
        "checks": checks,
        "calculation_checks_passed": all(
            row.get("checks_passed", False) for row in checks.values()
        ),
        "three_dimension_acceptance_passed": False,
        "four_dimension_acceptance_passed": False,
        "scope": "Finite current calculation and source-reading checks; full corpus, independent review and predictive validity remain unestablished.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-four-dimensions", action="store_true")
    parser.add_argument("--require-three-dimensions", action="store_true")
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")
    if not report["calculation_checks_passed"]:
        return 1
    if (
        args.require_three_dimensions
        and not report["three_dimension_acceptance_passed"]
    ):
        return 2
    return (
        2
        if args.require_four_dimensions
        and not report["four_dimension_acceptance_passed"]
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
