"""Audit apparent ICRF motion and a separately modelled modern display frame.

Exit1: numerical/coordinate contract failure. Exit2: original external epochs
remain missing. Reference generation runs independently of FateBridge/Swiss.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import os
import platform
import re
from datetime import datetime, timedelta
from pathlib import Path


def angular_error_arcsec(actual, expected):
    cross = [
        actual[1] * expected[2] - actual[2] * expected[1],
        actual[2] * expected[0] - actual[0] * expected[2],
        actual[0] * expected[1] - actual[1] * expected[0],
    ]
    return (
        math.degrees(
            math.atan2(
                math.hypot(*cross), math.fsum(a * b for a, b in zip(actual, expected))
            )
        )
        * 3600
    )


def direction_derivative(position, velocity):
    radius = math.hypot(*position)
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError("Invalid apparent direction radius")
    unit = [v / radius for v in position]
    radial = math.fsum(a * b for a, b in zip(unit, velocity))
    return [(v - a * radial) / radius for v, a in zip(velocity, unit)]


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            checksum.update(block)
    return checksum.hexdigest()


def unit_and_rate(ra_deg, dec_deg, east_arcsec_hour, north_arcsec_hour):
    alpha, delta = math.radians(ra_deg), math.radians(dec_deg)
    sa, ca, sd, cd = math.sin(alpha), math.cos(alpha), math.sin(delta), math.cos(delta)
    scale = math.radians(1 / 3600) * 24
    return [cd * ca, cd * sa, sd], [
        (-sa * east_arcsec_hour - sd * ca * north_arcsec_hour) * scale,
        (ca * east_arcsec_hour - sd * sa * north_arcsec_hour) * scale,
        cd * north_arcsec_hour * scale,
    ]


def validate_reference(protocol, fixture):
    expected_dates = (
        protocol["original_dates_tt"]
        + protocol["supplementary_dates_tt"]
        + protocol["modern_display_frame_dates_tt"]
    )
    refs = fixture["references"]
    if len(refs) != len(protocol["targets"]) or {r["body"] for r in refs} != set(
        protocol["targets"]
    ):
        raise ValueError("Apparent reference target coverage changed")
    months = dict(
        zip("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), range(1, 13))
    )

    def validate_raw(record):
        raw = record["raw_response_utf8"]
        if (
            hashlib.sha256(raw.encode()).hexdigest() != record["raw_response_sha256"]
            or json.loads(raw) != record["response"]
            or hashlib.sha256(record["response"].get("result", "").encode()).hexdigest()
            != record["result_sha256"]
        ):
            raise ValueError("Raw apparent reference hash mismatch")
        for key, value in protocol["reference_parameters"].items():
            if record["parameters"][key] != value:
                raise ValueError("Apparent reference coordinate/time contract changed")

    for reference in refs:
        validate_raw(reference)
        target = protocol["targets"][reference["body"]]
        if (
            target != reference["target_id"]
            or reference["parameters"]["COMMAND"] != f"'{target}'"
        ):
            raise ValueError("Apparent reference target identity changed")
        text = reference["response"]["result"]
        target_header = next(
            line for line in text.splitlines() if line.startswith("Target body name:")
        )
        number = re.search(r"\((\d+)\)", target_header)
        if number is None or int(number[1]) != {1: 199, 2: 299}.get(target, target):
            raise ValueError("Returned apparent target header changed")
        if not all(
            label in text
            for label in ["ICRF", "I_dRA*cosD", "I_d(DEC)/dt", "Date__(TT)"]
        ):
            raise ValueError("Apparent reference header changed")
        available = [row["date_tt"] for row in reference["rows"]]
        missing = [row["date_tt"] for row in reference["unavailable_requested_epochs"]]
        if (
            len(available) != len(set(available))
            or len(missing) != len(set(missing))
            or set(available) & set(missing)
            or set(available) | set(missing) != set(expected_dates)
        ):
            raise ValueError("Apparent reference epoch coverage changed")
        table = list(
            csv.reader(io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]))
        )
        if len(table) != len(reference["rows"]):
            raise ValueError("Apparent raw and parsed row counts differ")
        for parsed, raw in zip(reference["rows"], table):
            match = re.fullmatch(
                r"\s*(\d{1,4})-(\w{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.\d+\s*", raw[0]
            )
            if match is None:
                raise ValueError("Apparent raw epoch format changed")
            year, month, day, hour, minute, second = match.groups()
            value = datetime(
                int(year), months[month], int(day), int(hour), int(minute), int(second)
            )
            jd = (
                value.toordinal()
                + 1721424.5
                + (value.hour * 3600 + value.minute * 60 + value.second) / 86400
            )
            fields = [
                parsed[key]
                for key in [
                    "ra_degrees",
                    "dec_degrees",
                    "ra_cosdec_arcsec_per_hour",
                    "dec_arcsec_per_hour",
                ]
            ]
            if (
                value.isoformat() != parsed["date_tt"]
                or parsed["jd_tt"] != jd
                or fields != list(map(float, raw[3:7]))
                or parsed["printed_values"] != [v.strip() for v in raw[3:7]]
            ):
                raise ValueError("Apparent parsed data differ from raw columns")
            unit, rate = unit_and_rate(*fields)
            if (
                max(abs(a - b) for a, b in zip(unit, parsed["icrf_unit_direction"]))
                > 1e-15
                or max(
                    abs(a - b)
                    for a, b in zip(rate, parsed["icrf_direction_derivative_per_day"])
                )
                > 1e-15
            ):
                raise ValueError(
                    "Apparent unit/rate conversion differs from raw angles"
                )
            if ("erfa_display_frame" in parsed) != (
                parsed["date_tt"] in protocol["modern_display_frame_dates_tt"]
            ):
                raise ValueError("Independent display frame coverage changed")
        for missing_row in reference["unavailable_requested_epochs"]:
            validate_raw(missing_row["probe"])
            probe = missing_row["probe"]
            reason = probe["response"].get("error", probe["response"].get("result", ""))
            if (
                missing_row["date_tt"] not in protocol["original_dates_tt"]
                or reason != missing_row["reason"]
                or "No ephemeris" not in reason
            ):
                raise ValueError("Original missing apparent epoch evidence changed")
        if missing:
            validate_raw(reference["failed_original_request"])


def validate_derivative_reference(protocol, fixture, initial):
    """Re-derive every finite-difference vector from journalled raw positions."""
    sources = {r["body"]: r for r in initial["references"]}
    if len(fixture["references"]) != len(sources) or {
        r["body"] for r in fixture["references"]
    } != set(sources):
        raise ValueError("Derivative target coverage changed")
    for reference in fixture["references"]:
        source = sources[reference["body"]]
        if (
            reference["target_id"] != source["target_id"]
            or reference["unavailable_requested_epochs"]
            != source["unavailable_requested_epochs"]
        ):
            raise ValueError("Derivative target or original missing evidence changed")
        points = {}
        for batch in reference["batches"]:
            if (
                hashlib.sha256(batch["raw_response_utf8"].encode()).hexdigest()
                != batch["raw_response_sha256"]
                or json.loads(batch["raw_response_utf8"]) != batch["response"]
                or hashlib.sha256(
                    batch["response"].get("result", "").encode()
                ).hexdigest()
                != batch["result_sha256"]
            ):
                raise ValueError("Derivative raw position hash mismatch")
            for key in [
                "TIME_TYPE",
                "CENTER",
                "REF_SYSTEM",
                "APPARENT",
                "ANG_FORMAT",
                "EXTRA_PREC",
            ]:
                if batch["parameters"][key] != source["parameters"][key]:
                    raise ValueError("Derivative reference convention changed")
            if (
                batch["parameters"]["QUANTITIES"] != protocol["quantities"]
                or batch["parameters"]["COMMAND"] != source["parameters"]["COMMAND"]
            ):
                raise ValueError("Derivative quantity or target changed")
            text = batch["response"]["result"]
            table = list(
                csv.reader(
                    io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0])
                )
            )
            if len(table) != len(batch["rows"]):
                raise ValueError("Derivative raw row coverage changed")
            for row, raw in zip(batch["rows"], table):
                if [row["ra_degrees"], row["dec_degrees"]] != list(
                    map(float, raw[3:5])
                ) or row["printed_values"] != [v.strip() for v in raw[3:5]]:
                    raise ValueError("Derivative parsed coordinates differ from raw")
                when = datetime.fromisoformat(row["date_tt"])
                if (
                    when.strftime("%b-%d %H:%M:%S") not in raw[0]
                    or str(when.year).zfill(4) not in raw[0]
                ):
                    raise ValueError("Derivative raw epoch changed")
                unit = unit_and_rate(row["ra_degrees"], row["dec_degrees"], 0, 0)[0]
                if (
                    row["date_tt"] in points
                    or math.dist(unit, row["icrf_unit_direction"]) > 1e-15
                ):
                    raise ValueError("Derivative duplicate or altered unit direction")
                # Validate the spherical conversion above, then re-use the
                # frozen binary64 vector actually fed to the generator's
                # stencil. Re-evaluating libm here before differencing would
                # amplify harmless cross-platform trig rounding.
                points[row["date_tt"]] = row["icrf_unit_direction"]
        if len(reference["rows"]) != len(source["rows"]) or {
            r["date_tt"] for r in reference["rows"]
        } != {r["date_tt"] for r in source["rows"]}:
            raise ValueError("Derivative centre coverage changed")
        required = set()
        for row in reference["rows"]:
            center = datetime.fromisoformat(row["date_tt"])
            for step in protocol["five_point_step_seconds"]:
                times = [
                    (center + timedelta(seconds=step * k)).isoformat()
                    for k in [-2, -1, 1, 2]
                ]
                required.update(times)
                vectors = [points[t] for t in times]
                rate = [
                    (a - 8 * b + 8 * c - d) * 86400 / (12 * step)
                    for a, b, c, d in zip(*vectors)
                ]
                if math.dist(rate, row["five_point_derivatives"][str(step)]) > 1e-15:
                    raise ValueError("Derivative does not follow raw position stencil")
            if (
                row["icrf_direction_derivative_per_day"]
                != row["five_point_derivatives"]["1800"]
            ):
                raise ValueError("Derivative silently selected another stencil")
        if set(points) != required:
            raise ValueError("Derivative position probe coverage changed")


def audit(
    protocol,
    fixture,
    *,
    expected_model,
    derivative_protocol=None,
    derivative_fixture=None,
):
    from fatebridge.core.astro import runtime
    from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
    from fatebridge.core.jpl_ephemeris import jpl_header

    validate_reference(protocol, fixture)
    position_rates = {}
    if derivative_fixture is not None:
        validate_derivative_reference(derivative_protocol, derivative_fixture, fixture)
        position_rates = {
            (r["body"], row["date_tt"]): row
            for r in derivative_fixture["references"]
            for row in r["rows"]
        }
    swe = runtime.swe
    if swe is None:
        raise RuntimeError("Swiss Ephemeris required")
    flags = swe.FLG_SWIEPH
    for name in protocol["native_direction_flags"]:
        flags |= getattr(swe, name)
    if flags & swe.FLG_TRUEPOS or protocol["native_geometric_truepos"] is not False:
        raise ValueError("Apparent audit cannot use geometric true positions")
    cases = []
    missing = []
    files = {}
    for reference in fixture["references"]:
        name = reference["body"]
        for item in reference["unavailable_requested_epochs"]:
            missing.append(
                {"body": name, "date_tt": item["date_tt"], "reason": item["reason"]}
            )
        for row in reference["rows"]:
            values, returned = runtime.ephemeris_call(
                "calc", row["jd_tt"], PLANET_SWISSEPH_IDS[name], flags
            )
            if (
                len(values) != 6
                or not all(math.isfinite(v) for v in values)
                or returned < 0
                or not returned & swe.FLG_SPEED
                or runtime.ephemeris_model_from_retflag(returned) != expected_model
            ):
                raise ValueError(
                    "Requested finite apparent native state/model unavailable"
                )
            required = flags & (
                swe.FLG_XYZ | swe.FLG_EQUATORIAL | swe.FLG_J2000 | swe.FLG_ICRS
            )
            if returned & required != required or returned & swe.FLG_TRUEPOS:
                raise ValueError("Native apparent coordinate contract changed")
            unit = [v / math.hypot(*values[:3]) for v in values[:3]]
            rate = direction_derivative(values[:3], values[3:])
            angle = angular_error_arcsec(unit, row["icrf_unit_direction"])
            derivative = (
                math.degrees(
                    math.hypot(
                        *(
                            a - b
                            for a, b in zip(
                                rate, row["icrf_direction_derivative_per_day"]
                            )
                        )
                    )
                )
                * 3600
            )
            geometric, _ = runtime.ephemeris_call(
                "calc", row["jd_tt"], PLANET_SWISSEPH_IDS[name], flags | swe.FLG_TRUEPOS
            )
            wrong_angle = angular_error_arcsec(
                geometric[:3], row["icrf_unit_direction"]
            )
            case = {
                "body": name,
                "date_tt": row["date_tt"],
                "native_returned_flags": returned,
                "direction_error_arcsec": angle,
                "direction_derivative_error_arcsec_per_day": derivative,
                "passes_icrf_direction": angle
                <= protocol["direction_tolerance_arcsec"],
                "passes_icrf_rate": derivative
                <= protocol["direction_derivative_tolerance_arcsec_per_day"],
                "geometric_position_negative_control_fails": wrong_angle
                > protocol["direction_tolerance_arcsec"],
                "supplementary": row["date_tt"] in protocol["supplementary_dates_tt"],
            }
            position_reference = position_rates.get((name, row["date_tt"]))
            if position_reference is not None:
                residual = (
                    math.degrees(
                        math.dist(
                            rate,
                            position_reference["icrf_direction_derivative_per_day"],
                        )
                    )
                    * 3600
                )
                case.update(
                    position_derived_rate_error_arcsec_per_day=residual,
                    position_derived_rate_within_line=residual
                    <= derivative_protocol[
                        "direction_derivative_tolerance_arcsec_per_day"
                    ],
                    reference_stencil_difference_arcsec_per_day=position_reference[
                        "stencil_difference_arcsec_per_day"
                    ],
                    printed_quantity46_position_derivative_disagreement_arcsec_per_day=position_reference[
                        "printed_quantity46_difference_arcsec_per_day"
                    ],
                )
            if "erfa_display_frame" in row:
                reference_frame = row["erfa_display_frame"]
                ecliptic, display_flags = runtime.ephemeris_call(
                    "calc",
                    row["jd_tt"],
                    PLANET_SWISSEPH_IDS[name],
                    swe.FLG_SWIEPH | swe.FLG_SPEED,
                )
                if not display_flags & swe.FLG_SPEED or not all(
                    math.isfinite(v) for v in ecliptic
                ):
                    raise ValueError("Display frame native motion unavailable")
                longitude_error = (
                    abs(
                        (ecliptic[0] - reference_frame["longitude_degrees"] + 180) % 360
                        - 180
                    )
                    * 3600
                )
                speed_error = (
                    abs(
                        ecliptic[3] - reference_frame["longitude_speed_degrees_per_day"]
                    )
                    * 3600
                )
                case.update(
                    display_longitude_error_arcsec=longitude_error,
                    display_longitude_speed_error_arcsec_per_day=speed_error,
                    passes_display_longitude=longitude_error
                    <= protocol["display_longitude_tolerance_arcsec"],
                    passes_display_speed=speed_error
                    <= protocol["display_longitude_speed_tolerance_arcsec_per_day"],
                    omit_frame_derivative_negative_control_fails=abs(
                        ecliptic[3]
                        - reference_frame[
                            "omitted_frame_derivative_speed_degrees_per_day"
                        ]
                    )
                    * 3600
                    > protocol["display_longitude_speed_tolerance_arcsec_per_day"],
                )
                if position_reference is not None:
                    residual = (
                        abs(
                            ecliptic[3]
                            - position_reference["erfa_display_frame"][
                                "longitude_speed_degrees_per_day"
                            ]
                        )
                        * 3600
                    )
                    case.update(
                        position_derived_display_speed_error_arcsec_per_day=residual,
                        position_derived_display_speed_within_line=residual
                        <= derivative_protocol[
                            "display_longitude_speed_tolerance_arcsec_per_day"
                        ],
                    )
            case["passes"] = all(v for k, v in case.items() if k.startswith("passes_"))
            cases.append(case)
            slot = 0 if expected_model == "jpl" or name != "Moon" else 1
            filename, start, end, de = runtime.ephemeris_call(
                "get_current_file_data", slot
            )
            if filename and filename not in files:
                path = Path(filename)
                files[filename] = {
                    "filename": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                    "de_number": de,
                    "native_interval": [start, end],
                    "jpl_header": jpl_header(path) if expected_model == "jpl" else None,
                }
    failed = [c for c in cases if not c["passes"]]
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "requested_model": expected_model,
        "available_compared": len(cases),
        "supplementary_available": sum(c["supplementary"] for c in cases),
        "modern_display_compared": sum("passes_display_speed" in c for c in cases),
        "missing_original_references": missing,
        "all_original_requested_epochs_validated": not missing,
        "numeric_failures": failed,
        "cases": cases,
        "data_files": files,
        "max_direction_error_arcsec": max(c["direction_error_arcsec"] for c in cases),
        "max_direction_derivative_error_arcsec_per_day": max(
            c["direction_derivative_error_arcsec_per_day"] for c in cases
        ),
        "max_display_longitude_error_arcsec": max(
            c["display_longitude_error_arcsec"]
            for c in cases
            if "passes_display_speed" in c
        ),
        "max_display_longitude_speed_error_arcsec_per_day": max(
            c["display_longitude_speed_error_arcsec_per_day"]
            for c in cases
            if "passes_display_speed" in c
        ),
        "status": (
            "numeric_failure"
            if failed
            else "incomplete_external_reference" if missing else "bounded_checks_passed"
        ),
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--ephe", type=Path, required=True)
    parser.add_argument("--jpl-file")
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--derivative-protocol", type=Path)
    parser.add_argument("--derivative-reference", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.reference.read_text())
    if fixture["protocol_sha256"] != digest(args.protocol):
        raise ValueError("Frozen apparent protocol hash mismatch")
    if bool(args.derivative_protocol) != bool(args.derivative_reference):
        raise ValueError("Both derivative protocol and reference are required")
    dp = (
        json.loads(args.derivative_protocol.read_text())
        if args.derivative_protocol
        else None
    )
    df = (
        json.loads(args.derivative_reference.read_text())
        if args.derivative_reference
        else None
    )
    if df is not None and (
        df["protocol_sha256"] != digest(args.derivative_protocol)
        or dp["initial_protocol_sha256"] != digest(args.protocol)
        or dp["initial_reference_sha256"] != digest(args.reference)
    ):
        raise ValueError("Derivative protocol/reference identity mismatch")
    os.environ["SE_EPHE_PATH"] = str(args.ephe.resolve())
    if args.jpl_file:
        os.environ["FATEBRIDGE_JPL_FILE"] = args.jpl_file
    else:
        os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    result = audit(
        json.loads(args.protocol.read_text()),
        fixture,
        expected_model="jpl" if args.jpl_file else "swieph",
        derivative_protocol=dp,
        derivative_fixture=df,
    )
    result.update(
        protocol_sha256=digest(args.protocol),
        reference_sha256=digest(args.reference),
        audit_script_sha256=digest(Path(__file__)),
    )
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "status",
                    "available_compared",
                    "modern_display_compared",
                    "max_direction_error_arcsec",
                    "max_direction_derivative_error_arcsec_per_day",
                    "max_display_longitude_error_arcsec",
                    "max_display_longitude_speed_error_arcsec_per_day",
                ]
            }
        )
    )
    return (
        1
        if result["numeric_failures"]
        else 2 if result["missing_original_references"] else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
