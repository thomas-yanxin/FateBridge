"""Compare the maintained lunar derivative with independent source references."""

import argparse
import hashlib
import json
import math
import platform
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

from scripts.astrodice.audit_astrodice_position_motion import parse_date
from scripts.astrodice.diagnose_astrodice_lunar_order import angle_arcsec


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_reference(protocol, reference):
    import csv
    import io
    import re

    if reference["candidate_imported"] or reference["candidate_compared"]:
        raise ValueError("Collection was not separated from candidate")
    dates = protocol["development_dates_tt"] + protocol["holdout_dates_tt"]
    counts = {
        "astrodice_lunar_wide_stencil_v1": 137,
        "astrodice_lunar_source_window_boundary48_v1": 48,
        "astrodice_lunar_source_window_fractional51_v2": 51,
        "astrodice_lunar_precise_source_holdout12_v1": 12,
    }
    count = counts.get(protocol["protocol_id"])
    if count is None or len(dates) != count or len(set(dates)) != count:
        raise ValueError("Frozen lunar cohorts changed")
    wanted = set()
    outside = []
    for d in dates:
        for o in [0, *protocol["offsets_seconds"]]:
            try:
                wanted.add(
                    (datetime.fromisoformat(d) + timedelta(seconds=o)).isoformat()
                )
            except OverflowError:
                outside.append(
                    {
                        "center_tt": d,
                        "offset_seconds": o,
                        "reason": "Gregorian probe beyond AD9999; not an available or passing reference",
                    }
                )
    if outside != reference["outside_calendar"]:
        raise ValueError("Missing calendar endpoints changed")
    points = {}
    missing = {r["date_tt"] for r in reference["missing_probe_epochs"]}
    for batch in reference["batches"]:
        raw = batch["raw_response_utf8"]
        response = json.loads(raw)
        text = response.get("result", "")
        if (
            hashlib.sha256(raw.encode()).hexdigest() != batch["raw_response_sha256"]
            or response != batch["response"]
            or hashlib.sha256(text.encode()).hexdigest() != batch["result_sha256"]
        ):
            raise ValueError("Raw lunar reference identity changed")
        if any(
            batch["parameters"].get(k) != v
            for k, v in protocol["reference_parameters"].items()
        ):
            raise ValueError("Lunar target/time/frame changed")
        requested = {
            parse_date(label, True)
            for label in re.findall(r"'([^']+)'", batch["parameters"]["TLIST"])
        }
        if not requested <= wanted:
            raise ValueError("Lunar request cohort changed")
        if "error" in batch:
            if "No ephemeris" not in batch["error"]:
                raise ValueError("Unexplained reference failure")
            continue
        if not all(
            v in text
            for v in [
                "Target body name: Moon (301)",
                "Center body name: Earth (399)",
                "ICRF",
                "Date__(TT)",
            ]
        ):
            raise ValueError("Returned lunar headers changed")
        table = list(
            csv.reader(io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]))
        )
        if len(table) != len(batch["rows"]):
            raise ValueError("Lunar raw count changed")
        returned = set()
        for row, cols in zip(batch["rows"], table):
            d = parse_date(cols[0])
            angles = list(map(float, cols[3:5]))
            ra, dec = map(math.radians, angles)
            unit = [
                math.cos(dec) * math.cos(ra),
                math.cos(dec) * math.sin(ra),
                math.sin(dec),
            ]
            if (
                d != row["date_tt"]
                or d in points
                or angles != [row["ra_degrees"], row["dec_degrees"]]
                or row["printed_values"] != [x.strip() for x in cols[3:5]]
                or max(abs(a - b) for a, b in zip(unit, row["icrf_unit_direction"]))
                > 1e-15
            ):
                raise ValueError("Lunar raw direction/date changed")
            points[d] = row["icrf_unit_direction"]
            returned.add(d)
        if returned != requested:
            raise ValueError("Lunar requested probes missing")
    if set(points) & missing or set(points) | missing != wanted:
        raise ValueError("Lunar full coverage changed")
    weights = {
        k: float(
            Fraction((-1) ** (k + 1), k)
            * Fraction(
                math.factorial(6) ** 2, math.factorial(6 - k) * math.factorial(6 + k)
            )
        )
        for k in range(1, 7)
    }
    if [r["date_tt"] for r in reference["rows"]] != dates:
        raise ValueError("Lunar centers changed")
    for row in reference["rows"]:
        center = datetime.fromisoformat(row["date_tt"])
        absent = []
        for o in [0, *protocol["offsets_seconds"]]:
            try:
                probe = (center + timedelta(seconds=o)).isoformat()
            except OverflowError:
                absent.append({"offset_seconds": o, "reason": "outside_AD9999"})
                continue
            if probe not in points:
                absent.append(
                    {"offset_seconds": o, "date_tt": probe, "reason": "No ephemeris"}
                )
        if row["missing_probes"] != absent or row["status"] != (
            "incomplete" if absent else "available"
        ):
            raise ValueError("Lunar incomplete evidence changed")
        cohort = (
            "holdout"
            if row["date_tt"] in protocol["holdout_dates_tt"]
            else "development"
        )
        jd = (
            center.toordinal()
            + 1721424.5
            + (
                center.hour * 3600
                + center.minute * 60
                + center.second
                + center.microsecond / 1e6
            )
            / 86400
        )
        if row["cohort"] != cohort or row["jd_tt"] != jd:
            raise ValueError("Lunar cohort or time changed")
        if absent:
            continue
        rates = {
            str(h): [
                math.fsum(
                    weights[k]
                    * (
                        points[(center + timedelta(seconds=k * h)).isoformat()][axis]
                        - points[(center - timedelta(seconds=k * h)).isoformat()][axis]
                    )
                    for k in range(1, 7)
                )
                * 86400
                / h
                for axis in range(3)
            ]
            for h in protocol["steps_seconds"]
        }
        diff = math.degrees(math.dist(*rates.values())) * 3600
        if (
            rates != row["derivatives"]
            or row["icrf_direction_derivative_per_day"]
            != rates[str(protocol["chosen_step_seconds"])]
            or row["icrf_unit_direction"] != points[row["date_tt"]]
            or abs(row["step_difference_arcsec_per_day"] - diff) > 1e-12
        ):
            raise ValueError("Lunar frozen interpolation changed")
    return {
        "centers": len(dates),
        "position_probes": len(points),
        "available": sum(r["status"] == "available" for r in reference["rows"]),
        "incomplete": [r for r in reference["rows"] if r["status"] != "available"],
        "template_failures": [
            {
                "date_tt": r["date_tt"],
                "cohort": r["cohort"],
                "error": r["step_difference_arcsec_per_day"],
            }
            for r in reference["rows"]
            if r["status"] == "available"
            and r["step_difference_arcsec_per_day"] > 0.002
        ],
    }


