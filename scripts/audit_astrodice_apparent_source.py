"""Audit actual source-model apparent position and delivered display rates.

Reference math is independent of the native corrections; display orientation
still shares native geometry. All planned layers and method failures remain
visible. This study cannot regrade older Horizons comparisons.
"""

import argparse
import hashlib
import json
import math
import os
import traceback
from pathlib import Path

from scripts.audit_astrodice_local_motion import orientation_derivative
from scripts.audit_astrodice_v6_wide import cross, dot, rotate, unit

PASS = "declared_source_model_lines_satisfied"
FAIL = "numeric_failure_against_declared_source_model"
UNKNOWN = "source_or_method_unqualified"
AS = math.degrees(1) * 3600


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_frames(providers, comparison):
    """Retain every declared frame, including errors after a numerical failure."""
    if set(providers) != {"tropical", "lahiri"}:
        raise ValueError("All declared display frames are required")

    def capture(callback, require_status=False):
        try:
            value = callback()
            if require_status and value.get("status") not in {
                PASS,
                FAIL,
                UNKNOWN,
                "candidate_error",
            }:
                raise ValueError("Unknown frame outcome")
            return value, None
        except Exception as error:
            return None, {
                "status": "candidate_error",
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }

    # Preserve the normal native state-call order before frame projections.
    states = [(name, *capture(provider)) for name, provider in providers.items()]
    frames = {}
    for name, state, error in states:
        if error is not None:
            frames[name] = error
        else:
            result, error = capture(lambda: comparison(name, state), True)
            frames[name] = error if error is not None else result
    statuses = [value["status"] for value in frames.values()]
    status = next(
        (value for value in (FAIL, "candidate_error", UNKNOWN) if value in statuses),
        PASS,
    )
    return {"status": status, "frames": frames}


def project(center, matrix, derivatives):
    position = rotate(matrix, list(map(float, center["direction_icrf"])))
    velocity = rotate(matrix, list(map(float, center["derivative_per_day"])))
    radius_squared = position[0] ** 2 + position[1] ** 2
    if radius_squared < 0.0001:
        raise ValueError("Source display longitude is ill-conditioned")
    rates = []
    for derivative in derivatives:
        frame = rotate(derivative, list(map(float, center["direction_icrf"])))
        v = [a + b for a, b in zip(velocity, frame)]
        rates.append((position[0] * v[1] - position[1] * v[0]) / radius_squared * AS)
    spread = abs(rates[0] - rates[1])
    return {
        "rate_arcsec_per_day": rates[-1],
        "frame_check_difference_arcsec_per_day": spread,
        "arithmetic_and_frame_check_radius_arcsec_per_day": spread + 1e-7,
        "frame_check_qualified": spread <= 0.00002,
    }


