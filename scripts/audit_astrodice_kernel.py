"""Audit available frozen JPL geometric ICRF vectors with real .se1 data.

This is an explicit data-backed integration check, not a file-free unit test.
Exit 1 means numerical/model failure; exit 2 means requested external evidence
is incomplete even if every available comparison passes.
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
from datetime import datetime
from pathlib import Path


def validate_reference(protocol, fixture):
    """Bind every comparison to raw returned data and the complete protocol."""
    references = fixture["references"]
    names = [r["body"] for r in references]
    if len(names) != len(set(names)) or set(names) != set(protocol["targets"]):
        raise ValueError("Reference body coverage differs from frozen protocol")
    for reference in references:
        raw = reference["raw_response_utf8"]
        if (
            hashlib.sha256(raw.encode()).hexdigest() != reference["raw_response_sha256"]
            or json.loads(raw) != reference["response"]
        ):
            raise ValueError("Raw reference response mismatch")
        text = reference["response"]["result"]
        if hashlib.sha256(text.encode()).hexdigest() != reference["result_sha256"]:
            raise ValueError("Raw reference result hash mismatch")
        if (
            reference["target_id"] != protocol["targets"][reference["body"]]
            or reference["parameters"]["COMMAND"] != f"'{reference['target_id']}'"
        ):
            raise ValueError("Reference target identity mismatch")
        for key, value in {
            "TIME_TYPE": "'TT'",
            "REF_SYSTEM": "'ICRF'",
            "REF_PLANE": "'FRAME'",
            "VEC_CORR": "'NONE'",
            "CENTER": "'500@399'",
            "OUT_UNITS": "'AU-D'",
        }.items():
            if reference["parameters"][key] != value:
                raise ValueError("Reference frame/time/correction mismatch")
        # Horizons reports the zero-satellite Mercury/Venus barycenter aliases
        # with IDs 199/299 even when explicitly requested as 1/2.
        header_target = {1: 199, 2: 299}.get(
            reference["target_id"], reference["target_id"]
        )
        target_line = next(
            line for line in text.splitlines() if line.startswith("Target body name:")
        )
        header_number = re.search(r"\((\d+)\)", target_line)
        if header_number is None or header_number.group(1) != str(header_target):
            raise ValueError("Reference returned target header mismatch")
        if not all(
            x in text
            for x in [
                "JDTT",
                "Reference frame : ICRF",
                "GEOMETRIC cartesian",
            ]
        ):
            raise ValueError("Reference header mismatch")
        available = [r["date_tt"] for r in reference["rows"]]
        missing = [r["date_tt"] for r in reference["unavailable_requested_epochs"]]
        expected = protocol["dates_tt"] + protocol["supplemental_dates_tt"]
        if (
            len(available) != len(set(available))
            or len(missing) != len(set(missing))
            or set(available) & set(missing)
            or set(available) | set(missing) != set(expected)
        ):
            raise ValueError("Reference epoch coverage differs from frozen protocol")
        table = list(
            csv.reader(io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]))
        )
        if len(table) != len(reference["rows"]):
            raise ValueError("Parsed reference row coverage mismatch")
        for parsed, row in zip(reference["rows"], table):
            value = datetime.fromisoformat(parsed["date_tt"])
            jd = (
                value.toordinal()
                + 1721424.5
                + (value.hour * 3600 + value.minute * 60 + value.second) / 86400
            )
            if (
                abs(jd - float(row[0])) > 1e-9
                or parsed["jd_tt"] != float(row[0])
                or parsed["position_au"] != list(map(float, row[2:5]))
                or parsed["velocity_au_per_day"] != list(map(float, row[5:8]))
            ):
                raise ValueError("Parsed reference values differ from raw JPL rows")
        if missing:
            failed = reference["failed_original_request"]
            if (
                failed is None
                or hashlib.sha256(failed["raw_response_utf8"].encode()).hexdigest()
                != failed["raw_response_sha256"]
                or json.loads(failed["raw_response_utf8"]) != failed["response"]
            ):
                raise ValueError("Missing-epoch evidence mismatch")
            error = failed["response"].get(
                "error", failed["response"].get("result", "")
            )
            if (
                any(
                    r["reason"] != error
                    for r in reference["unavailable_requested_epochs"]
                )
                or "No ephemeris" not in error
            ):
                raise ValueError("Missing-epoch reason mismatch")


def angular_error_arcsec(actual, expected):
    cross = (
        actual[1] * expected[2] - actual[2] * expected[1],
        actual[2] * expected[0] - actual[0] * expected[2],
        actual[0] * expected[1] - actual[1] * expected[0],
    )
    dot = math.fsum(a * b for a, b in zip(actual, expected))
    return math.degrees(math.atan2(math.hypot(*cross), dot)) * 3600


def direction_derivative(position, velocity):
    """Derivative of the ICRF line-of-sight unit vector, in inverse days."""
    radius = math.hypot(*position)
    if radius <= 0 or not math.isfinite(radius):
        raise ValueError("Invalid direction derivative radius")
    unit = [x / radius for x in position]
    radial = math.fsum(a * b for a, b in zip(unit, velocity))
    return [(v - u * radial) / radius for u, v in zip(unit, velocity)]


def velocity_diagnostics(values, returned, reference_row, protocol, speed_flag):
    """Keep unavailable motion distinct from zero or stationary motion."""
    status = "finite_native_state"
    component = rate = None
    if returned < 0 or len(values) != 6 or not all(math.isfinite(v) for v in values):
        status = "invalid_native_state"
    elif not returned & speed_flag:
        status = "speed_flag_missing"
    else:
        actual = values[3:6]
        expected = reference_row["velocity_au_per_day"]
        if len(expected) != 3 or not all(math.isfinite(v) for v in expected):
            raise ValueError("Invalid reference velocity")
        component = max(abs(a - b) for a, b in zip(actual, expected))
        actual_rate = direction_derivative(values[:3], actual)
        expected_rate = direction_derivative(reference_row["position_au"], expected)
        rate = (
            math.degrees(
                math.hypot(*(a - b for a, b in zip(actual_rate, expected_rate)))
            )
            * 3600
        )
    return {
        "velocity_state_status": status,
        "native_speed_flag_returned": returned >= 0 and bool(returned & speed_flag),
        "component_velocity_error_au_per_day": component,
        "direction_derivative_error_arcsec_per_day": rate,
        "passes_velocity_check": (
            status == "finite_native_state"
            and component <= protocol["component_velocity_tolerance_au_per_day"]
            and rate <= protocol["direction_derivative_tolerance_arcsec_per_day"]
        ),
    }


def audit(protocol, fixture, *, expected_model="swieph", velocity_protocol=None):
    from fatebridge.core.astro import runtime
    from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
    from fatebridge.core.jpl_ephemeris import jpl_header

    validate_reference(protocol, fixture)
    if velocity_protocol is not None:
        if (
            velocity_protocol["position_protocol_sha256"] != fixture["protocol_sha256"]
            or velocity_protocol["require_speed_flag"] is not True
            or any(
                not math.isfinite(velocity_protocol[key]) or velocity_protocol[key] <= 0
                for key in (
                    "component_velocity_tolerance_au_per_day",
                    "direction_derivative_tolerance_arcsec_per_day",
                )
            )
        ):
            raise ValueError("Velocity protocol identity or thresholds are invalid")
    swe = runtime.swe
    if swe is None:
        raise RuntimeError("This integration audit requires Swiss Ephemeris")
    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_J2000
        | swe.FLG_EQUATORIAL
        | swe.FLG_XYZ
        | swe.FLG_TRUEPOS
        | swe.FLG_ICRS
        | swe.FLG_SPEED
    )
    cases = []
    files = {}
    missing = []
    with runtime.preserve_ephemeris_path():
        for reference in fixture["references"]:
            body = reference["body"]
            missing.extend(
                {"body": body, **row}
                for row in reference["unavailable_requested_epochs"]
            )
            for row in reference["rows"]:
                values, returned = runtime.ephemeris_call(
                    "calc", row["jd_tt"], PLANET_SWISSEPH_IDS[body], flags
                )
                actual = values[:3]
                component = max(abs(a - b) for a, b in zip(actual, row["position_au"]))
                angle = angular_error_arcsec(actual, row["position_au"])
                model = runtime.ephemeris_model_from_retflag(returned)
                cases.append(
                    {
                        "body": body,
                        "date_tt": row["date_tt"],
                        "jd_tt": row["jd_tt"],
                        "component_error_au": component,
                        "angular_error_arcsec": angle,
                        "model": model,
                        "passes_available_numeric_check": (
                            model == expected_model
                            and math.isfinite(component)
                            and math.isfinite(angle)
                            and component <= protocol["component_tolerance_au"]
                            and angle <= protocol["angular_tolerance_arcsec"]
                        ),
                    }
                )
                if velocity_protocol is not None:
                    case = cases[-1]
                    case["passes_position_check"] = case[
                        "passes_available_numeric_check"
                    ]
                    case.update(
                        velocity_diagnostics(
                            values, returned, row, velocity_protocol, swe.FLG_SPEED
                        )
                    )
                    case["passes_available_numeric_check"] = (
                        case["passes_position_check"] and case["passes_velocity_check"]
                    )
                path, start, end, denum = swe.get_current_file_data(
                    1 if body == "Moon" and model != "jpl" else 0
                )
                if path:
                    file = Path(path)
                    if path not in files:
                        if model == "jpl":
                            header = jpl_header(file)
                            start = header["start_julian_day_tdb"]
                            end = header["end_julian_day_tdb"]
                            denum = header["de_number"]
                        digest = hashlib.sha256()
                        with file.open("rb") as source:
                            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                                digest.update(chunk)
                        files[path] = {
                            "start_jd": start,
                            "end_jd": end,
                            "range_time_scale": (
                                "TDB" if model == "jpl" else "native_TT"
                            ),
                            "de_number": denum,
                            "sha256": digest.hexdigest(),
                            "observed_bodies": [],
                        }
                    if body not in files[path]["observed_bodies"]:
                        files[path]["observed_bodies"].append(body)
    failed = [c for c in cases if not c["passes_available_numeric_check"]]
    result = {
        "platform": platform.platform(),
        "swisseph_version": swe.version,
        "requested_model": expected_model,
        "scope": protocol["scope"],
        "angular_tolerance_arcsec": protocol["angular_tolerance_arcsec"],
        "component_tolerance_au": protocol["component_tolerance_au"],
        "cases": cases,
        "available_compared": len(cases),
        "numeric_failures": failed,
        "original_requested_comparisons": len(protocol["dates_tt"])
        * len(protocol["targets"]),
        "supplementary_available": sum(
            c["date_tt"] in protocol["supplemental_dates_tt"] for c in cases
        ),
        "missing_original_references": missing,
        "all_original_requested_epochs_validated": not missing and not failed,
        "max_component_error_au": max(c["component_error_au"] for c in cases),
        "max_angular_error_arcsec": max(c["angular_error_arcsec"] for c in cases),
        "data_files": files,
        "status": (
            "numeric_failure"
            if failed
            else (
                "incomplete_external_reference"
                if missing
                else "bounded_comparisons_passed"
            )
        ),
    }
    if velocity_protocol is not None:
        result.update(
            {
                "velocity_protocol": velocity_protocol,
                "position_numeric_failure_count": sum(
                    not c["passes_position_check"] for c in cases
                ),
                "velocity_numeric_failure_count": sum(
                    not c["passes_velocity_check"] for c in cases
                ),
                "max_component_velocity_error_au_per_day": max(
                    (
                        c["component_velocity_error_au_per_day"]
                        for c in cases
                        if c["component_velocity_error_au_per_day"] is not None
                    ),
                    default=None,
                ),
                "max_direction_derivative_error_arcsec_per_day": max(
                    (
                        c["direction_derivative_error_arcsec_per_day"]
                        for c in cases
                        if c["direction_derivative_error_arcsec_per_day"] is not None
                    ),
                    default=None,
                ),
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ephe", type=Path, required=True)
    parser.add_argument(
        "--jpl-file",
        help="Strict DE441 basename in --ephe; rejects native fallback",
    )
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--velocity-protocol", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ["SE_EPHE_PATH"] = str(args.ephe.resolve())
    if args.jpl_file:
        os.environ["FATEBRIDGE_JPL_FILE"] = args.jpl_file
    else:
        os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    fixture = json.loads(args.reference.read_text())
    assert (
        fixture["protocol_sha256"]
        == hashlib.sha256(args.protocol.read_bytes()).hexdigest()
    )
    velocity_protocol = (
        json.loads(args.velocity_protocol.read_text())
        if args.velocity_protocol
        else None
    )
    if velocity_protocol is not None:
        assert (
            velocity_protocol["reference_fixture_sha256"]
            == hashlib.sha256(args.reference.read_bytes()).hexdigest()
        )
    result = audit(
        json.loads(args.protocol.read_text()),
        fixture,
        expected_model="jpl" if args.jpl_file else "swieph",
        velocity_protocol=velocity_protocol,
    )
    if args.velocity_protocol:
        result["velocity_protocol_sha256"] = hashlib.sha256(
            args.velocity_protocol.read_bytes()
        ).hexdigest()
    result["reference_sha256"] = hashlib.sha256(args.reference.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "status",
                    "available_compared",
                    "supplementary_available",
                    "max_component_error_au",
                    "max_angular_error_arcsec",
                    "all_original_requested_epochs_validated",
                )
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
