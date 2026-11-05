"""Reproduce bounded specialty-chart evidence without assigning authority scores."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import re
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.birth_clock import resolve_solar_birth_clock
from fatebridge.core.astro.day_meridian import day_meridian_coordinates
from fatebridge.core.astro.fictitious_elements import fictitious_element_source
from fatebridge.core.astro.geometry import _sector13_for_longitude
from fatebridge.core.astro.midpoints import _native_factors, midpoint_geometry
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.seven_planets import seven_planet_view
from fatebridge.core.astro.solar_arc import solar_arc_state
from fatebridge.core.astro.time_scales import (
    datetime_from_ut1,
    ephemeris_time,
    tt_from_ut1,
    ut1_from_tt,
)
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)
from scripts.replay_witte_meridian_sources import FIXTURE as WITTE_1923_FIXTURE
from scripts.replay_witte_meridian_sources import (
    FIXTURE_SHA256 as WITTE_1923_FIXTURE_SHA256,
)
from scripts.replay_witte_meridian_sources import replay as replay_witte_sources

ROOT = Path(__file__).resolve().parents[1]


def reference_check() -> dict:
    fixture = json.loads((ROOT / "tests/fixtures/uranian-witte-2026.json").read_text())
    records = []
    for row in fixture["rows"]:
        moment = datetime.fromisoformat(row["utc"])
        birth = build_astro_birth_info(
            birth_year=moment.year,
            birth_month=moment.month,
            birth_day=moment.day,
            birth_hour=0,
            birth_timezone="UTC",
            birth_longitude=0,
            birth_latitude=0,
        )
        factors = {p["id"]: p for p in _native_factors(birth, False)["factors"]}
        for name, value in row["positions"].items():
            expected = (
                value["sign_index"] * 30
                + value["degree"]
                + value["minute"] / 60
                + value["second"] / 3600
            )
            actual = factors[name]["longitude"]
            error = abs((actual - expected + 180) % 360 - 180) * 3600
            records.append(
                {
                    "utc": row["utc"],
                    "factor": name,
                    "kind": factors[name]["kind"],
                    "error_arcseconds": error,
                    "tolerance_arcseconds": value["tolerance_arcseconds"],
                    "within_tolerance": error <= value["tolerance_arcseconds"],
                }
            )
    return {
        "reference_count": len(records),
        "passed": sum(r["within_tolerance"] for r in records),
        "source_pdf_sha256": fixture["source_pdf_sha256"],
        "source_url": fixture["source_url"],
        "tolerance_policy": fixture["tolerance_policy"],
        "scope": fixture["scope"],
        "comparisons": records,
    }


def sector_check() -> dict:
    rng = random.Random(430231)
    edges = [Fraction(360 * n, 13) for n in range(14)]
    tested = 0
    failed = []
    for anchor in (0.0, 17.25, 121.4667, math.nextafter(360.0, 0.0), -180.0):
        probes = [rng.uniform(-720, 720) for _ in range(500)]
        for boundary in edges:
            cusp = float(Fraction(anchor) + boundary)
            probes.extend(
                [math.nextafter(cusp, -math.inf), cusp, math.nextafter(cusp, math.inf)]
            )
        for value in probes:
            tested += 1
            expected = bisect_right(edges, (Fraction(value) - Fraction(anchor)) % 360)
            if _sector13_for_longitude(value, anchor) != expected:
                failed.append(
                    {"anchor": anchor, "longitude": value, "expected": expected}
                )
    return {
        "probe_count": tested,
        "failed": failed,
        "source": "independent exact interval search on represented float values",
    }


def geometry_check() -> dict:
    rng = random.Random(13981)
    values = {str(i): rng.uniform(-400, 700) for i in range(9)}
    result = midpoint_geometry(values)
    checks = []
    for dial in (90, 45):

        def error(doubled: float) -> float:
            phi = math.pi * doubled / dial
            return abs(math.atan2(math.sin(phi), math.cos(phi))) * dial / (2 * math.pi)

        expected_two = set()
        expected_three = set()
        expected_four = set()
        pairs = list(combinations(values, 2))
        for a, b in pairs:
            # Point-to-point equations do not use the doubled midpoint angle.
            phase = 2 * math.pi * (values[a] - values[b]) / dial
            direct_error = (
                abs(math.atan2(math.sin(phase), math.cos(phase))) * dial / (2 * math.pi)
            )
            if direct_error <= 1:
                expected_two.add(tuple(sorted((a, b))))
            for p in values:
                if (
                    p not in (a, b)
                    and error(2 * values[p] - values[a] - values[b]) <= 1
                ):
                    expected_three.add((p, a, b))
        for (a, b), (c, d) in combinations(pairs, 2):
            if (
                len({a, b, c, d}) == 4
                and error(values[a] + values[b] - values[c] - values[d]) <= 1
            ):
                expected_four.add((a, b, c, d))
        actual = result["dials"][str(dial)]
        checks.append(
            {
                "dial": dial,
                "two_factor_set_matches": {
                    (r["id_a"], r["id_b"]) for r in actual["two_factor_contacts"]
                }
                == expected_two,
                "three_factor_set_matches": {
                    (r["point"], r["id_a"], r["id_b"])
                    for r in actual["three_factor_contacts"]
                }
                == expected_three,
                "four_factor_set_matches": {
                    (r["id_a"], r["id_b"], r["id_c"], r["id_d"])
                    for r in actual["four_factor_contacts"]
                }
                == expected_four,
                "expected_two_count": len(expected_two),
                "expected_three_count": len(expected_three),
                "expected_four_count": len(expected_four),
            }
        )
    return {
        "reference": "independent direct point-pair and doubled-angle midpoint trigonometric equations",
        "unique_two_factor_pair_count": result["unique_two_factor_pair_count"],
        "two_factor_source_sections": "Rudolph 1979 laws 13 and 16; geometry only, no source-authored numeric birth cases or event outcomes added",
        "checks": checks,
    }


def source_example_check() -> dict:
    fixture = json.loads(
        (ROOT / "tests/fixtures/uranian-rudolph-1979.json").read_text()
    )
    checks = []
    for case in fixture["cases"]:
        geometry = midpoint_geometry(case["positions"], orb_degrees=0.0)
        matched = True
        for dial in (90, 45):
            rows = [
                r
                for r in geometry["dials"][str(dial)][case["kind"]]
                if r["equation"] == case["equation"]
            ]
            matched &= bool(rows) == (dial in case["expected_dials"])
            if rows:
                matched &= (
                    rows[0]["axis_offset_degrees"] == case["axis_offset_degrees"]
                    and rows[0]["orb"] == 0
                )
        checks.append(
            {
                "case_id": case["id"],
                "source_sections": case["source_sections"],
                "matched": matched,
            }
        )
    return {
        "source_url": fixture["source_url"],
        "source_html_sha256": fixture["source_html_sha256"],
        "case_origin": fixture["case_origin"],
        "source_authored_horoscope_cases": 0,
        "checks": checks,
    }


def symbolic_source_check() -> dict:
    fixture = json.loads(
        (ROOT / "tests/fixtures/uranian-udo-1996-symbolic.json").read_text()
    )
    checks = []
    for case in fixture["cases"]:
        result = midpoint_geometry(case["positions"], orb_degrees=0.0)
        contact = next(
            r
            for r in result["dials"][str(case["midpoint_period"])][
                "four_factor_contacts"
            ]
            if r["equation"] == case["midpoint_equation"]
        )
        point = contact["sensitive_point"]
        matched = (
            point["longitude"] == case["expected_point"]
            and point["period_degrees"] == case["expected_sensitive_period"]
            and point["occupancy"] == case["expected_occupancy"]
            and ("source_interpretation" in contact) == case["source_reading_allowed"]
        )
        checks.append({"case_id": case["id"], "matched": matched})
    regression = seven_planet_view(
        [{"id": "Sun", "longitude": 0.0}, {"id": "Moon", "longitude": 180.00001}]
    )
    midpoint = regression["midpoints"][0]["longitude"]
    return {
        "source_url": fixture["source_url"],
        "source_pdf_sha256": fixture["source_pdf_sha256"],
        "locator": fixture["locator"],
        "source_authored_symbolic_examples": 1,
        "source_authored_numerical_horoscopes": 0,
        "numeric_witness_origin": fixture["numeric_witness_origin"],
        "checks": checks,
        "near_antipodal_regression": {
            "actual": midpoint,
            "expected": 270.000005,
            "matched": abs(midpoint - 270.000005) < 1e-12,
        },
    }


def sensitivity_check() -> dict:
    payload = {
        "name": "虚构：生时敏感性审计",
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 4,
        "birth_minute": 30,
        "birth_timezone": "UTC",
        "birth_longitude": 0.0,
        "birth_latitude": 0.0,
        "birth_time_uncertainty_minutes": 10.0,
    }
    germany = calculate_germany_chart_analysis(**payload)["midpoint_analysis"]
    sensitivity = germany["time_sensitivity"]
    orbs = []
    for sample in sensitivity["samples"]:
        values = sample["factor_longitudes"]
        phase = math.radians(
            values["Mars"] + values["Jupiter"] - values["Zeus"] - values["Midheaven"]
        )
        orbs.append(abs(math.degrees(math.atan2(math.sin(phase), math.cos(phase)))))
    present = sum(orb <= 2 for orb in orbs)
    pattern = sensitivity["source_pattern"]
    chart13 = calculate_core_chart_analysis(**payload, chart_variant="chart13")
    sectors = chart13["time_sensitivity"]
    sector_replay = True
    for record in sectors["sector_assignments"]:
        independent = [
            math.floor(
                (
                    (
                        s["factor_longitudes"][record["id"]]
                        - s["factor_longitudes"]["Ascendant"]
                    )
                    % 360
                )
                * 13
                / 360
            )
            + 1
            for s in sectors["samples"]
        ]
        sector_replay &= independent == record["sector_by_sample"]
    changed = [
        r["id"] for r in sectors["sector_assignments"] if len(r["observed_sectors"]) > 1
    ]
    return {
        "input_origin": "Explicitly fictional integration stimulus; no person or outcome dataset",
        "uncertainty_minutes": 10,
        "sample_count": sensitivity["sample_count"],
        "independent_source_pattern_replay_matches": present
        == pattern["present_sample_count"],
        "nominal_interpretation_count": len(germany["interpretations"]),
        "sampled_present_count": present,
        "sampled_absent_count": len(orbs) - present,
        "nominal_reading_has_counterexamples_inside_declared_samples": 0
        < present
        < len(orbs),
        "sector_assignment_independent_replay_matches": sector_replay,
        "sector_factors_with_sampled_changes": changed,
        "maximum_recorded_sample_gap_seconds": sensitivity[
            "maximum_recorded_sample_gap_seconds"
        ],
        "continuous_interval_proven": False,
        "sample_frequency_is_probability": False,
        "scope": "Factors, one source pattern and equal13 assignments only; no full contact-set stability or outcome inference",
    }


def solar_arc_check() -> dict:
    fixture = json.loads(
        (ROOT / "tests/fixtures/uranian-solar-arc-horizons.json").read_text()
    )
    expected = {r["utc"]: r["apparent_ecliptic_longitude"] for r in fixture["rows"]}
    comparisons = []
    for case in fixture["cases"]:
        start = datetime.fromisoformat(case["birth_utc"])
        profile = solar_arc_state(
            start,
            ephemeris_time(start).jd_tt,
            datetime.fromisoformat(case["analysis_utc"]),
        )
        first, last = expected[case["birth_utc"]], expected[case["progressed_utc"]]
        first_error = (
            abs((profile["natal_tropical_sun"] - first + 180) % 360 - 180) * 3600
        )
        last_error = (
            abs((profile["progressed_tropical_sun"] - last + 180) % 360 - 180) * 3600
        )
        arc_error = abs(profile["solar_arc_degrees"] - (last - first) % 360) * 3600
        comparisons.append(
            {
                "birth_utc": case["birth_utc"],
                "analysis_utc": case["analysis_utc"],
                "solar_arc_degrees": profile["solar_arc_degrees"],
                "sun_ephemeris_models": profile["sun_ephemeris_models"],
                "sun_observation_indices": profile["sun_observation_indices"],
                "sun_ephemeris_source": profile["sun_ephemeris_source"],
                "difference_from_one_degree_per_year": profile[
                    "difference_from_one_degree_per_year"
                ],
                "natal_sun_error_arcseconds": first_error,
                "progressed_sun_error_arcseconds": last_error,
                "arc_error_arcseconds": arc_error,
                "matched": max(first_error, last_error)
                <= fixture["position_tolerance_arcseconds"]
                and arc_error <= fixture["arc_tolerance_arcseconds"],
            }
        )
    static = json.loads((ROOT / "tests/fixtures/uranian-al319-static.json").read_text())
    lo, hi = Fraction(959, 2), Fraction(961, 2)
    differences = []
    for row in static["rows"]:

        def minutes(parts):
            return parts[0] * 1800 + parts[1] * 60 + parts[2]

        difference = (minutes(row["directed"]) - minutes(row["natal"])) % 21600
        differences.append(difference)
        lo = max(lo, Fraction(difference - 1))
        hi = min(hi, Fraction(difference + 1))
    return {
        "sun_position_checks": len(comparisons) * 2,
        "true_arc_checks": len(comparisons),
        "comparisons": comparisons,
        "all_sun_and_arc_checks_passed": all(c["matched"] for c in comparisons),
        "reference_collection_mode": fixture["collection_mode"],
        "reference_original_retrieved_at": fixture["retrieved_at"],
        "original_raw_http_bytes_preserved": fixture[
            "original_http_json_bytes_preserved"
        ],
        "reference_transport_limit": "New live NASA requests timed out; existing full decoded NASA response was reparsed, with source-fixture and decoded-table hashes. Original HTTP JSON byte hash could not be reverified because those encoded bytes were not preserved by the older collector.",
        "publisher_static_pairs": len(static["rows"]),
        "publisher_arc_consistent_interval_arcminutes": [float(lo), float(hi)],
        "publisher_static_rounding_intervals_compatible": lo <= hi,
        "publisher_observed_printed_arc_differences_arcminutes": sorted(
            set(differences)
        ),
        "publisher_static_is_date_to_arc_benchmark": False,
        "classical_original_numerical_horoscopes": 0,
        "biwheel_geometry_test_file": "tests/test_other_chart_solar_arc.py; this script does not execute pytest",
        "empirical_outcomes": 0,
    }


def sun_batch_check() -> dict:
    """Exact identity at one instant; not independent positional validation."""
    result = calculate_germany_chart_analysis(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        birth_time_uncertainty_minutes=0,
        analysis_datetime=datetime(2000, 1, 1, 12, tzinfo=timezone.utc),
    )["midpoint_analysis"]["solar_arc_analysis"]
    profile = result["profile"]
    day = result["daily_meridian"]["profile"]
    source = profile["sun_ephemeris_source"]
    return {
        "scope": "Fictional zero-elapsed identity; no independent celestial coordinates or outcome validation",
        "solar_arc_degrees": profile["solar_arc_degrees"],
        "natal_progressed_indices": profile["sun_observation_indices"],
        "target_index": day["target_sun_observation_index"],
        "source": source,
        "zero_arc_and_day_identity_preserved": profile["solar_arc_degrees"] == 0
        and day["upper_meridian_longitude"] == day["natal_upper_meridian_longitude"]
        and day["lower_meridian_longitude"] == day["natal_lower_meridian_longitude"]
        and source["query_count"] == 1
        and profile["sun_observation_indices"] == [0, 0]
        and day["target_sun_observation_index"] == 0,
        "configuration_race_and_progressed_coverage_regressions": "tests/test_other_chart_solar_sources.py; this script does not execute pytest",
        "regressions_executed_by_this_script": False,
    }


def physical_chart_source_check() -> dict:
    """A software source comparison, not an independent position oracle."""
    result = calculate_core_chart_analysis(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        chart_variant="chart13",
        birth_time_uncertainty_minutes=0,
    )
    nominal = result["chart_profile"]["physical_ephemeris_source"]
    sampled = result["time_sensitivity"]["physical_ephemeris_sources"]
    models = {name: row["model"] for name, row in nominal["by_factor"].items()}
    profile = result["chart_profile"]
    native = _native_factors(
        build_astro_birth_info(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=12,
            birth_timezone="UTC",
            birth_longitude=0,
            birth_latitude=0,
        ),
        False,
        include_hypothetical=False,
    )
    native_models = {
        row["model"]
        for row in native["physical_ephemeris_source"]["by_factor"].values()
    }
    node = next(row for row in native["factors"] if row["id"] == "North Node")
    physical_summary = (
        next(iter(set(models.values()))) if len(set(models.values())) == 1 else "mixed"
    )
    model_semantics_match = (
        profile["ephemeris_model"] == physical_summary
        and profile["ephemeris_model_scope"] == "physical_bodies"
        and profile["nonphysical_factor_models"]
        == {"North Node": "swisseph_analytical_mean_node"}
        and native["ephemeris_models"] == sorted(native_models)
        and native["ephemeris_model_scope"] == "physical_bodies"
        and node["model"] == "swisseph_analytical_mean_node"
        and "native_return_flags" in node
    )
    return {
        "scope": "Fictional equal13 chart with a zero-radius birth-time sample; actual native model/source agreement, not an independent celestial or empirical test",
        "nominal_source": nominal,
        "sampled_models_match_nominal": bool(sampled)
        and all(
            {name: row["model"] for name, row in source["by_factor"].items()} == models
            for source in sampled
        ),
        "physical_factor_count": len(models),
        "analytical_node_in_physical_file_trace": "North Node" in models,
        "physical_model_semantics_match_actual_sources": model_semantics_match,
        "physical_model_summary": profile["ephemeris_model"],
        "nonphysical_factor_models": profile["nonphysical_factor_models"],
        "native_physical_models": native["ephemeris_models"],
        "analytical_node": node,
        "mean_node_source_url": "https://github.com/aloistr/swisseph/blob/v2.10.03/swemmoon.c#L1493",
        "model_semantics_regression_file": "tests/test_other_chart_model_semantics.py",
        "strict_jpl_regressions_executed_by_this_script": False,
        "regression_file": "tests/test_other_chart_coordinate_sources.py",
        "concurrency_and_three_surface_regressions_executed_by_this_script": False,
        "atomic_file_read_proven": False,
        "absolute_position_accuracy_certified": False,
    }


def cross_school_model_check() -> dict:
    """Model bookkeeping at one fixed epoch; not an astronomical oracle."""
    from fatebridge.core import guolao, human_design, jyotish
    from fatebridge.core.astro import runtime
    from fatebridge.core.human_design_mechanics import BODY_IDS

    birth = build_astro_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=0,
    )
    india = jyotish.positions(birth)
    hd = human_design.positions_at_tt(india["julian_day_tt"], "mean")
    guolao_raw = guolao.positions(birth)
    guolao_provenance = guolao_raw["ephemeris_provenance"]
    guolao_motion = guolao_raw["longitude_motion"]
    guolao_physical = sorted(
        {
            row[key]
            for row in guolao_provenance["by_body"].values()
            for key in ("ecliptic_model", "equatorial_model")
        }
    )
    expected = "swisseph_analytical_mean_node"
    india_physical = sorted(
        {india["ephemeris_by_body"][name] for name in jyotish.GRAHAS[:7]}
        | {row["ephemeris_model"] for row in india["equatorial"].values()}
    )
    return {
        "scope": "Fictional fixed-epoch model metadata agreement, not an independent celestial or real-world prediction test",
        "india_physical_models": india_physical,
        "india_summary_models": india["ephemeris_models"],
        "india_node_models": india["nonphysical_factor_models"],
        "india_node_return_flags": india["native_node_return_flags"],
        "hd_physical_models": sorted(
            {hd[name]["ephemeris_model"] for name in BODY_IDS}
        ),
        "hd_mean_node_model": hd["NorthNode"]["ephemeris_model"],
        "hd_mean_node_raw_flag_model": hd["NorthNode"]["native_return_flag_model"],
        "hd_mean_node_return_flags": hd["NorthNode"]["return_flags"],
        "guolao_physical_models": guolao_physical,
        "guolao_summary_models": guolao_raw["models"],
        "guolao_provenance": guolao_provenance,
        "guolao_motion_bookkeeping": {
            "reference_frame": guolao_motion["reference_frame"],
            "native_rates_retained": all(
                "longitude_speed_native" in state
                for state in guolao_raw["states"].values()
            ),
            "lunar_light_time_status": guolao_motion["lunar_light_time"]["status"],
            "complete_position_derivative_status": {
                key: value["status"]
                for key, value in guolao_motion["complete_position_derivatives"].items()
            },
            "physical_factors": sorted(
                guolao_motion["physical_ephemeris_source"]["by_factor"]
            ),
            "independent_numeric_reference_compared_here": False,
        },
        "model_semantics_match": (
            india["ephemeris_models"] == india_physical
            and india["ephemeris_model_scope"] == "physical_bodies"
            and india["nonphysical_factor_models"]["Rahu"] == expected
            and hd["NorthNode"]["ephemeris_model"] == expected
            and hd["SouthNode"]["ephemeris_model"] == expected
            and guolao_raw["models"] == guolao_physical
            and guolao_provenance["fixed_star_observer_ephemeris_model"]
            == runtime.ephemeris_model_from_retflag(
                guolao_provenance["fixed_star_observer_return_flags"]
            )
            and not guolao_provenance["absolute_astronomical_accuracy_certified"]
            and guolao_motion["reference_frame"] == "tropical_ecliptic_of_date"
            and set(guolao_motion["physical_ephemeris_source"]["by_factor"])
            == set(guolao.CN)
        ),
        "strict_jpl_and_concurrency_regression_file": "tests/test_other_chart_school_ephemeris_policy.py",
        "strict_jpl_and_concurrency_tests_executed_by_this_script": False,
        "guolao_strict_jpl_regression_file": "tests/test_guolao_ephemeris_policy.py",
        "guolao_strict_jpl_tests_executed_by_this_script": False,
        "guolao_motion_reference_auditor": "scripts/audit_guolao_motion.py",
        "guolao_motion_reference_auditor_executed_by_this_script": False,
        "accuracy_certified": False,
    }


def day_meridian_check() -> dict:
    fixture = json.loads(
        (ROOT / "tests/fixtures/uranian-witte1924-day-meridian.json").read_text()
    )
    case = fixture["example"]

    def angle(parts):
        return Fraction(parts[0] * 1800 + parts[1] * 60 + parts[2], 60)

    arc = Fraction(case["solar_arc_degrees_minutes"][0]) + Fraction(
        case["solar_arc_degrees_minutes"][1], 60
    )
    actual = day_meridian_coordinates(
        float((angle(case["natal_lower_meridian"]) + 180) % 360),
        float(angle(case["natal_tropical_sun"])),
        float(arc),
        float(angle(case["target_tropical_sun"])),
    )
    expected = float(angle(case["printed_lower_meridian"]))
    disagreement = fixture["earlier_source_disagreement"]
    older = float(angle(disagreement["printed_upper_meridian"]))
    error = abs(actual["lower_meridian_longitude"] - expected)
    older_data = WITTE_1923_FIXTURE.read_bytes()
    if hashlib.sha256(older_data).hexdigest() != WITTE_1923_FIXTURE_SHA256:
        raise ValueError("Frozen Witte 1923 transcription checksum mismatch")
    reconciliation = replay_witte_sources(json.loads(older_data))
    return {
        "original_author_printed_arithmetic_cases": 3,
        "distinct_historical_examples": 1,
        "selected_1924_equation_printed_cases": 1,
        "source_url": fixture["source_url"],
        "source_pdf_sha256": fixture["source_pdf_sha256"],
        "source_section": fixture["formula_section"],
        "transcription": fixture["transcription"],
        "scope": fixture["scope"],
        "calculated_lower_meridian": actual["lower_meridian_longitude"],
        "printed_lower_meridian": expected,
        "arithmetic_replay_error_degrees": error,
        "selected_1924_equation_replay_matches": error <= 1e-12,
        "older_printed_upper_meridian": older,
        "older_result_difference_arcminutes": abs(
            older - actual["upper_meridian_longitude"]
        )
        * 60,
        "original_variants_reconciled": False,
        "earlier_source_disagreement_status_at_capture": disagreement["status"],
        "source_disagreement_status": reconciliation["source_disagreement_status"],
        "printed_variant_difference_explained": reconciliation[
            "difference_explained_by_printed_cusp_offset"
        ],
        "source_reconciliation": reconciliation,
        "original_progression_time_key_accepted": False,
        "full_original_numerical_horoscopes_accepted": 0,
        "event_claims_adopted": False,
        "empirical_outcomes": 0,
    }


def meridian_house_check() -> dict:
    from scripts.audit_meridian_house_geometry import (
        geometry_grid,
        read_protocol,
        signed,
        vector_longitude,
    )

    protocol = read_protocol()
    grid = geometry_grid(protocol)
    result = calculate_germany_chart_analysis(
        name="虚构：子午宫表审计",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=0,
        birth_time_uncertainty_minutes=1,
    )
    layer = result["midpoint_analysis"]
    meridian = layer["meridian_houses"]
    profile = meridian["profile"]
    errors = [
        abs(
            signed(
                row["longitude"],
                vector_longitude(row["right_ascension"], profile["true_obliquity"])
                - profile["ayanamsha_apparent"],
            )
        )
        for row in meridian["cusps"]
    ]
    samples = layer["time_sensitivity"]["samples"]
    sampled = []
    for sample in samples:
        for index, longitude in enumerate(sample["meridian_house_cusps"], 1):
            expected = (
                vector_longitude(
                    (sample["meridian_armc"] + (index - 10) * 30) % 360,
                    sample["meridian_obliquity"],
                )
                - sample["meridian_ayanamsha"]
            )
            sampled.append(abs(signed(longitude, expected)))
    passed = (
        grid["passed"]
        and max(errors + sampled) <= protocol["geometry_tolerance_degrees"]
    )
    return {
        "geometric_checks_passed": passed,
        "predeclared_grid": {
            key: value for key, value in grid.items() if key != "rows"
        },
        "actual_nominal_profile": profile,
        "actual_nominal_cusps": meridian["cusps"],
        "actual_nominal_maximum_replay_error_degrees": max(errors),
        "actual_birth_sample_count": len(samples),
        "actual_sample_maximum_replay_error_degrees": max(sampled),
        "first_cusp_replaces_ascendant": False,
        "base_chart_houses_replaced": False,
        "original_printed_table_auditor": "scripts/audit_meridian_house_geometry.py --source-comparison",
        "original_printed_table_comparison_executed_by_this_function": False,
        "full_original_rulebook_accepted": False,
        "empirical_outcomes": 0,
    }


def historical_natal_check() -> dict:
    """Replay the later clock convention without treating it as Witte's record.

    The original minute-rounded positions remain observations to compare, not
    exact astronomical targets to fit. Source disagreements do not disappear
    because the new API correctly transports seconds.
    """
    from fatebridge.core.astro import runtime

    fixture = json.loads(
        (ROOT / "tests/fixtures/uranian-witte1919-natal.json").read_text()
    )
    inputs = fixture["adopted_input"]
    result = calculate_germany_chart_analysis(**inputs)
    layer = result["midpoint_analysis"]
    values = {row["id"]: row["longitude"] for row in layer["factors"]}
    checks = []
    for row in fixture["printed_natal_positions"]:
        printed = row["sign_index"] * 30 + row["degree"] + row["minute"] / 60
        signed_error = (
            float((Fraction(values[row["id"]]) - Fraction(printed) + 180) % 360 - 180)
            * 60
        )
        checks.append(
            {
                "id": row["id"],
                "printed_longitude": printed,
                "computed_longitude": values[row["id"]],
                "signed_difference_arcminutes": signed_error,
                "within_half_printed_unit": abs(signed_error) <= 0.5,
                "within_one_printed_unit": abs(signed_error) <= 1,
            }
        )
    instant = datetime.fromisoformat(fixture["adopted_utc_label"])
    # Conditional arithmetic only: the 1919 passage does not certify whether
    # its local clock is mean/apparent time, nor its minute/second precision.
    literal_local_23 = instant.replace(hour=23, minute=0, second=0)
    conditional_lmt_gmt = literal_local_23 - timedelta(
        seconds=inputs["birth_longitude"] * 240
    )
    jd_ut1 = (
        instant.toordinal()
        + 1721424.5
        + (instant.hour * 3600 + instant.minute * 60 + instant.second) / 86400
    )
    swe = runtime.swe
    theta = math.radians((swe.sidtime(jd_ut1) * 15 + inputs["birth_longitude"]) % 360)
    epsilon = math.radians(swe.calc_ut(jd_ut1, swe.ECL_NUT)[0][0])
    latitude = math.radians(inputs["birth_latitude"])
    expected_mc = (
        math.degrees(math.atan2(math.sin(theta), math.cos(theta) * math.cos(epsilon)))
        % 360
    )
    expected_asc = (
        math.degrees(
            math.atan2(
                math.cos(theta),
                -math.sin(theta) * math.cos(epsilon)
                - math.tan(latitude) * math.sin(epsilon),
            )
        )
        % 360
    )
    angle_errors = {
        "Midheaven": abs(values["Midheaven"] - expected_mc),
        "Ascendant": abs(values["Ascendant"] - expected_asc),
    }
    minute = calculate_germany_chart_analysis(**{**inputs, "birth_second": 0})[
        "midpoint_analysis"
    ]
    minute_values = {row["id"]: row["longitude"] for row in minute["factors"]}
    changes = {}
    for period in ("90", "45"):
        changes[period] = {
            field: len(
                {row["equation"] for row in layer["dials"][period][field]}
                ^ {row["equation"] for row in minute["dials"][period][field]}
            )
            for field in (
                "two_factor_contacts",
                "three_factor_contacts",
                "four_factor_contacts",
            )
        }
    return {
        "original_source": fixture["source"],
        "later_clock_source": fixture["clock_reworking"],
        "adopted_input": inputs,
        "clock_policy_note": fixture["clock_policy_note"],
        "conditional_clock_arithmetic": {
            "assumption": "Literal 23:00 is LMT at the later author's stated 10E; not a verified identification of the original clock basis",
            "conditional_lmt_to_gmt": conditional_lmt_gmt.isoformat(),
            "published_gmt_minus_conditional_lmt_seconds": (
                instant - conditional_lmt_gmt
            ).total_seconds(),
            "later_clock_conversion_certified": False,
            "source_hour_precision_certified_as_exact_minute_or_second": False,
        },
        "source_clock_instant_preserved": result["base_chart"]["person_info"][
            "utc_datetime"
        ]
        == fixture["adopted_utc_label"],
        "native_ut1_equals_independent_gregorian_ordinal": layer["profile"][
            "julian_day_ut1"
        ]
        == jd_ut1,
        "independent_angle_algebra_error_degrees": angle_errors,
        "independent_angle_algebra_matches": all(
            error <= 1e-8 for error in angle_errors.values()
        ),
        "angle_oracle_scope": "Gregorian ordinal plus equatorial/ecliptic geometry using Swiss sidereal time and obliquity, without Swiss house routines; independent plumbing/algebra check, not a separate astronomical ephemeris",
        "mc_change_when_seconds_omitted_arcminutes": float(
            (Fraction(values["Midheaven"]) - Fraction(minute_values["Midheaven"]) + 180)
            % 360
            - 180
        )
        * 60,
        "contact_set_symmetric_difference_when_seconds_omitted": changes,
        "printed_position_comparisons": checks,
        "all_original_printed_positions_within_half_unit": all(
            row["within_half_printed_unit"] for row in checks
        ),
        "all_original_printed_positions_within_one_unit": all(
            row["within_one_printed_unit"] for row in checks
        ),
        "original_rounding_policy": fixture["rounding_policy"],
        "source_disagreement_status": fixture["source_disagreement_status"],
        "numeric_birth_cases_examined": 1,
        "complete_original_numeric_cases_accepted": 0,
        "event_claims_adopted": False,
        "empirical_outcomes": 0,
        "numeric_subset_gate_scope": "API seconds preservation and independent angle algebra only. Known printed-coordinate disagreements remain outside acceptance and are explicitly reported, not repaired by changing time or tolerance.",
    }


def solar_clock_check() -> dict:
    from fatebridge.core.astro import runtime

    roundtrips = []
    for year in (400, 1000, 1600, 1879, 1900, 1959, 1960, 1968, 2000, 2050):
        moment = datetime(year, 5, 14, 22, 20, tzinfo=timezone.utc)
        scales = ephemeris_time(moment)
        restored = datetime_from_ut1(scales.jd_ut1)
        roundtrips.append(
            {
                "utc_carrier": moment.isoformat(),
                "forward_method": scales.method,
                "tt_paths_difference_seconds": (
                    tt_from_ut1(scales.jd_ut1) - scales.jd_tt
                )
                * 86400,
                "inverse_ut1_error_seconds": (ut1_from_tt(scales.jd_tt) - scales.jd_ut1)
                * 86400,
                "utc_roundtrip_error_seconds": (restored - moment).total_seconds(),
            }
        )
    cases = []
    swe = runtime.swe
    for wall, longitude in (
        (datetime(1879, 5, 14, 23), 10.0),
        (datetime(2000, 2, 29, 0, 7, 19), -73.98765),
        (datetime(1960, 7, 1, 12), 0.0),
        (datetime(1000, 1, 2, 0, 7, 19), 180.0),
    ):
        label_jd = (
            wall.toordinal()
            + 1721424.5
            + (wall.hour * 3600 + wall.minute * 60 + wall.second) / 86400
        )
        for basis in ("local_mean_solar", "local_apparent_solar"):
            moment, receipt = resolve_solar_birth_clock(wall, longitude, basis)
            scales = ephemeris_time(moment)
            mean_jd = scales.jd_ut1 + longitude / 360
            if basis == "local_mean_solar":
                error = (mean_jd - label_jd) * 86400
            else:
                # Separate Cartesian ecliptic -> equatorial projection; do not
                # call the production EOT/clock-display helper as its own oracle.
                lon, lat = runtime.ephemeris_call(
                    "calc", scales.jd_tt, swe.SUN, swe.FLG_SWIEPH
                )[0][:2]
                eps = math.radians(
                    runtime.ephemeris_call("calc", scales.jd_tt, swe.ECL_NUT)[0][0]
                )
                lon, lat = math.radians(lon), math.radians(lat)
                ra = (
                    math.degrees(
                        math.atan2(
                            math.sin(lon) * math.cos(lat) * math.cos(eps)
                            - math.sin(lat) * math.sin(eps),
                            math.cos(lon) * math.cos(lat),
                        )
                    )
                    % 360
                )
                ha = (
                    runtime.ephemeris_call("sidtime", scales.jd_ut1) * 15
                    + longitude
                    - ra
                ) % 360
                seconds = (ha * 240 + 43200) % 86400
                expected = wall.hour * 3600 + wall.minute * 60 + wall.second
                error = (seconds - expected + 43200) % 86400 - 43200
            cases.append(
                {
                    "input_wall": wall.isoformat(),
                    "basis": basis,
                    "longitude": longitude,
                    "receipt": receipt,
                    "independent_clock_equation_error_seconds": error,
                    "calendar_day_neighborhood_matches": abs(mean_jd - label_jd) < 0.02,
                    "matched": abs(error) <= 0.0002 and abs(mean_jd - label_jd) < 0.02,
                }
            )
    matched = all(
        abs(row[key]) <= 0.0002
        for row in roundtrips
        for key in (
            "tt_paths_difference_seconds",
            "inverse_ut1_error_seconds",
            "utc_roundtrip_error_seconds",
        )
    )
    return {
        "historical_and_modern_roundtrips": roundtrips,
        "roundtrip_tolerance_seconds": 0.0002,
        "all_roundtrips_match": matched,
        "local_solar_clock_checks": cases,
        "all_local_clock_equations_match": all(row["matched"] for row in cases),
        "oracle_scope": "Shared-model inversion and independent angle algebra; not measured historical Earth rotation or a separate astronomical ephemeris",
        "historical_tidal_policy": "Before1960 Swiss utc_to_jd and jdet_to_utc call deltat_ex with -1; UT1/TT helpers now use the same option. From1960 the explicit SOFA/IERS UTC path retains FLG_SWIEPH.",
        "source_urls": [
            "https://www.astro.com/swisseph/swephprg.htm",
            "https://github.com/aloistr/swisseph/blob/master/swedate.c",
        ],
        "original_oz_basis_disambiguated": False,
        "outcome_based_clock_fitting_performed": False,
        "record_precision_certified": False,
        "new_empirical_outcomes": 0,
    }


def historical_ephemeris_check() -> dict:
    from fatebridge.core.astro import runtime

    fixture = json.loads(
        (ROOT / "tests/fixtures/uranian-historical-horizons.json").read_text()
    )
    checks = []
    swe = runtime.swe
    with runtime.preserve_ephemeris_path():
        swe.set_ephe_path(configured_ephemeris_path() or "")
        physical_trace = PhysicalEphemerisTrace()
        for case in fixture["cases"]:
            raw = case["raw_http_json"].encode("utf-8")
            if hashlib.sha256(raw).hexdigest() != case["raw_http_json_sha256"]:
                raise ValueError("Historical NASA HTTP JSON bytes changed")
            response = json.loads(raw)
            text = response["result"]
            params = case["request_parameters"]
            identity = re.search(
                rf"Target body name:\s+{re.escape(case['body'])}\s+\({case['body_id']}\)",
                text,
            )
            if not (
                identity
                and "GEOCENTRIC" in text
                and "{source: DE441}" in text
                and params["COMMAND"] == f"'{case['body_id']}'"
                and params["TIME_TYPE"] == "'TT'"
                and params["CENTER"] == "'500@399'"
                and params["QUANTITIES"] == "'31'"
            ):
                raise ValueError("Historical NASA target/frame/time definition changed")
            rows = list(
                csv.reader(io.StringIO(text.split("$$SOE\n")[1].split("$$EOE")[0]))
            )
            if len(rows) != 1:
                raise ValueError("Historical NASA epoch count changed")
            moment = datetime.strptime(rows[0][0].strip(), "%Y-%b-%d %H:%M:%S.%f")
            expected = float(rows[0][3])
            if (
                moment != datetime.fromisoformat(case["epoch_tt"])
                or expected != case["apparent_ecliptic_longitude"]
            ):
                raise ValueError("Historical NASA epoch/parsed reference changed")
            # This calendar number labels TT, not UTC or a fitted natal clock.
            jd_tt = (
                moment.toordinal()
                + 1721424.5
                + (moment.hour * 3600 + moment.minute * 60 + moment.second) / 86400
            )
            coordinates, flag = runtime.ephemeris_call(
                "calc", jd_tt, getattr(swe, case["body"].upper()), swe.FLG_SWIEPH
            )
            physical_trace.observe(
                case["body"], runtime.ephemeris_model_from_retflag(flag)
            )
            actual = float(coordinates[0])
            error = ((actual - expected + 180) % 360 - 180) * 3600
            checks.append(
                {
                    "body": case["body"],
                    "epoch_tt": case["epoch_tt"],
                    "julian_day_tt": jd_tt,
                    "reference_longitude": expected,
                    "computed_longitude": actual,
                    "signed_error_arcseconds": error,
                    "tolerance_arcseconds": case["tolerance_arcseconds"],
                    "matched": abs(error) <= case["tolerance_arcseconds"],
                    "actual_ephemeris_model": runtime.ephemeris_model_from_retflag(
                        flag
                    ),
                    "raw_http_json_sha256": case["raw_http_json_sha256"],
                }
            )
        physical_source = physical_trace.finish()
    return {
        "scope": fixture["scope"],
        "reference_frame": fixture["reference_frame"],
        "reference_count": len(checks),
        "passed": sum(row["matched"] for row in checks),
        "all_positions_within_predeclared_tolerance": all(
            row["matched"] for row in checks
        ),
        "checks": checks,
        "selected_search_path": configured_ephemeris_path(),
        "physical_ephemeris_source": physical_source,
        "independence_scope": "Independently retrieved Horizons calculation, not necessarily independent underlying planetary dynamics: Swiss se1 data may use the same DE441 series. File contexts expose the actual DE header edition; no independent outcome validation.",
        "tolerances_predeclared_before_comparison": True,
        "failing_modes_must_not_be_hidden": True,
        "original_clock_basis_certified": False,
        "empirical_outcomes": 0,
    }


def progression_key_source_check() -> dict:
    """A reproduced failure is a truthful diagnostic, not a source pass."""
    from fatebridge.core.astro.progression_key_sources import (
        progression_key_source_comparison,
    )
    from scripts.replay_witte_progression_constant import RECORD, RECORD_SHA256, replay

    raw = RECORD.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RECORD_SHA256:
        raise ValueError("Frozen progression-constant record checksum mismatch")
    independent = replay(json.loads(raw))
    runtime_comparison = progression_key_source_comparison()
    comparable_keys = (
        "id",
        "computed_time_seconds",
        "printed_time_seconds",
        "printed_minus_computed_time_seconds",
        "arithmetic_matches_print",
    )
    runtime_rows = [
        {key: row[key] for key in comparable_keys}
        for row in runtime_comparison["operations"]
    ]
    return {
        "runtime_diagnostic_matches_independent_replay": runtime_rows
        == independent["operations"],
        "printed_arithmetic_consistent": independent["printed_arithmetic_consistent"],
        "source_original_time_key_accepted": False,
        "independent_source_audit": independent,
        "runtime_comparison": runtime_comparison,
        "scope": "Correctly detecting the source's negative arithmetic result does not pass original conformance or alter current coordinates",
    }


def witte1925_table_source_check() -> dict:
    """Compare numeric interpolation without passing unresolved source cells."""
    from fatebridge.core.astro.witte1925_table import (
        interpolate,
        load_table,
        source_table_analysis,
    )
    from scripts.replay_witte1925_table import (
        reference_cells,
        reference_interpolate,
        replay,
    )

    record = load_table()
    nodes = reference_cells(record)
    checks = []
    for day in range(0, 371, 5):
        for age in range(10, 91, 5):
            expected = reference_interpolate(record, Fraction(day), Fraction(age))
            result = interpolate(record, day, age)
            unknown = expected is None
            exact = None if unknown else [expected.numerator, expected.denominator]
            weights = [Fraction(*r["weight_fraction"]) for r in result["corners"]]
            matched = (
                result["status"] == ("underdetermined" if unknown else "computed")
                and result["arcminutes_fraction"] == exact
                and (result["arcminutes"] is None) == unknown
                and sum(weights) == 1
                and all(w > 0 for w in weights)
            )
            checks.append(
                {
                    "day_offset": day,
                    "age_years": age,
                    "status": result["status"],
                    "reference_arcminutes_fraction": exact,
                    "runtime_arcminutes_fraction": result["arcminutes_fraction"],
                    "matched": matched,
                }
            )
    runtime_table = source_table_analysis()
    independent = replay(record)
    return {
        "raw_age_cells": len(nodes),
        "resolved_source_nodes": sum(v is not None for v in nodes.values()),
        "unresolved_source_nodes": sum(v is None for v in nodes.values()),
        "grid_probes_including_source_nodes": len(checks),
        "computed_grid_probes": sum(c["status"] == "computed" for c in checks),
        "underdetermined_grid_probes": sum(
            c["status"] == "underdetermined" for c in checks
        ),
        "numeric_and_unknown_state_replay_matches": all(c["matched"] for c in checks),
        "checks": checks,
        "runtime_source_table": runtime_table,
        "independent_source_audit": independent,
        "all_table_degrees_resolved": independent["all_table_degrees_resolved"],
        "full_original_method_accepted": False,
        "scope": "Grid probes overlap the printed nodes; unknown-state checks are not successful source positions, sky observations, independent historical examples or event predictions",
    }


def meridian_factor_placement_check() -> dict:
    from scripts import audit_meridian_factor_placement as oracle

    geometry = oracle.grid(oracle.pinned(oracle.PROTOCOL, oracle.PROTOCOL_SHA256))
    original = oracle.source_cusps(oracle.pinned(oracle.RECORD, oracle.RECORD_SHA256))
    return {
        "geometry": geometry,
        "source_table": original,
        "numeric_subset_checks_passed": geometry["numeric_checks_matched"]
        and geometry["interior_integer_checks_matched"],
        "source_table_reconciled_with_all_predeclared_models": all(
            c["all_six_meridian_intervals_overlap"] for c in original["columns"]
        ),
        "full_original_method_accepted": False,
        "scope": "Full-direction RA geometry; p59 printed-table disagreements remain outside numerical implementation acceptance",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    orbit_source_before = fictitious_element_source()
    reference = reference_check()
    sectors = sector_check()
    geometry = geometry_check()
    source_examples = source_example_check()
    symbolic = symbolic_source_check()
    sensitivity = sensitivity_check()
    solar_arc = solar_arc_check()
    sun_batch = sun_batch_check()
    physical_chart = physical_chart_source_check()
    cross_school = cross_school_model_check()
    day_meridian = day_meridian_check()
    meridian_houses = meridian_house_check()
    progression_key = progression_key_source_check()
    table1925 = witte1925_table_source_check()
    meridian_placement = meridian_factor_placement_check()
    historical_natal = historical_natal_check()
    solar_clock = solar_clock_check()
    historical_ephemeris = historical_ephemeris_check()
    orbit_source_after = fictitious_element_source()
    numerical_pass = (
        reference["passed"] == reference["reference_count"]
        and not sectors["failed"]
        and all(row["matched"] for row in source_examples["checks"])
        and all(row["matched"] for row in symbolic["checks"])
        and symbolic["near_antipodal_regression"]["matched"]
        and sensitivity["independent_source_pattern_replay_matches"]
        and sensitivity["nominal_reading_has_counterexamples_inside_declared_samples"]
        and sensitivity["sector_assignment_independent_replay_matches"]
        and bool(sensitivity["sector_factors_with_sampled_changes"])
        and solar_arc["all_sun_and_arc_checks_passed"]
        and solar_arc["publisher_static_rounding_intervals_compatible"]
        and sun_batch["zero_arc_and_day_identity_preserved"]
        and physical_chart["sampled_models_match_nominal"]
        and physical_chart["physical_model_semantics_match_actual_sources"]
        and cross_school["model_semantics_match"]
        and day_meridian["selected_1924_equation_replay_matches"]
        and day_meridian["source_reconciliation"]["printed_arithmetic_checks_passed"]
        and meridian_houses["geometric_checks_passed"]
        and progression_key["runtime_diagnostic_matches_independent_replay"]
        and table1925["numeric_and_unknown_state_replay_matches"]
        and meridian_placement["numeric_subset_checks_passed"]
        and historical_natal["source_clock_instant_preserved"]
        and historical_natal["native_ut1_equals_independent_gregorian_ordinal"]
        and historical_natal["independent_angle_algebra_matches"]
        and solar_clock["all_roundtrips_match"]
        and solar_clock["all_local_clock_equations_match"]
        and historical_ephemeris["all_positions_within_predeclared_tolerance"]
        and orbit_source_before == orbit_source_after
        and all(
            row["two_factor_set_matches"]
            and row["three_factor_set_matches"]
            and row["four_factor_set_matches"]
            for row in geometry["checks"]
        )
    )
    report = {
        "audit_version": "other_chart_schools_v24",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "numerical_subset_checks_passed": numerical_pass,
        "fictitious_element_source": {
            "before": orbit_source_before,
            "after": orbit_source_after,
            "matching_endpoint_reads": orbit_source_before == orbit_source_after,
            "continuous_file_immutability_proven": False,
            "regression_file": "tests/test_other_chart_orbit_sources.py; this script does not execute pytest",
        },
        "publisher_reference": reference,
        "sector_partition": sectors,
        "midpoint_geometry": geometry,
        "source_rule_illustrations": source_examples,
        "original_symbolic_example": symbolic,
        "birth_time_sensitivity": sensitivity,
        "solar_arc": solar_arc,
        "sun_ephemeris_batch": sun_batch,
        "physical_chart_source": physical_chart,
        "cross_school_model_semantics": cross_school,
        "day_meridian": day_meridian,
        "meridian_houses": meridian_houses,
        "meridian_factor_placement": meridian_placement,
        "progression_key_source": progression_key,
        "original_progression_source_arithmetic_passed": progression_key[
            "printed_arithmetic_consistent"
        ],
        "original_progression_time_key_accepted": False,
        "witte1925_table_source": table1925,
        "all_witte1925_table_degrees_resolved": table1925["all_table_degrees_resolved"],
        "historical_natal": historical_natal,
        "local_solar_clock": solar_clock,
        "historical_ephemeris": historical_ephemeris,
        "all_original_natal_printed_positions_matched": historical_natal[
            "all_original_printed_positions_within_half_unit"
        ],
        "four_objectives": {
            "calendar_and_geometry": "bounded numeric references, three independent historical TT planetary references with mode-dependent pass/fail, shared historical UT1/TT inversion and explicit local solar clock algebra checked; not exhaustive across the input domain, all ephemeris modes or measured Earth orientation",
            "specified_original_text": "Rudolph 1979 subset, Udo Rudolph 1996 p.14 symbolic example and Witte 1924 p.15 ecliptic equation traced; three printed operations from one historical example replayed. The 1923/1924 meridian difference is explained by the printed natal VIII cusp offset; the separate four-arcminute sensitive-point residual is retained. Eight Witte1923 progression-constant time-angle operations include two inconsistent printed totals; detecting those failures does not validate that time key. Witte1925 entire table retains342 age cells with24 unresolved; the printed55deg47min worked sum is consistent, while a hypothetical unrounded55deg47.925min policy is not adopted. Witte1924 pp56/58 full-direction RA placement implemented; p59 houses11/12/2 remain unreconciled in both predeclared obliquity models without fitting. Witte1919 p.26 natal coordinate discrepancies, full progression-time conventions and complete original rulebooks remain unaccepted",
            "interpretation_fidelity": "natal and directed source readings use actual direct occupancy, explicit factor layers and deduplicated claim identity; birth-time samples recalculated separately; real model dialogue not evaluated",
            "real_world_prediction": "symbolic solar-arc timing computed; no frozen event prediction model, prospective cohort or outcome dataset; not_tested",
        },
        "all_four_objectives_validated": False,
        "authority_certified": False,
        "protocol_regression_command": "uv run --locked --extra dev pytest -q tests/test_other_chart_clock_basis.py tests/test_other_chart_birth_seconds.py tests/test_other_chart_two_factor.py tests/test_other_chart_orbit_sources.py tests/test_ephemeris_runtime.py tests/test_other_chart_day_meridian.py tests/test_other_chart_solar_arc.py tests/test_other_chart_sensitivity.py tests/test_other_chart_depth.py tests/test_other_chart_schools.py tests/test_other_chart_schools_transports.py",
        "protocol_regression_executed_by_this_script": False,
        "historical_ephemeris_regression_command": "uv run --locked --extra dev pytest -q tests/test_other_chart_historical_reference.py",
        "historical_ephemeris_tolerance_policy": "Exact predeclared tolerance failures under fallback remain failures, not skips",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "reference_checks_passed": reference["passed"],
                "reference_checks_total": reference["reference_count"],
                "sector_probe_count": sectors["probe_count"],
                "numerical_subset_checks_passed": numerical_pass,
                "all_original_natal_printed_positions_matched": report[
                    "all_original_natal_printed_positions_matched"
                ],
                "all_four_objectives_validated": False,
            }
        )
    )
    return 0 if numerical_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