def audit(
    run,
    fixture,
    reference_path,
    case_index,
    *,
    expected_derivative_method_id="fatebridge_complete_position_derivative_v8",
):
    root = Path(__file__).resolve().parents[1]
    reference = json.loads(reference_path.read_text())
    row = reference["rows"][case_index]
    original = json.loads((fixture / "geometric-reference.json").read_text())["rows"][
        row["window_index"]
    ]
    kernel = fixture / original["kernel_path"]
    if (
        digest(kernel) != original["kernel_sha256"]
        or os.environ.get("FATEBRIDGE_JPL_FILE") != kernel.name
        or Path(os.environ["SE_EPHE_PATH"]).resolve() != kernel.parent.resolve()
    ):
        raise ValueError("Declared source-window kernel configuration changed")
    from fatebridge.core.astro import ephemeris, runtime
    from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
    from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
    from fatebridge.core.astro.zodiac import native_lahiri_positions

    if not Path(runtime.__file__).resolve().is_relative_to(root):
        raise ValueError("Native sampler imported outside project")
    trace = PhysicalEphemerisTrace()
    jd, body = row["native_numeric_argument"], row["body"]
    layers = {}
    if row.get("position_status") != "qualified_under_declared_source_position_model":
        layers["position"] = {
            "status": UNKNOWN,
            "reason": "reference_position_unqualified",
        }
    else:
        try:
            flags = (
                runtime.swe.FLG_SWIEPH
                | runtime.swe.FLG_SPEED
                | runtime.swe.FLG_XYZ
                | runtime.swe.FLG_J2000
                | runtime.swe.FLG_ICRS
                | runtime.swe.FLG_EQUATORIAL
            )
            value, ret = runtime.ephemeris_call(
                "calc", jd, PLANET_SWISSEPH_IDS[body], flags
            )
            mask = 0
            for name in COORDINATE_FLAGS:
                mask |= getattr(runtime.swe, name)
            if (
                runtime.ephemeris_model_from_retflag(ret) != "jpl"
                or ret < 0
                or ret & mask != (flags | runtime.swe.FLG_NONUT) & mask
                or len(value) != 6
                or not all(math.isfinite(v) for v in value)
            ):
                raise ValueError("Apparent ICRF source/coordinate flags changed")
            trace.observe(body + "_source_apparent_position", "jpl")
            actual = unit(value[:3])
            expected = unit(
                list(map(float, row["position_centers"][-1]["direction_icrf"]))
            )
            error = (
                math.atan2(math.hypot(*cross(actual, expected)), dot(actual, expected))
                * AS
            )
            layers["position"] = {
                "status": (
                    FAIL
                    if error - 1e-9 > 0.02
                    else PASS if error + 1e-9 <= 0.02 else UNKNOWN
                ),
                "difference_arcsec": error,
                "fixed_line_arcsec": 0.02,
                "arithmetic_radius_arcsec": 1e-9,
                "native_icrf_position_and_raw_velocity": list(value),
            }
        except Exception as error:
            layers["position"] = {
                "status": "candidate_error",
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
    if row.get("status") != "qualified_under_declared_continuous_source_model":
        layers["rate"] = {
            "status": UNKNOWN,
            "reason": "reference_derivative_unqualified",
        }
    else:
        try:
            metadata = {}

            def tropical_state():
                state, model = ephemeris._swisseph_planet_state(
                    body,
                    jd,
                    julian_day_tt=jd,
                    source_trace=trace,
                    motion_metadata=metadata,
                )
                if model != "jpl":
                    raise ValueError("Delivered rate used another physical backend")
                return state

            def lahiri_state():
                return native_lahiri_positions(
                    [body],
                    julian_day_ut1=jd,
                    julian_day_tt=jd,
                    source_trace=trace,
                    motion_metadata=metadata,
                )[body]

            def comparison(name, state):
                sidereal = name == "lahiri"
                matrix, derivatives, geometry = orientation_derivative(
                    jd, sidereal, "jpl", trace
                )
                projected = project(row["centers"][-1], matrix, derivatives)
                policy = metadata["complete_position_derivatives"][body + ":" + name]
                method_ok = (
                    policy.get("status") == "applied"
                    and policy.get("method_id") == expected_derivative_method_id
                )
                error = abs(
                    state["longitude_speed"] * 3600 - projected["rate_arcsec_per_day"]
                )
                radius = projected["arithmetic_and_frame_check_radius_arcsec_per_day"]
                # Actual numeric failure takes precedence even if the expected
                # derivative method was unavailable and native speed was kept.
                status = (
                    FAIL
                    if error - radius > 0.002
                    else (
                        PASS
                        if method_ok
                        and projected["frame_check_qualified"]
                        and error + radius <= 0.002
                        else UNKNOWN
                    )
                )
                return {
                    "status": status,
                    "actual_delivered_rate_degrees_per_day": state["longitude_speed"],
                    "reference": projected,
                    "difference_arcsec_per_day": error,
                    "conditional_error_upper_arcsec_per_day": error + radius,
                    "method_qualified": method_ok,
                    "candidate_policy": policy,
                    "frame_geometry": geometry,
                }

            collected = collect_frames(
                {"tropical": tropical_state, "lahiri": lahiri_state}, comparison
            )
            layers["rate"] = {**collected, "fixed_line_arcsec_per_day": 0.002}
        except Exception as error:
            layers["rate"] = {
                "status": "candidate_error",
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
    statuses = [v["status"] for v in layers.values()]
    overall = next(
        (s for s in (FAIL, "candidate_error", UNKNOWN) if s in statuses), PASS
    )
    return {
        "id": row["id"],
        "role": row["role"],
        "body": body,
        "date_tdb": row["date_tdb"],
        "native_numeric_argument": jd,
        "status": overall,
        "exit_code": (
            1
            if overall in {FAIL, "candidate_error"}
            else 2 if overall == UNKNOWN else 0
        ),
        "layers": layers,
        "physical_sources": trace.finish(),
        "reference_sha256": digest(reference_path),
        "full_goal_complete": False,
        "original_Horizons_results_regraded": False,
        "scope": "Declared continuous source position/derivative, same numeric TDB argument under native TT approximation, shared display orientation. Not full TT conversion, independent frame certification or observational accuracy.",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "fixture", "reference", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--case-index", type=int, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = audit(args.run, args.fixture, args.reference, args.case_index)
    with args.output.open("x") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(result["id"], result["status"])
    raise SystemExit(result["exit_code"])