def audit(protocol, reference, *, production_order=False):
    from fatebridge.core.astro import continuous_lahiri as frame
    from fatebridge.core.astro import ephemeris, runtime
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
    from scripts.astrodice.astrodice_lunar_pipeline import BIAS
    from scripts.astrodice.audit_astrodice_apparent import direction_derivative

    swe = runtime.swe
    trace = PhysicalEphemerisTrace()
    rows = []
    model = None
    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_SPEED
        | swe.FLG_ICRS
        | swe.FLG_J2000
        | swe.FLG_EQUATORIAL
        | swe.FLG_XYZ
    )
    for row in reference["rows"]:
        if row["status"] != "available":
            rows.append(
                {k: row[k] for k in ["date_tt", "cohort", "status", "missing_probes"]}
            )
            continue
        jd = row["jd_tt"]
        production_metadata = {}
        produced, model = ephemeris._swisseph_planet_state(
            "Moon",
            jd,
            julian_day_tt=jd,
            source_trace=trace,
            motion_metadata=production_metadata,
        )
        if production_order:
            from fatebridge.core.astro.zodiac import native_lahiri_positions

            native_lahiri_positions(
                ["Moon"],
                julian_day_ut1=jd,
                julian_day_tt=jd,
                lunar_adjustments={
                    "Moon": (
                        produced["longitude_speed_light_time_correction"],
                        model,
                        produced["longitude_speed_spatial_aberration_correction"],
                        produced.get(
                            "longitude_speed_lunar_source_remainder_correction"
                        ),
                    )
                },
                source_trace=trace,
                motion_metadata=production_metadata,
            )
        native, returned = runtime.ephemeris_call("calc", jd, swe.MOON, flags)
        if runtime.ephemeris_model_from_retflag(returned) != model:
            raise ValueError("Lunar diagnostic source changed")
        trace.observe("Moon", model)
        fixed = production_metadata["lunar_light_time"]["fixed_frame_source_derivative"]
        result = {k: row[k] for k in ["date_tt", "cohort", "status"]}
        result.update(
            domain_state=produced,
            template_step_difference_arcsec_per_day=row[
                "step_difference_arcsec_per_day"
            ],
            native_icrf_position_error_arcsec=angle_arcsec(
                native[:3], row["icrf_unit_direction"]
            ),
            native_icrf_rate_error_arcsec_per_day=math.degrees(
                math.dist(
                    direction_derivative(native[:3], native[3:]),
                    row["icrf_direction_derivative_per_day"],
                )
            )
            * 3600,
            source_motion_status=fixed["status"],
        )
        if fixed["status"] != "applied":
            result.update(
                status="current_source_motion_unavailable", reason=fixed["reason"]
            )
            rows.append(result)
            continue
        decoded = frame.decode_native_fixed_reception_state(
            jd,
            fixed["full_fixed_frame_apparent_position_au"],
            fixed["full_fixed_frame_velocity_au_per_native_argument_day"],
        )
        # The decoder supplies dynamical J2000. The original Horizons directions
        # are ICRF; invert the inspected, constant IAU2006 native frame bias.
        inverse_bias = frame.transpose(BIAS)
        position = frame.mv(inverse_bias, decoded["position"])
        velocity = frame.mv(inverse_bias, decoded["velocity_per_native_argument_day"])
        result.update(
            current_fixed_source_rate_error_arcsec_per_day=math.degrees(
                math.dist(
                    direction_derivative(position, velocity),
                    row["icrf_direction_derivative_per_day"],
                )
            )
            * 3600,
            icrf_position_error_arcsec=angle_arcsec(
                position, row["icrf_unit_direction"]
            ),
            current_source_method_id=fixed["method_id"],
            shared_frame_decoder_independently_certified=False,
        )
        if production_order:
            result["source_windows"] = production_metadata.get("lunar_source_windows")
        rows.append(result)
    available = [r for r in rows if r["status"] == "available"]
    metrics = [
        "current_fixed_source_rate_error_arcsec_per_day",
        "native_icrf_rate_error_arcsec_per_day",
        "template_step_difference_arcsec_per_day",
        "icrf_position_error_arcsec",
    ]
    summary = {
        cohort: {
            metric: {
                "count": len(rs),
                "max": max((r[metric] for r in rs), default=None),
                "above_fixed_line": sum(
                    r[metric]
                    > (0.02 if metric == "icrf_position_error_arcsec" else 0.002)
                    for r in rs
                ),
            }
            for metric in metrics
        }
        for cohort in ["development", "holdout", "all"]
        for rs in [[r for r in available if cohort == "all" or r["cohort"] == cohort]]
    }
    numeric_failed = any(
        r["current_fixed_source_rate_error_arcsec_per_day"] > 0.002
        or r["icrf_position_error_arcsec"] > 0.02
        for r in available
    )
    reference_unresolved = len(available) != len(rows) or any(
        r["template_step_difference_arcsec_per_day"] > 0.002 for r in available
    )
    return {
        "status": (
            "numeric_acceptance_failed"
            if numeric_failed
            else (
                "reference_evidence_unresolved"
                if reference_unresolved
                else "limited_diagnostic_lines_satisfied"
            )
        ),
        "exit_code": 1 if numeric_failed else 2 if reference_unresolved else 0,
        "platform": platform.platform(),
        "model": model,
        "request_order": (
            "domain_and_lahiri_then_icrf"
            if production_order
            else "domain_tropical_then_icrf"
        ),
        "gated_rate_metric": "current_fixed_source_rate_error_arcsec_per_day",
        "fixed_line_arcsec_per_day": 0.002,
        "fixed_position_line_arcsec": 0.02,
        "summary": summary,
        "cases": rows,
        "physical_sources": trace.finish(),
        "scope": "Actual maintained fixed-reception source derivative, not a former light-time-only correction. Raw native rates are diagnostic only. Original missing endpoints/reference quality remain; shared frame decoding and native argument-day comparisons do not certify physical TT/TDB equivalence or predictive validity.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    for key in ["protocol", "reference", "output"]:
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--production-order", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    reference = json.loads(args.reference.read_text())
    if digest(args.protocol) != reference["protocol_sha256"]:
        raise ValueError("Frozen lunar protocol changed")
    validation = validate_reference(protocol, reference)
    result = (
        {"validation": validation, "candidate_compared": False}
        if args.validate_only
        else audit(
            protocol,
            reference,
            production_order=args.production_order,
        )
    )
    result["inputs"] = {
        "protocol_sha256": digest(args.protocol),
        "reference_sha256": digest(args.reference),
    }
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ["cases", "physical_sources"]},
            indent=2,
        )
    )
    raise SystemExit(result.get("exit_code", 0))
