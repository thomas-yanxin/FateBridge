"""Measure every frozen ten-body tropical/Lahiri reference row.

Keep the operator's actual backend, every failure and the original engineering
line. Exit 1 is a measured failure; exit 2 is unavailable evidence/source data.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from fatebridge.core.astro import ephemeris, runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.astro.zodiac import native_lahiri_positions
from scripts.guolao.audit_guolao_motion import load_reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_SHA256 = "7500bb8ad80313e886b461882ab81386110e87a933181df3ec67fec1cc625675"
REFERENCE_SHA256 = "3441dca5cb939edbfef37171da87b7c44a0a56bb0a6800c2e126784030fda78b"


def loaded(protocol_path: Path, reference_path: Path) -> tuple[dict, dict]:
    return load_reference(
        protocol_path,
        reference_path,
        protocol_sha256=PROTOCOL_SHA256,
        reference_sha256=REFERENCE_SHA256,
    )


def evaluate(protocol: dict, reference: dict) -> dict[str, Any]:
    rows = []
    for target in reference["references"]:
        body = target["body"]
        for ref in target["rows"]:
            jd = ref["jd_tt"]
            for frame in protocol["frames"]:
                sidereal = frame == "lahiri"
                policy: dict[str, Any] = {}
                trace = PhysicalEphemerisTrace()
                row: dict[str, Any] = {
                    "body": body,
                    "date_tt": ref["date_tt"],
                    "frame": frame,
                    "source_error": None,
                    "reference_resolved": False,
                    "passed": False,
                }
                frame_key = "erfa_lahiri_frame" if sidereal else "erfa_display_frame"
                uncertainty = (
                    "lahiri_frame_step_difference_arcsec_per_day"
                    if sidereal
                    else "frame_step_difference_arcsec_per_day"
                )
                resolved = (
                    ref["status"] == "available"
                    and ref["stencil_difference_arcsec_per_day"]
                    <= protocol["reference_stencil_uncertainty_line_arcsec_per_day"]
                    and ref[uncertainty]
                    <= protocol["frame_step_uncertainty_line_arcsec_per_day"]
                )
                row["reference_resolved"] = resolved
                try:
                    if sidereal:
                        with runtime.preserve_ephemeris_path():
                            runtime.ephemeris_call(
                                "set_sid_mode", runtime.swe.SIDM_LAHIRI, 0, 0
                            )
                            coordinates, flags = runtime.ephemeris_call(
                                "calc",
                                jd,
                                PLANET_SWISSEPH_IDS[body],
                                runtime.swe.FLG_SWIEPH
                                | runtime.swe.FLG_SPEED
                                | runtime.swe.FLG_SIDEREAL,
                            )
                            model = runtime.ephemeris_model_from_retflag(flags)
                            trace.observe(body, model)
                            states = native_lahiri_positions(
                                [body],
                                julian_day_ut1=jd,
                                julian_day_tt=jd,
                                source_trace=trace,
                                motion_metadata=policy,
                            )
                            state = states[body]
                            if (state["longitude"], state["latitude"]) != tuple(
                                coordinates[:2]
                            ):
                                raise ValueError("Sidereal source probe changed")
                    else:
                        result = ephemeris._swisseph_planet_state(
                            body,
                            jd,
                            julian_day_tt=jd,
                            source_trace=trace,
                            motion_metadata=policy,
                        )
                        if result is None:
                            raise ValueError("Physical state unavailable")
                        state, model = result
                    trace.finish()
                    row.update(state=state, actual_model=model, motion_policy=policy)
                    if ref["status"] == "available":
                        expected = ref[frame_key]["longitude_speed_degrees_per_day"]
                        residual = (state["longitude_speed"] - expected) * 3600
                        row.update(
                            reference_speed=expected,
                            longitude_residual_arcsec=math.remainder(
                                state["longitude"]
                                - ref[frame_key]["longitude_degrees"],
                                360,
                            )
                            * 3600,
                            native_signed_residual_arcsec_per_day=(
                                state["longitude_speed_native"] - expected
                            )
                            * 3600,
                            signed_residual_arcsec_per_day=residual,
                            passed=resolved
                            and math.isfinite(residual)
                            and abs(residual)
                            <= protocol[
                                "display_longitude_speed_tolerance_arcsec_per_day"
                            ],
                        )
                except Exception as error:
                    row["source_error"] = {
                        "type": type(error).__name__,
                        "message": str(error),
                    }
                rows.append(row)
    return {
        "audit_version": "shared_moshier_frames_holdout_v1",
        "scope": "Ten physical bodies in two actual display frames at twelve predeclared TT epochs. Independent reference pipeline, possibly shared DE441 dynamics. No whole-domain, original-page, station-time, real-model semantic or human-outcome acceptance.",
        "protocol_sha256": PROTOCOL_SHA256,
        "reference_sha256": REFERENCE_SHA256,
        "requested": len(protocol["dates_tt"])
        * len(protocol["targets"])
        * len(protocol["frames"]),
        "passed": sum(row["passed"] for row in rows),
        "source_errors": sum(row["source_error"] is not None for row in rows),
        "unresolved_reference": sum(not row["reference_resolved"] for row in rows),
        "numerical_subset_checks_passed": all(row["passed"] for row in rows),
        "rows": rows,
        "all_four_objectives_validated": False,
        "authority_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "tests/data/astro/moshier_frames/protocol.json",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=ROOT / "tests/data/astro/moshier_frames/reference.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = evaluate(*loaded(args.protocol, args.reference))
    except (OSError, ValueError, KeyError) as error:
        args.output.write_text(
            json.dumps(
                {
                    "reference_validation_error": str(error),
                    "numerical_subset_checks_passed": False,
                    "all_four_objectives_validated": False,
                    "authority_certified": False,
                },
                indent=2,
            )
            + "\n"
        )
        return 2
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}))
    if result["source_errors"] or result["unresolved_reference"]:
        return 2
    return 0 if result["numerical_subset_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
