"""Collect a frozen apparent ICRF direction/rate oracle, then project with ERFA.

Maintenance only: run outside the project with pyerfa==2.0.1.5/numpy==2.5.4.
Never import FateBridge or Swiss here. Ordinary tests use the frozen result.
All dates, targets, engineering thresholds and frame step precede collection.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import erfa

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
VERSIONS = {"pyerfa": "2.0.1.5", "numpy": "2.5.4"}
MONTHS = dict(
    zip("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), range(1, 13))
)


def julian_day_tt(date):
    value = datetime.fromisoformat(date)
    return (
        value.toordinal()
        + 1721424.5
        + (value.hour * 3600 + value.minute * 60 + value.second) / 86400
    )


def request(target, dates, protocol):
    parameters = {
        **protocol["reference_parameters"],
        "format": "json",
        "COMMAND": f"'{target}'",
        "MAKE_EPHEM": "'YES'",
        "OBJ_DATA": "'NO'",
        "TLIST": "'" + " ".join(format(julian_day_tt(d), ".17g") for d in dates) + "'",
        "TLIST_TYPE": "'JD'",
    }
    url = URL + "?" + urlencode(parameters)
    raw = subprocess.check_output(
        ["curl", "--fail", "--silent", "--show-error", "--max-time", "45", url]
    )
    response = json.loads(raw)
    return {
        "parameters": parameters,
        "request_url": url,
        "raw_response_utf8": raw.decode(),
        "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
        "response": response,
        "result_sha256": hashlib.sha256(
            response.get("result", "").encode()
        ).hexdigest(),
    }


def direction_and_rate(ra_degrees, dec_degrees, ra_cosdec_arcsec_hour, dec_arcsec_hour):
    """The supplied RA rate ALREADY includes cos(dec); do not apply it twice."""
    ra, dec = map(math.radians, (ra_degrees, dec_degrees))
    scale = math.pi / 180 / 3600 * 24
    unit = [math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]
    east = [-math.sin(ra), math.cos(ra), 0]
    north = [
        -math.sin(dec) * math.cos(ra),
        -math.sin(dec) * math.sin(ra),
        math.cos(dec),
    ]
    rate = [
        (ra_cosdec_arcsec_hour * a + dec_arcsec_hour * b) * scale
        for a, b in zip(east, north)
    ]
    return unit, rate


def frame_matrix(jd_tt, offset_days=0):
    t = jd_tt - 2451545.0 + offset_days
    matrix = erfa.pnm06a(2451545.0, t)
    epsilon = erfa.obl06(2451545.0, t) + erfa.nut06a(2451545.0, t)[1]
    c, s = math.cos(epsilon), math.sin(epsilon)
    return [
        list(map(float, matrix[0])),
        [float(c * matrix[1][i] + s * matrix[2][i]) for i in range(3)],
        [float(-s * matrix[1][i] + c * matrix[2][i]) for i in range(3)],
    ]


def project_motion(jd_tt, unit, rate, step):
    matrix = frame_matrix(jd_tt)
    plus, minus = frame_matrix(jd_tt, step), frame_matrix(jd_tt, -step)
    derivative = [
        [(a - b) / (2 * step) for a, b in zip(x, y)] for x, y in zip(plus, minus)
    ]
    q = [math.fsum(a * b for a, b in zip(row, unit)) for row in matrix]
    moving = [math.fsum(a * b for a, b in zip(row, rate)) for row in matrix]
    frame = [math.fsum(a * b for a, b in zip(row, unit)) for row in derivative]
    qdot = [a + b for a, b in zip(moving, frame)]
    denominator = q[0] ** 2 + q[1] ** 2
    longitude = math.degrees(math.atan2(q[1], q[0])) % 360
    speed = math.degrees((q[0] * qdot[1] - q[1] * qdot[0]) / denominator)
    omitted_frame_speed = math.degrees(
        (q[0] * moving[1] - q[1] * moving[0]) / denominator
    )
    return {
        "longitude_degrees": longitude,
        "longitude_speed_degrees_per_day": speed,
        "omitted_frame_derivative_speed_degrees_per_day": omitted_frame_speed,
        "frame_rate_contribution_arcsec_per_day": (speed - omitted_frame_speed) * 3600,
    }


def parse_rows(record, dates, protocol):
    text = record["response"].get("result", "")
    if "$$SOE\n" not in text:
        raise ValueError("No observer table: " + record["response"].get("error", text))
    if not all(x in text for x in ["ICRF", "I_dRA*cosD", "I_d(DEC)/dt", "Date__(TT)"]):
        raise ValueError("Unexpected apparent frame/rate/time header")
    rows = []
    for raw in csv.reader(
        io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0])
    ):
        match = re.fullmatch(
            r"\s*(\d{1,4})-(\w{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.\d+\s*", raw[0]
        )
        if match is None:
            raise ValueError("Unexpected observer epoch format")
        year, month, day, hour, minute, second = match.groups()
        date = datetime(
            int(year), MONTHS[month], int(day), int(hour), int(minute), int(second)
        ).isoformat()
        ra, dec, rate_ra, rate_dec = map(float, raw[3:7])
        if not all(math.isfinite(x) for x in [ra, dec, rate_ra, rate_dec]):
            raise ValueError("Nonfinite apparent reference")
        unit, rate = direction_and_rate(ra, dec, rate_ra, rate_dec)
        row = {
            "date_tt": date,
            "jd_tt": julian_day_tt(date),
            "ra_degrees": ra,
            "dec_degrees": dec,
            "ra_cosdec_arcsec_per_hour": rate_ra,
            "dec_arcsec_per_hour": rate_dec,
            "printed_values": [v.strip() for v in raw[3:7]],
            "icrf_unit_direction": unit,
            "icrf_direction_derivative_per_day": rate,
        }
        if date in protocol["modern_display_frame_dates_tt"]:
            step = protocol["frame_derivative_step_days"]
            projection = project_motion(row["jd_tt"], unit, rate, step)
            half = project_motion(row["jd_tt"], unit, rate, step / 2)
            projection["half_step_speed_difference_arcsec_per_day"] = (
                half["longitude_speed_degrees_per_day"]
                - projection["longitude_speed_degrees_per_day"]
            ) * 3600
            row["erfa_display_frame"] = projection
        rows.append(row)
    names = [row["date_tt"] for row in rows]
    if len(names) != len(set(names)) or set(names) != set(dates):
        raise ValueError("Observer epoch coverage differs from requested dates")
    return rows


def generate(protocol_path):
    protocol = json.loads(protocol_path.read_text())
    for package, expected in VERSIONS.items():
        if importlib.metadata.version(package) != expected:
            raise RuntimeError(
                "Independent reference dependencies differ from fixed versions"
            )
    original = protocol["original_dates_tt"]
    dates = (
        original
        + protocol["supplementary_dates_tt"]
        + protocol["modern_display_frame_dates_tt"]
    )
    if len(dates) != len(set(dates)):
        raise ValueError("Protocol dates overlap")
    references = []
    for body, target in protocol["targets"].items():
        first = request(target, dates, protocol)
        failed = None
        missing = []
        if "$$SOE\n" not in first["response"].get("result", ""):
            # Probe, do not assume, the previously unavailable original endpoint.
            # Other failures abort collection rather than silently dropping rows.
            failed = first
            endpoint = original[-1]
            probe = request(target, [endpoint], protocol)
            reason = probe["response"].get("error", probe["response"].get("result", ""))
            if "No ephemeris" not in reason:
                raise ValueError("Cannot establish a missing original endpoint")
            missing.append({"date_tt": endpoint, "reason": reason, "probe": probe})
            first = request(
                target, [date for date in dates if date != endpoint], protocol
            )
        available_dates = [
            date for date in dates if date not in {m["date_tt"] for m in missing}
        ]
        rows = parse_rows(first, available_dates, protocol)
        references.append(
            {
                "body": body,
                "target_id": target,
                **first,
                "failed_original_request": failed,
                "unavailable_requested_epochs": missing,
                "rows": rows,
            }
        )
        print(
            f"{body}: {len(rows)} apparent directions/rates; {len(missing)} missing original epochs",
            flush=True,
        )
    forbidden = [
        name
        for name in sys.modules
        if any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in ["fatebridge", "swisseph"]
        )
    ]
    if forbidden:
        raise RuntimeError("Reference process imported a forbidden implementation")
    return {
        "source": URL,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "versions": {name: importlib.metadata.version(name) for name in VERSIONS},
        "erfa_version": erfa.version.erfa_version,
        "sofa_version": erfa.version.sofa_version,
        "forbidden_implementation_imports": [],
        "references": references,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = generate(args.protocol)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
