"""Independent apparent directions projected into tropical and standard Lahiri.

Maintenance only, in the isolated pinned ERFA/NumPy environment. This defines
the Swiss standard-Lahiri frame from its published anchor and precession model;
it does not establish agreement with an inspected original almanac page.
"""

import argparse
import json
import math
from pathlib import Path

import erfa
import gen_guolao_motion_reference as collector
import numpy as np

LAHIRI_ANCHOR_JD_TT = 2435553.5
LAHIRI_ANCHOR_DEGREES = 23.250182778 - 0.004658035


def julian_epoch(jd_tt):
    return 2000.0 + (jd_tt - 2451545.0) / 365.25


def mean_obliquity(jd_tt):
    epoch = julian_epoch(jd_tt)
    return math.acos(float(np.dot(erfa.ltpequ(epoch), erfa.ltpecl(epoch))))


def reference_ecliptic_longitude(vector):
    epsilon = mean_obliquity(LAHIRI_ANCHOR_JD_TT)
    return math.degrees(
        math.atan2(
            math.cos(epsilon) * vector[1] + math.sin(epsilon) * vector[2],
            vector[0],
        )
    )


def mean_ayanamsha(jd_tt):
    reference = erfa.ltp(julian_epoch(LAHIRI_ANCHOR_JD_TT))
    current = erfa.ltp(julian_epoch(jd_tt))
    axis = np.array([1.0, 0.0, 0.0])
    equinox = reference @ current.T @ axis
    # Standard Lahiri's reference was expressed with IAU1976 precession.
    correction = erfa.pmat76(LAHIRI_ANCHOR_JD_TT, 0.0) @ reference.T @ axis
    return (
        -reference_ecliptic_longitude(equinox)
        + LAHIRI_ANCHOR_DEGREES
        - reference_ecliptic_longitude(correction)
    ) % 360


def frame_matrix(jd_tt):
    epsilon = mean_obliquity(jd_tt)
    c, s = math.cos(epsilon), math.sin(epsilon)
    ecliptic = np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
    aya = math.radians(mean_ayanamsha(jd_tt))
    c, s = math.cos(aya), math.sin(aya)
    zero_point = np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
    return zero_point @ ecliptic @ erfa.ltpb(julian_epoch(jd_tt))


def project_lahiri_motion(jd_tt, unit, rate, step):
    matrix = frame_matrix(jd_tt)
    derivative = (frame_matrix(jd_tt + step) - frame_matrix(jd_tt - step)) / (2 * step)
    q = matrix @ np.asarray(unit)
    moving = matrix @ np.asarray(rate)
    frame = derivative @ np.asarray(unit)
    qdot = moving + frame
    denominator = q[0] ** 2 + q[1] ** 2

    def longitude_rate(vector):
        return float(math.degrees((q[0] * vector[1] - q[1] * vector[0]) / denominator))

    speed = longitude_rate(qdot)
    omitted = longitude_rate(moving)
    return {
        "longitude_degrees": math.degrees(math.atan2(q[1], q[0])) % 360,
        "longitude_speed_degrees_per_day": speed,
        "omitted_frame_derivative_speed_degrees_per_day": omitted,
        "frame_rate_contribution_arcsec_per_day": (speed - omitted) * 3600,
        "mean_ayanamsha_degrees": mean_ayanamsha(jd_tt),
    }


def add_lahiri_frames(result, protocol):
    step = protocol["frame_derivative_step_days"]
    for target in result["references"]:
        for row in target["rows"]:
            if row["status"] != "available":
                continue
            arguments = (
                row["jd_tt"],
                row["icrf_unit_direction"],
                row["seven_point_derivatives"][str(protocol["chosen_step_seconds"])],
            )
            value = project_lahiri_motion(*arguments, step)
            half_step = project_lahiri_motion(*arguments, step / 2)
            row["erfa_lahiri_frame"] = value
            row["lahiri_frame_step_difference_arcsec_per_day"] = (
                abs(
                    value["longitude_speed_degrees_per_day"]
                    - half_step["longitude_speed_degrees_per_day"]
                )
                * 3600
            )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    for name in ("protocol", "archive", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refuse to replace an earlier reference")
    protocol = json.loads(args.protocol.read_text())
    result = add_lahiri_frames(collector.generate(args), protocol)
    result["projection_scope"] = (
        "IAU2006/2000A tropical and code-defined standard-Lahiri moving frames. "
        "Independent reference pipeline; NASA and Swiss can share DE441 dynamics. "
        "No inspected original-page or human-outcome validation."
    )
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
