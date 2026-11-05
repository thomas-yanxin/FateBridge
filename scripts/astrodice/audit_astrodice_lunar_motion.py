"""Keep native and source-corrected lunar motion against a frozen reference.

Exit1 means numerical failures; exit2 means missing/unresolved reference
evidence. Neither application tests nor this diagnostic certify predictions.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import platform
import re
from datetime import datetime, timedelta
from pathlib import Path

from scripts.astrodice.audit_astrodice_apparent import (
    digest,
    direction_derivative,
    unit_and_rate,
)


def seven_point(points, date, seconds):
    center = datetime.fromisoformat(date)
    values = [
        points[(center + timedelta(seconds=k * seconds)).isoformat()]
        for k in [-3, -2, -1, 1, 2, 3]
    ]
    return [
        (-a + 9 * b - 45 * c + 45 * d - 9 * e + f) * 86400 / (60 * seconds)
        for a, b, c, d, e, f in zip(*values)
    ]


def validate_reference(protocol, fixture, development_reference):
    previous_missing = next(
        item["unavailable_requested_epochs"]
        for item in development_reference["references"]
        if item["body"] == "Moon"
    )
    if fixture["previous_original_missing_epochs"] != previous_missing:
        raise ValueError("Original missing lunar endpoint evidence changed")
    dates = protocol["development_dates_tt"] + protocol["holdout_dates_tt"]
    if len(dates) != len(set(dates)):
        raise ValueError("Lunar cohorts overlap")
    wanted = {
        (datetime.fromisoformat(d) + timedelta(seconds=o)).isoformat()
        for d in dates
        for o in [0, *protocol["offsets_seconds"]]
    }
    months = dict(
        zip("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), range(1, 13))
    )
    points = {}
    missing = set()
    for batch in fixture["batches"]:
        raw = batch["raw_response_utf8"]
        response = json.loads(raw)
        text = response.get("result", "")
        if (
            hashlib.sha256(raw.encode()).hexdigest() != batch["raw_response_sha256"]
            or response != batch["response"]
            or hashlib.sha256(text.encode()).hexdigest() != batch["result_sha256"]
        ):
            raise ValueError("Lunar raw reference identity changed")
        for key, value in protocol["reference_parameters"].items():
            if batch["parameters"].get(key) != value:
                raise ValueError("Lunar reference time/frame/target contract changed")
        labels = re.findall(r"'([^']+)'", batch["parameters"]["TLIST"])
        requested = set()
        for label in labels:
            match = re.fullmatch(
                r"(\d+)ad-(\w{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2})", label
            )
            if match is None:
                raise ValueError("Lunar reference calendar request changed")
            y, m, d, h, mi, s = match.groups()
            requested.add(
                datetime(int(y), months[m], int(d), int(h), int(mi), int(s)).isoformat()
            )
        if len(requested) != len(labels) or not requested <= wanted:
            raise ValueError("Lunar reference requested epoch coverage changed")
        if "error" in batch:
            if "No ephemeris" not in batch["error"]:
                raise ValueError("Unexplained lunar reference error")
            continue
        if not all(
            label in text
            for label in [
                "Target body name: Moon (301)",
                "ICRF",
                "Date__(TT)",
                "$$SOE\n",
            ]
        ):
            raise ValueError(
                "Lunar reference returned coordinate/target header changed"
            )
        table = list(
            csv.reader(io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]))
        )
        if len(table) != len(batch["rows"]):
            raise ValueError("Lunar raw and parsed counts differ")
        returned = set()
        for row, columns in zip(batch["rows"], table):
            match = re.fullmatch(
                r"\s*(\d{1,4})-(\w{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.\d+\s*",
                columns[0],
            )
            if match is None:
                raise ValueError("Lunar raw epoch format changed")
            y, m, d, h, mi, s = match.groups()
            date = datetime(
                int(y), months[m], int(d), int(h), int(mi), int(s)
            ).isoformat()
            if date != row["date_tt"] or date in points:
                raise ValueError("Lunar parsed epochs differ or are duplicated")
            angles = [row["ra_degrees"], row["dec_degrees"]]
            if angles != list(map(float, columns[3:5])) or row["printed_values"] != [
                v.strip() for v in columns[3:5]
            ]:
                raise ValueError("Lunar parsed angles differ from raw response")
            unit = unit_and_rate(*angles, 0, 0)[0]
            stored = row["icrf_unit_direction"]
            if (
                len(stored) != 3
                or max(abs(a - b) for a, b in zip(unit, stored)) > 1e-15
            ):
                raise ValueError("Lunar unit vector differs from raw angles")
            # Preserve the frozen binary64 values through the stencil. Small
            # cross-platform libm differences must not be amplified by subtraction.
            points[date] = stored
            returned.add(date)
        if returned != requested:
            raise ValueError("Lunar raw request and response epochs differ")
    for item in fixture["missing_probe_epochs"]:
        if "No ephemeris" not in item["reason"] or item["date_tt"] not in wanted:
            raise ValueError("Lunar missing epoch lacks evidence")
        missing.add(item["date_tt"])
    if set(points) & missing or set(points) | missing != wanted:
        raise ValueError("Lunar probe coverage incomplete")
    rows = fixture["rows"]
    if len(rows) != len(dates) or [r["date_tt"] for r in rows] != dates:
        raise ValueError("Lunar center coverage changed")
    for row in rows:
        date = row["date_tt"]
        value = datetime.fromisoformat(date)
        expected_jd = (
            value.toordinal()
            + 1721424.5
            + (value.hour * 3600 + value.minute * 60 + value.second) / 86400
        )
        cohort = "holdout" if date in protocol["holdout_dates_tt"] else "development"
        unavailable = [
            (value + timedelta(seconds=o)).isoformat()
            for o in [0, *protocol["offsets_seconds"]]
            if (value + timedelta(seconds=o)).isoformat() not in points
        ]
        if (
            row["jd_tt"] != expected_jd
            or row["cohort"] != cohort
            or row["missing_probe_epochs"] != unavailable
        ):
            raise ValueError("Lunar center metadata changed")
        if row["status"] != ("incomplete" if unavailable else "available"):
            raise ValueError("Lunar missing probes cannot pass")
        if unavailable:
            continue
        rates = {
            str(step): seven_point(points, date, step)
            for step in protocol["seven_point_steps_seconds"]
        }
        chosen = rates[str(protocol["chosen_step_seconds"])]
        difference = math.degrees(math.dist(*rates.values())) * 3600
        if (
            row["seven_point_derivatives"] != rates
            or row["icrf_direction_derivative_per_day"] != chosen
            or row["icrf_unit_direction"] != points[date]
            or abs(row["stencil_difference_arcsec_per_day"] - difference) > 1e-12
        ):
            raise ValueError("Lunar derivative differs from frozen stencil")
        if ("erfa_display_frame" in row) != (
            date in protocol["modern_display_dates_tt"]
        ):
            raise ValueError("Lunar independent display coverage changed")


def audit(protocol, fixture):
    from fatebridge.core.astro import ephemeris, runtime
    from fatebridge.core.astro.lunar_motion import (
        LIGHT_SPEED_AU_PER_DAY,
        aberration_position_jvp,
        dot,
    )
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
    from fatebridge.core.astro.zodiac import native_lahiri_positions

    swe = runtime.swe
    assert swe is not None
    trace = PhysicalEphemerisTrace()
    cases = []
    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_ICRS
        | swe.FLG_J2000
        | swe.FLG_EQUATORIAL
        | swe.FLG_XYZ
        | swe.FLG_SPEED
    )
    for row in fixture["rows"]:
        if row["status"] != "available":
            cases.append(
                {
                    "date_tt": row["date_tt"],
                    "cohort": row["cohort"],
                    "status": row["status"],
                }
            )
            continue
        jd = row["jd_tt"]
        metadata = {}
        state, model = ephemeris._swisseph_planet_state(
            "Moon", jd, julian_day_tt=jd, source_trace=trace, motion_metadata=metadata
        )
        lahiri = native_lahiri_positions(
            ["Moon"],
            julian_day_ut1=jd,
            julian_day_tt=jd,
            lunar_adjustments={
                "Moon": (state["longitude_speed_light_time_correction"], model)
            },
            motion_metadata=metadata,
        )["Moon"]
        if (
            lahiri["longitude_speed_light_time_correction"]
            != state["longitude_speed_light_time_correction"]
            or "longitude_speed_rotation_correction" in lahiri
        ):
            raise ValueError("Lunar sidereal correction propagation failed")
        native, returned = runtime.ephemeris_call("calc", jd, swe.MOON, flags)
        if runtime.ephemeris_model_from_retflag(returned) != model:
            raise ValueError("Lunar audit model mismatch")
        geo, _ = runtime.ephemeris_call("calc", jd, swe.MOON, flags | swe.FLG_TRUEPOS)
        radius = math.hypot(*geo[:3])
        tau = radius / LIGHT_SPEED_AU_PER_DAY
        tau_dot = dot(geo[:3], geo[3:]) / radius / LIGHT_SPEED_AU_PER_DAY
        earth, _ = runtime.ephemeris_call(
            "calc", jd, swe.EARTH, flags | swe.FLG_TRUEPOS | swe.FLG_BARYCTR
        )
        moon, _ = runtime.ephemeris_call(
            "calc", jd - tau, swe.MOON, flags | swe.FLG_TRUEPOS | swe.FLG_BARYCTR
        )
        apparent, change = aberration_position_jvp(
            [a - b for a, b in zip(moon[:3], earth[:3])],
            [-v * tau_dot for v in moon[3:]],
            [v / LIGHT_SPEED_AU_PER_DAY for v in earth[3:]],
        )
        expected = row["icrf_direction_derivative_per_day"]
        rate = direction_derivative(native[:3], native[3:])
        corrected = direction_derivative(
            native[:3], [v + d for v, d in zip(native[3:], change)]
        )
        case = {
            "date_tt": row["date_tt"],
            "cohort": row["cohort"],
            "status": "available",
            "model": model,
            "native_icrf_error_arcsec_per_day": math.degrees(math.dist(rate, expected))
            * 3600,
            "chain_icrf_error_arcsec_per_day": math.degrees(
                math.dist(corrected, expected)
            )
            * 3600,
            "position_reproduction_error_au": math.dist(apparent, native[:3]),
            "stencil_difference_arcsec_per_day": row[
                "stencil_difference_arcsec_per_day"
            ],
            "state": state,
            "lahiri_state": lahiri,
            "correction_metadata": metadata,
        }
        if "erfa_display_frame" in row:
            display = row["erfa_display_frame"]["longitude_speed_degrees_per_day"]
            for name, speed in [
                ("native", state["longitude_speed_native"]),
                ("corrected", state["longitude_speed"]),
            ]:
                case[name + "_display_error_arcsec_per_day"] = (
                    abs(speed - display) * 3600
                )
        cases.append(case)
    available = [c for c in cases if c["status"] == "available"]
    metrics = [
        "native_icrf_error_arcsec_per_day",
        "chain_icrf_error_arcsec_per_day",
        "native_display_error_arcsec_per_day",
        "corrected_display_error_arcsec_per_day",
        "stencil_difference_arcsec_per_day",
    ]
    cohorts = {}
    for cohort in ["development", "holdout", "all"]:
        rows = [r for r in available if cohort == "all" or r["cohort"] == cohort]
        cohorts[cohort] = {
            key: {
                "compared": len([r for r in rows if key in r]),
                "above_fixed_line": sum(
                    r[key] > protocol["direction_derivative_tolerance_arcsec_per_day"]
                    for r in rows
                    if key in r
                ),
                "max": max(r[key] for r in rows if key in r),
            }
            for key in metrics
        }
    numeric = any(
        cohorts["all"][key]["above_fixed_line"]
        for key in [
            "chain_icrf_error_arcsec_per_day",
            "corrected_display_error_arcsec_per_day",
        ]
    )
    unresolved = bool(
        fixture["previous_original_missing_epochs"]
        or cohorts["all"]["stencil_difference_arcsec_per_day"]["above_fixed_line"]
    )
    return {
        "status": (
            "numeric_acceptance_failed"
            if numeric
            else (
                "reference_evidence_unresolved"
                if unresolved
                else "diagnostic_lines_satisfied"
            )
        ),
        "exit_code": 1 if numeric else 2 if unresolved else 0,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "native_version": swe.version,
        "cohorts": cohorts,
        "cases": cases,
        "physical_sources": trace.finish(),
        "previous_original_missing_epochs": fixture["previous_original_missing_epochs"],
        "scope": "Post-discovery diagnostic only. Native rate, corrected rate, template uncertainty and original quantity46 failures remain separate. No perfect-accuracy or prediction certification.",
    }


def audit_other_display_rates(reference):
    """Keep all pre-existing modern cases, including inner-planet failures."""
    from fatebridge.core.astro import ephemeris
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace

    trace = PhysicalEphemerisTrace()
    cases = []
    for target in reference["references"]:
        for row in target["rows"]:
            if "erfa_display_frame" not in row:
                continue
            state, model = ephemeris._swisseph_planet_state(
                target["body"],
                row["jd_tt"],
                julian_day_tt=row["jd_tt"],
                source_trace=trace,
            )
            expected = row["erfa_display_frame"]["longitude_speed_degrees_per_day"]
            cases.append(
                {
                    "body": target["body"],
                    "date_tt": row["date_tt"],
                    "model": model,
                    "native_error_arcsec_per_day": abs(
                        state["longitude_speed_native"] - expected
                    )
                    * 3600,
                    "corrected_error_arcsec_per_day": abs(
                        state["longitude_speed"] - expected
                    )
                    * 3600,
                    "state": state,
                }
            )
    summary = {}
    for body in sorted({row["body"] for row in cases}):
        rows = [r for r in cases if r["body"] == body]
        summary[body] = {
            "compared": len(rows),
            "native_max_arcsec_per_day": max(
                r["native_error_arcsec_per_day"] for r in rows
            ),
            "corrected_max_arcsec_per_day": max(
                r["corrected_error_arcsec_per_day"] for r in rows
            ),
            "native_above_fixed_line": sum(
                r["native_error_arcsec_per_day"] > 0.002 for r in rows
            ),
            "corrected_above_fixed_line": sum(
                r["corrected_error_arcsec_per_day"] > 0.002 for r in rows
            ),
        }
    return {
        "scope": "All300 already-public modern position-derived display cases; post-discovery, no independent new holdout claim. Original native results remain unchanged in the earlier audit.",
        "fixed_line_arcsec_per_day": 0.002,
        "by_body": summary,
        "cases": cases,
        "physical_sources": trace.finish(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    for name in ["protocol", "reference", "output"]:
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    fixture = json.loads(args.reference.read_text())
    if digest(args.protocol) != fixture["protocol_sha256"]:
        raise ValueError("Lunar frozen protocol identity changed")
    previous_path = args.reference.with_name("apparent-position-derivative.json")
    if digest(previous_path) != protocol["development_reference_sha256"]:
        raise ValueError("Lunar development reference identity changed")
    validate_reference(protocol, fixture, json.loads(previous_path.read_text()))
    result = audit(protocol, fixture)
    result["existing_modern_display_diagnostics"] = audit_other_display_rates(
        json.loads(previous_path.read_text())
    )
    result["inputs"] = {
        "protocol_sha256": digest(args.protocol),
        "reference_sha256": digest(args.reference),
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {key: result[key] for key in ["status", "cohorts", "exit_code"]}, indent=2
        )
    )
    raise SystemExit(result["exit_code"])
