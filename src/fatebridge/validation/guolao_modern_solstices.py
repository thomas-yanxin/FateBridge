"""Independent frozen Horizons TT brackets and conditional source-clock errors."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core import guolao_calendar_date_bridge as bridge
from fatebridge.core.guolao_cardinals import gujin43_cardinal_example
from fatebridge.core.guolao_gnomon_epoch import PROFILE as LITERAL_PROFILE
from fatebridge.core.guolao_gnomon_epoch import READING_PROFILE, load_gnomon_epoch
from fatebridge.core.guolao_modern_time import (
    CLOCK_POLICY,
    apparent_solar_state_tt,
    historical_clock_components,
    solar_crossing_tt,
)
from fatebridge.core.guolao_year_labels import shoushi_year_context

DATA = Path(__file__).resolve().parents[1] / "data/guolao/modern-solstices-v1.json"
PROFILE = "guolao_horizons_seasons_tt_clock_reference_v1"


def parse_horizons_observer(
    raw: bytes, expected_tt: list[F], *, clock: bool, inertial: bool = False
) -> dict[str, Any]:
    """Read-only complete-output validation; never salvage partial tables."""
    payload = json.loads(raw)
    if "error" in payload or payload.get("signature") != {
        "source": "NASA/JPL Horizons API",
        "version": "1.0",
    }:
        raise ValueError("Horizons错误或签名版本不符")
    result = payload["result"]
    if result.count("$$SOE") != 1 or result.count("$$EOE") != 1:
        raise ValueError("Horizons表界缺失或重复")
    before, rest = result.split("$$SOE")
    table = rest.split("$$EOE")[0]
    for token in (
        "Target body name: Sun (10)",
        "Center body name: Earth (399)",
        "{source: DE441}",
        "NO (AIRLESS)",
        "Calendar mode   : Gregorian",
    ):
        if token not in before:
            raise ValueError("Horizons来源或坐标环境不符: " + token)
    token = "Center geodetic : 116.4, 40.0" if clock else "Center-site name: GEOCENTRIC"
    if token not in before:
        raise ValueError("Horizons观测点不符")
    if clock and inertial:
        raise ValueError("太阳钟与惯性坐标参考模式须分别声明")
    header = next(
        (
            v
            for v in before.splitlines()
            if "JDTT," in v and ("RA_(ICRF-a-app)" in v if inertial else "TDB-UT" in v)
        ),
        None,
    )
    if header is None:
        raise ValueError("Horizons未明确返回TT标签")
    names = [v.strip() for v in next(csv.reader([header]))]
    required = (
        ["ObsEcLon", "ObsEcLat", "RA_(ICRF-a-app)", "DEC_(ICRF-a-app)"]
        if inertial
        else (
            ["TDB-UT", "L_Ap_SOL_Time"] if clock else ["TDB-UT", "ObsEcLon", "ObsEcLat"]
        )
    )
    if any(v not in names for v in required):
        raise ValueError("Horizons参考量缺失")
    rows = []
    for fields in csv.reader(io.StringIO(table.strip())):
        if len(fields) != len(names):
            raise ValueError("Horizons列数变化")
        row = {name: fields[n].strip() for n, name in enumerate(names) if name}
        try:
            for name in [names[0], *required]:
                F(row[name])
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError("Horizons值缺失或非有限数") from exc
        rows.append(row)
    if len(rows) != len(expected_tt) or len(set(expected_tt)) != len(expected_tt):
        raise ValueError("Horizons参考行不完整或重复，不能取部分当作全量")
    for row, tt in zip(rows, expected_tt):
        if abs(F(row[names[0]]) - tt) > F(1, 10**8):
            raise ValueError("Horizons时刻与请求不一致")
        if clock:
            valid = 0 <= F(row["L_Ap_SOL_Time"]) < 24
        else:
            valid = 0 <= F(row["ObsEcLon"]) < 360 and -90 <= F(row["ObsEcLat"]) <= 90
        if not valid:
            raise ValueError("Horizons返回角度越界")
    return {
        "signature": payload["signature"],
        "header": header,
        "metadata": before,
        "rows": rows,
    }


def load_reference() -> tuple[dict[str, Any], str]:
    blob = DATA.read_bytes()
    source = json.loads(blob)
    plan = source["plan"]
    if (
        source["profile_id"] != PROFILE
        or source["schema"] != PROFILE
        or len(source["reference_brackets"]) != 14
        or len(source["historical_clock_rows"]) != 12
        or plan["reference_bisection_rounds"] != 15
        or plan["nominal_comparison_warning_seconds"] != 60
        or source["reference_backend"] != "DE441"
        or source["source_epoch_calibrated"] is not False
        or source["used_in_native_birth_chart"] is not False
    ):
        raise ValueError("固定参考、警示线或声明改变，不改样本迎合比较")
    for name, wanted in source["source_component_data_hashes"].items():
        if hashlib.sha256((DATA.parent / name).read_bytes()).hexdigest() != wanted:
            raise ValueError("具名原算链来源已改变，须重新核验")
    return source, hashlib.sha256(blob).hexdigest()


def _source_clock_rows(case_id: str) -> list[dict[str, Any]]:
    dates = bridge.load_calendar_date_bridge(bridge.PROFILE)
    if case_id in (
        "winter1277",
        "summer1278",
        "winter1278",
        "summer1279",
        "winter1279",
        "winter1280",
    ):
        rows = []
        for profile in (LITERAL_PROFILE, READING_PROFILE):
            model = load_gnomon_epoch(profile)
            if case_id == "winter1280":
                mean = model.season_mean("winter1279")
                cycle = (F(mean["mean_source_cycle_day_exact"]) + F("365.2425")) % 60
                reference = model.source["season_means"][-1]
            else:
                mean = model.season_mean(case_id)
                cycle = F(mean["mean_source_cycle_day_exact"])
                reference = mean["published_reference"]
            serial: int | F = bridge.calendar_label_noon_jdn(
                *map(int, reference["printed_calendar_date"].split("-")),
                calendar=bridge.CALENDARS[1],
            )
            rows.append(
                {
                    "source_profile": profile,
                    "source_cycle_day_exact": str(cycle),
                    "conditional_source_label_serial_exact": str(F(serial) + cycle % 1),
                    "source_clock_interpretation": "local_apparent_solar_time_as_interpreted_by_Li2013",
                    "modern_clock_calibration_accepted": False,
                }
            )
        if case_id == "winter1280":
            winter = dates.winter_candidates(
                source_year=1281, search_policy=bridge.SEARCH_POLICY
            )
            serial = winter["candidates"][0]["calendar_label_noon_jdn"]
            rows.append(
                {
                    "source_profile": "fixed_original_qiying_55_06",
                    "source_cycle_day_exact": "2753/50",
                    "conditional_source_label_serial_exact": str(F(serial) + F("0.06")),
                    "source_clock_interpretation": "local_apparent_solar_time_as_interpreted_by_Li2013",
                    "modern_clock_calibration_accepted": False,
                }
            )
        return rows
    if case_id in (
        "winter1598",
        "spring1599",
        "summer1599",
        "autumn1599",
        "winter1599",
    ):
        cardinal = {
            "winter1598": "winter",
            "spring1599": "spring",
            "summer1599": "summer",
            "autumn1599": "autumn",
            "winter1599": "next_winter",
        }[case_id]
        times = gujin43_cardinal_example(profile="nlc166")["cardinal_times"]
        counter = F(
            next(v for v in times if v["cardinal"] == cardinal)[
                "unwrapped_source_day_exact"
            ]
        )
        mapped = dates.source_counter_label(
            counter,
            source_year=1599,
            search_policy=bridge.SEARCH_POLICY,
            counter_basis=bridge.COUNTER_BASIS,
        )
        serial = (
            F(mapped["conditional_date_labels"]["calendar_label_noon_jdn"])
            + counter % 1
        )
        return [
            {
                "source_profile": "gujin43_named318_cardinal_times",
                "unwrapped_source_counter_exact": str(counter),
                "conditional_source_label_serial_exact": str(serial),
                "source_clock_interpretation": "apparent_and_mean_hypotheses_both_retained_not_selected_by_fit",
                "modern_clock_calibration_accepted": False,
            }
        ]
    if case_id == "winter1607":
        context = shoushi_year_context(source_year=1608)
        winter = dates.winter_candidates(
            source_year=1608, search_policy=bridge.SEARCH_POLICY
        )
        serial = F(winter["candidates"][0]["calendar_label_noon_jdn"]) + F(
            context["winter_fraction_of_day_exact"]
        )
        return [
            {
                "source_profile": "shoushi_source1608_winter1607",
                "conditional_source_label_serial_exact": str(serial),
                "source_clock_interpretation": "apparent_and_mean_hypotheses_both_retained_not_selected_by_fit",
                "modern_clock_calibration_accepted": False,
            }
        ]
    return []


def audit_frame_diagnostic(*, include_swieph: bool) -> dict[str, Any]:
    blob = DATA.with_name("modern-solstices-frame-diagnostic-v1.json").read_bytes()
    diagnostic = json.loads(blob)
    if (
        diagnostic["base_reference_data_sha256"]
        != hashlib.sha256(DATA.read_bytes()).hexdigest()
        or diagnostic["postcomparison_diagnostic"] is not True
    ):
        raise ValueError("比较后的坐标诊断来源不符")
    records = []
    for row in diagnostic["reference_rows"]:
        tt = float(F(row["tt_jd_requested_exact"]))
        reference_ra = float(row["RA_(ICRF-a-app)"])
        reference_dec = float(row["DEC_(ICRF-a-app)"])
        for backend in (
            ("moshier", "swieph_de441") if include_swieph else ("moshier",)
        ):
            inertial = apparent_solar_state_tt(
                tt, backend=backend, frame="apparent_equatorial_icrf"
            )
            tropical = apparent_solar_state_tt(
                tt, backend=backend, frame="native_apparent_tropical_date"
            )
            for state in (inertial, tropical):
                for file in state["observed_source_files"]:
                    wanted = diagnostic["expected_swieph_DE441_files"][file["filename"]]
                    if any(file[k] != v for k, v in wanted.items()):
                        raise ValueError("实际DE441文件与已记录来源不符")
            x = (
                math.remainder(inertial["position"][0] - reference_ra, 360)
                * 3600
                * math.cos(math.radians(reference_dec))
            )
            y = (inertial["position"][1] - reference_dec) * 3600
            records.append(
                {
                    "reference": row,
                    "inertial_state": inertial,
                    "tropical_state": tropical,
                    "inertial_tangent_distance_arcseconds": math.hypot(x, y),
                    "native_tropical_minus_Horizons_longitude_arcseconds": math.remainder(
                        tropical["position"][0] - float(row["ObsEcLon"]), 360
                    )
                    * 3600,
                    "date_frames_reconciled_or_native_policy_changed": False,
                }
            )
    return {
        "profile_id": diagnostic["profile_id"],
        "diagnostic_data_sha256": hashlib.sha256(blob).hexdigest(),
        "postcomparison_diagnostic": True,
        "same14_reference_epochs_retained": True,
        "include_swieph_de441": include_swieph,
        "records": records,
        "inertial_agreement_is_independent_orbital_observation": False,
        "DE441_reference_and_swieph_share_dynamical_model": True,
        "date_frame_rotation_changed_to_fit": False,
    }


def audit_modern_solstices(*, include_swieph: bool = False) -> dict[str, Any]:
    source, fingerprint = load_reference()
    events = []
    for ref in source["reference_brackets"]:
        case = ref["case"]
        # The independent reference searched a full fixed five-day window.
        # Use that same window here, never the subsecond reference bracket.
        from datetime import date

        start = F(
            date(case["year"], case["gregorian_month"], case["start_day"]).toordinal()
        ) + F("1721424.5")
        result = solar_crossing_tt(
            case["target_deg"],
            float(start),
            float(start + source["plan"]["window_days"]),
        )
        selected = F(result["selected_jd_tt_exact"])
        low, high = F(ref["lower_tt_jd_exact"]), F(ref["upper_tt_jd_exact"])
        distance = (
            F()
            if low <= selected <= high
            else min(abs(selected - low), abs(selected - high)) * 86400
        )
        events.append(
            {
                "case_id": case["id"],
                "reference": ref,
                "native": result,
                "native_minus_reference_endpoint_seconds_exact": [
                    str((selected - high) * 86400),
                    str((selected - low) * 86400),
                ],
                "distance_outside_reference_bracket_seconds_exact": str(distance),
                "within_predeclared60_second_warning_line": distance <= 60,
                "coordinate_frame_definitions_fully_reconciled": False,
            }
        )
    clocks = []
    anchor = bridge.load_calendar_date_bridge(bridge.PROFILE).anchor_serial
    for row in source["historical_clock_rows"]:
        parts = historical_clock_components(
            F(row["tt_jd_exact"]),
            F(row["TDB_minus_UT1_seconds"]),
            F(row["apparent_solar_hours"]),
            F(source["clock_reference_site"]["longitude_east_deg"]),
            year=row["year"],
            timescale_difference_policy=CLOCK_POLICY,
        )
        mean = F(parts["mean_local_calendar_label_serial_exact"])
        apparent = F(parts["apparent_local_calendar_label_serial_exact"])
        comparisons = []
        for original in _source_clock_rows(row["case_id"]):
            original_serial = F(original["conditional_source_label_serial_exact"])
            comparisons.append(
                {
                    **original,
                    "source_minus_reference_apparent_nominal_seconds_exact": str(
                        (original_serial - apparent) * 86400
                    ),
                    "source_minus_reference_mean_nominal_seconds_exact": str(
                        (original_serial - mean) * 86400
                    ),
                    "best_clock_hypothesis_or_source_variant_selected_by_error": False,
                }
            )
        clocks.append(
            {
                "case_id": row["case_id"],
                "clock_components": parts,
                "reference_local_apparent_cycle_day_exact": str(
                    (apparent - anchor) % 60
                ),
                "source_comparisons": comparisons,
                "reference_epoch": "midpoint_of_subsecond_DE441_TT_bracket",
                "site": source["clock_reference_site"],
                "source_epoch_calibration_accepted": False,
            }
        )
    return {
        "model_id": PROFILE,
        "source_data_sha256": fingerprint,
        "all14_fixed_window_modern_events": events,
        "all12_historical_clock_comparisons": clocks,
        "postcomparison_frame_diagnostic": audit_frame_diagnostic(
            include_swieph=include_swieph
        ),
        "warning_line_seconds": 60,
        "warning_line_is_an_accuracy_certificate": False,
        "reference_TT_bracket_width_seconds_exact": "675/1024",
        "reference_root_bracket_is_physical_uncertainty": False,
        "source_constants_or_observations_adjusted_to_reference": False,
        "historical_Earth_rotation_uncertainty_quantified": False,
        "exact_historical_observatory_location_established": False,
        "full_original_calendar_or_local_clock_calibrated": False,
        "native_birth_chart_or_phase_chain_backfilled": False,
        "real_world_predictive_efficacy_tested": False,
        "four_axis_perfect_scores_established": False,
    }
