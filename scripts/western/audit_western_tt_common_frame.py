"""Audit all sealed directions in declared frames and reference points."""

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import math
import zipfile
from pathlib import Path

from fatebridge.core.astro import runtime
from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.astro.reference_points import ephemeris_reference_points
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/astro/tt_common_frame"


def unit(longitude, latitude):
    a, d = map(math.radians, (longitude, latitude))
    return math.cos(a) * math.cos(d), math.sin(a) * math.cos(d), math.sin(d)


def angular_distance(a, b):
    cross = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    return (
        math.degrees(
            math.atan2(math.hypot(*cross), math.fsum(x * y for x, y in zip(a, b)))
        )
        * 3600
    )


def validate_corpus():
    manifest = json.loads((FIXTURE / "source-files.json").read_text())
    for filename, expected in manifest["files"].items():
        if hashlib.sha256((FIXTURE / filename).read_bytes()).hexdigest() != expected:
            raise ValueError("Independent physical reference changed: " + filename)
    plan = json.loads((FIXTURE / "protocol.json").read_text())
    ref = json.loads(gzip.decompress((FIXTURE / "reference.json.gz").read_bytes()))
    assert ref["production_imports"] is False
    assert (
        ref["protocol_sha256"]
        == hashlib.sha256((FIXTURE / "protocol.json").read_bytes()).hexdigest()
    )
    with zipfile.ZipFile(FIXTURE / "raw-responses.zip") as z:
        for case in ref["cases"]:
            for data in case["targets"].values():
                receipt = data["receipt"]
                assert (
                    hashlib.sha256(z.read(receipt["raw_file"])).hexdigest()
                    == receipt["response_sha256"]
                )
    return plan, ref


@runtime.preserve_ephemeris_path()
def audit(plan, ref):
    swe = runtime.swe
    assert [swe.version, importlib.metadata.version("pyswisseph")] == plan[
        "native_version_scope"
    ]
    selected = configured_ephemeris_path()
    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_EQUATORIAL
        | swe.FLG_ICRS
        | swe.FLG_J2000
        | swe.FLG_SPEED
    )
    trace = PhysicalEphemerisTrace()
    rows = []
    models = {}
    cache = {}
    with use_ut1_source("iers_c04"):
        for case in ref["cases"]:
            for name, target in case["targets"].items():
                control = name in plan["body_control_targets"]
                planet = name.split("_")[0]
                for sample in target["rows"]:
                    tt = sample["tt"]
                    key = planet, tt
                    if key not in cache:
                        actual = _swisseph_planet_state(
                            planet,
                            julian_day_tt=tt,
                            source_trace=trace,
                            correct_motion=False,
                        )
                        if actual is None or actual[1] != "swieph":
                            raise ValueError(
                                "Declared Swiss physical state unavailable"
                            )
                        state, model = actual
                        models[planet] = model
                        inertial, returned = runtime.ephemeris_call(
                            "calc", tt, PLANET_SWISSEPH_IDS[planet], flags
                        )
                        assert_physical_configuration(selected)
                        if (
                            returned & flags != flags
                            or runtime.ephemeris_model_from_retflag(returned) != model
                        ):
                            raise ValueError("Native ICRF coordinate contract changed")
                        if not all(math.isfinite(x) for x in inertial):
                            raise ValueError("Nonfinite native ICRF direction")
                        cache[key] = state, unit(inertial[0], inertial[1])
                    state, inertial_unit = cache[key]
                    native_unit = unit(state["longitude"], state["latitude"])
                    errors = {
                        model: angular_distance(native_unit, unit(*position))
                        for model, position in sample["projections"].items()
                    }
                    rows.append(
                        dict(
                            case_id=case["case_id"],
                            planet=planet,
                            reference_target=target["target"],
                            same_reference_point=not control,
                            tt=tt,
                            native_longitude=state["longitude"],
                            native_latitude=state["latitude"],
                            icrf_error_arcseconds=angular_distance(
                                inertial_unit, unit(*sample["icrf"])
                            ),
                            projected_errors_arcseconds=errors,
                            primary_passed=errors[plan["primary_projection"]]
                            <= plan["position_line_arcseconds"],
                        )
                    )
            print("Completed common-frame case", case["case_id"], flush=True)
    primary = [r for r in rows if r["same_reference_point"]]
    controls = [r for r in rows if not r["same_reference_point"]]
    assert len(primary) == plan["all_primary_positions_required"]
    assert len(controls) == plan["body_control_positions_required"]

    def summary(data):
        return dict(
            count=len(data),
            icrf_failed=sum(
                r["icrf_error_arcseconds"] > plan["position_line_arcseconds"]
                for r in data
            ),
            icrf_maximum_arcseconds=max(r["icrf_error_arcseconds"] for r in data),
            frames={
                model: dict(
                    failed=sum(
                        r["projected_errors_arcseconds"][model]
                        > plan["position_line_arcseconds"]
                        for r in data
                    ),
                    maximum_arcseconds=max(
                        r["projected_errors_arcseconds"][model] for r in data
                    ),
                )
                for model in [plan["primary_projection"], *plan["other_projections"]]
            },
        )

    return dict(
        protocol_id=plan["protocol_id"],
        primary_projection=plan["primary_projection"],
        position_line_arcseconds=plan["position_line_arcseconds"],
        primary=summary(primary),
        mixed_point_controls=summary(controls),
        rows=rows,
        physical_ephemeris_source=trace.finish(),
        reference_points=ephemeris_reference_points(models, []),
        complete_motion_derivative_tested=False,
        original_cross_frame_7684_failures_replaced=False,
        production_coordinates_modified=False,
        full_original_text_acceptance=False,
        actual_model_fidelity_tested=False,
        real_world_observations_added=0,
        finite_declared_primary_comparison_passed=all(
            r["primary_passed"] for r in primary
        ),
    )


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Existing audit results cannot be overwritten")
    plan, ref = validate_corpus()
    result = audit(plan, ref)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "primary",
                    "mixed_point_controls",
                    "finite_declared_primary_comparison_passed",
                )
            },
            indent=2,
        )
    )
    raise SystemExit(0 if result["finite_declared_primary_comparison_passed"] else 1)


if __name__ == "__main__":
    main()
