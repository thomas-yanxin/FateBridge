"""Select near-knot conditions using unbent source geometry alone.

No candidate, apparent-direction sampler or derivative reference is imported.
Both prospective cohorts are fixed before either is evaluated.
"""

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN
from decimal import Decimal as N
from decimal import localcontext
from pathlib import Path

from scripts.astrodice.astrodice_apparent_source_reference import (
    D,
    Reader,
    cross,
    dot,
    norm,
    scale,
    sub,
    unit,
)


def geometry(reader, body, epoch):
    now = reader.states(D(epoch), body)
    target, earth, sun = now[body], now["Earth"], now["Sun"]
    rough = target[:3]
    for _ in range(2):
        delay = norm(sub(rough, earth[:3])) * 149597870700 / 299792458 / 86400
        rough = sub(target[:3], scale(target[3:], delay))
    retarded = reader.body_state(D(epoch) - delay, body)
    ray = sub(retarded[:3], earth[:3])
    u = unit(ray)
    earth_helio = sub(earth[:3], sun[:3])
    radius = D((959.63 / 3600) * (math.pi / 180))
    impact = norm(cross(u, unit(earth_helio))) * norm(earth_helio) / radius
    projection = dot(u, sub(sun[:3], earth[:3]))
    return impact.v, norm(ray).v > projection.v > 0


def select(run, fixture):
    plan_path = run / "boundary-selection-before.json"
    plan = json.loads(plan_path.read_text())
    base = json.loads((fixture / "geometric-reference.json").read_text())["rows"]
    crossings = []
    cohorts = {"A": [], "B": []}
    with localcontext() as context:
        context.prec = 70
        for declaration in plan["solar_crossings"]:
            window, target_literal = (
                declaration["window_index"],
                declaration["impact_knot"],
            )
            reader = Reader(fixture, window)
            original = base[window]
            epoch = N.from_float(original["native_numeric_argument"])
            target = N.from_float(float(target_literal))
            previous = None
            brackets = []
            for seconds in range(
                -plan["search_radius_seconds"],
                plan["search_radius_seconds"] + 1,
                plan["scan_step_seconds"],
            ):
                impact, background = geometry(
                    reader, "Mercury", epoch + N(seconds) / 86400
                )
                point = {
                    "offset_seconds": seconds,
                    "impact_fraction": str(impact),
                    "background": background,
                }
                if (
                    previous is not None
                    and (N(previous["impact_fraction"]) - target) * (impact - target)
                    < 0
                ):
                    brackets.append((previous, point))
                previous = point
            if len(brackets) != 2:
                raise ValueError(
                    "Predeclared two solar-knot crossings were not available"
                )
            for crossing_index, (left, right) in enumerate(brackets):
                lo, hi = N(left["offset_seconds"]), N(right["offset_seconds"])
                flo = N(left["impact_fraction"]) - target
                for _ in range(80):
                    mid = (lo + hi) / 2
                    impact, background = geometry(
                        reader, "Mercury", epoch + mid / 86400
                    )
                    if not background:
                        raise ValueError(
                            "Selected solar knot is not on the background ray"
                        )
                    fm = impact - target
                    if flo * fm <= 0:
                        hi = mid
                    else:
                        lo, flo = mid, fm
                    if hi - lo <= N(plan["bisection_width_seconds"]):
                        break
                if hi - lo > N(plan["bisection_width_seconds"]):
                    raise ValueError(
                        "Frozen source-geometry bisection did not converge"
                    )
                rounded = int(
                    ((lo + hi) / 2).to_integral_value(rounding=ROUND_HALF_EVEN)
                )
                crossings.append(
                    {
                        "window_index": window,
                        "impact_knot": target_literal,
                        "crossing_index": crossing_index,
                        "source_offset_lower_seconds": str(lo),
                        "source_offset_upper_seconds": str(hi),
                        "rounded_offset_seconds": rounded,
                    }
                )
                for cohort, seconds in plan["cohort_side_offsets_seconds"].items():
                    for side in (-1, 1):
                        label = (
                            datetime.fromisoformat(original["date_tdb"])
                            + timedelta(seconds=rounded + side * seconds)
                        ).isoformat()
                        cohorts[cohort].append(
                            {
                                "id": f"boundary-{cohort}-{window}-{crossing_index}-{side:+d}",
                                "body": "Mercury",
                                "window_index": window,
                                "date_tdb": label,
                                "role": "geometry_selected_solar_knot_holdout",
                                "source_knot": target_literal,
                                "side_seconds_from_rounded_crossing": side * seconds,
                            }
                        )
        venus = base[2]
        for cohort, seconds in plan["venus_offsets_seconds"].items():
            for side in (-1, 1):
                label = (
                    datetime.fromisoformat(venus["date_tdb"])
                    + timedelta(seconds=side * seconds)
                ).isoformat()
                cohorts[cohort].append(
                    {
                        "id": f"venus-clock-{cohort}-{side:+d}",
                        "body": "Venus",
                        "window_index": 2,
                        "date_tdb": label,
                        "role": "predeclared_remote_era_confirmation",
                        "offset_seconds_from_known_center": side * seconds,
                    }
                )
    if any(
        name == "swisseph" or name == "fatebridge" or name.startswith("fatebridge.")
        for name in sys.modules
    ):
        raise ValueError("Geometry-only selector imported candidate")
    return {
        "method_id": "unbent_geometry_selected_solar_mass_knots_v1",
        "selection_plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "crossings": crossings,
        "cohorts": cohorts,
        "candidate_or_apparent_rate_used_for_selection": False,
        "original_grade_replaced": False,
        "scope": "Two-sided profile-knot coverage selected from fixed original DE441 geometry. Cohort B stays unopened until any A-based repair has been frozen.",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = select(args.run, args.fixture)
    with args.output.open("x") as file:
        file.write(json.dumps(result, indent=2) + "\n")
    print({key: len(value) for key, value in result["cohorts"].items()})
