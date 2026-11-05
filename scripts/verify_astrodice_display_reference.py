"""Independent source and expanded moving-frame replay of every frozen row."""

import argparse
import hashlib
import json
import sys
from fractions import Fraction as Q
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_astrodice_display_frame import (
    constant,
    data_from_primary,
    frame_state,
    project,
)
from scripts.verify_astrodice_lunar_split import (
    LunarSource,
    binary64_nearest,
)
from scripts.verify_astrodice_lunar_split import model as lunar
from scripts.verify_astrodice_lunar_split import tdb_label
from scripts.verify_astrodice_observer_clock import cover, independent_pi, rounded
from scripts.verify_astrodice_taylor_remainder import (
    R,
    dot,
    length,
    normalize,
    plus,
    subtract,
    times,
    vector_product,
)

PLAN_SHA = "6f3cc7e38645bf69c40ca072599f5718cd9a86b6da3bb4be1b505cb7b40414b5"
INPUT_SHA = "8e463d5ac5b94e2d7cf8e3eff1174e55d14bd8ae999869a3f8ad7092852f8c1d"
K = Q(149597870700, 299792458 * 86400)


class InnerSource(LunarSource):
    def state_derivatives(self, t, body):
        if body in ("Earth", "Moon"):
            return super().state_derivatives(t, body)
        return self.group_derivatives(t, {"Mercury": 0, "Venus": 1, "Sun": 10}[body])


def inner(case, body, epoch, data, profile):
    source = InnerSource(Path(case["source"]), case["window"])
    t = R([rounded(epoch), rounded(1)])
    current = source.state_derivatives(t, body)
    observer = source.state_derivatives(t, "Earth")
    sun = source.state_derivatives(t, "Sun")
    target = current[:3]
    for _ in range(2):
        delay = length(subtract(target, observer[:3])) * K
        target = subtract(current[:3], times(current[3:], delay))
    emitted = source.state_derivatives(t - delay, body)
    ray = subtract(emitted[:3], observer[:3])
    distance = length(ray)
    u = normalize(ray)
    earth_sun = subtract(observer[:3], sun[:3])
    radius = length(earth_sun)
    e = normalize(earth_sun)
    q = normalize(subtract(emitted[:3], subtract(sun[:3], times(sun[3:], delay))))
    impact = (
        length(vector_product(u, e))
        * radius
        / Q(float.fromhex(data["solar_radius_radians_hex"]))
    )
    low, high = impact.v[0]
    if low > 1:
        mass = constant(1)
    else:
        mass = None
        for (r0, m0), (r1, m1) in zip(profile, profile[1:]):
            r0, m0, r1, m1 = map(lambda x: Q(float(x)), (r0, m0, r1, m1))
            if r1 < low <= high < r0:
                mass = m0 + (impact - r0) * ((m1 - m0) / (r1 - r0))
                break
        if mass is None:
            raise ValueError("Independent solar cell/axis unresolved")
    strength = (
        mass
        * (2 * Q(float.fromhex(data["GM_sun_hex"])) / Q(299792458**2 * 149597870700))
        / radius
    )
    denominator = dot(plus(q, e), plus(q, e)) / 2
    deflected = times(
        plus(u, times(vector_product(u, vector_product(e, q)), strength / denominator)),
        distance,
    )
    beta = times(observer[3:], K)
    r = length(deflected)
    gamma = (1 - dot(beta, beta)).sqrt()
    projection = dot(deflected, beta) / r
    return normalize(
        times(
            plus(
                times(deflected, gamma), times(beta, r * (1 + projection / (1 + gamma)))
            ),
            1 / (1 + projection),
        )
    )


def check_vector(computed, saved):
    if len(computed) != len(saved):
        raise ValueError("Reference vector shape changed")
    for exact, value in zip(computed, saved):
        if set(value) != {"value", "derivative"}:
            raise ValueError("Derivative field omitted")
        cover(exact.v[0], value["value"])
        cover(exact.v[1], value["derivative"])


def verify(run, path):
    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    from scripts.astrodice_reference_data import verify_material

    verify_material(run / "plan-before-evaluation.json")
    plan = json.loads((run / "plan-before-evaluation.json").read_text())
    saved = json.loads(path.read_text())
    split = saved["split"]
    if (
        saved["protocol_sha256"] != PLAN_SHA
        or saved["physical_TT_equivalence_certified"] is not False
        or saved["original_failure_records_regraded"] is not False
        or saved["old_gates"] != {"production": 2, "overall": 1}
    ):
        raise ValueError("Reference identity or claim promoted")
    expected = [(i, b) for i, c in enumerate(plan[split]) for b in c["bodies"]]
    if [(r["case_index"], r["body"]) for r in saved["rows"]] != expected or len(
        saved["frames"]
    ) != len(plan[split]):
        raise ValueError("Planned reference population omitted/rebound")
    data = data_from_primary(run)
    if saved["coefficient_sha256"] != sha(
        run / "frame-coefficients-before-evaluation.json"
    ):
        raise ValueError("Coefficient digest detached")
    profile = json.loads(
        Path(
            "tests/data/astrodice/reference_sets/fixture-apparent-source-v1/source-solar-profile.json"
        ).read_text()
    )["radius_mass_pairs"]
    results = []
    frames = {}
    for index, case in enumerate(plan[split]):
        epoch = binary64_nearest(tdb_label(case["label"]))
        frame = frame_state(epoch, data)
        frames[index] = frame
        stored = saved["frames"][index]
        if (
            stored["label"] != case["label"]
            or stored["case_index"] != index
            or stored["exact_binary64_numeric_jd"] != str(epoch)
        ):
            raise ValueError("Frame epoch rebound")
        for kind in ("mean", "true"):
            for row, record in zip(frame[kind], stored[kind]):
                check_vector(row, record)
        check_vector([frame["psi"], frame["deps"]], [stored["psi"], stored["deps"]])
    for row in saved["rows"]:
        case = plan[split][row["case_index"]]
        epoch = binary64_nearest(tdb_label(case["label"]))
        if (
            any(row[k] != v for k, v in case.items())
            or row["exact_label_jd_tdb"] != str(tdb_label(case["label"]))
            or row["exact_binary64_numeric_jd"] != str(epoch)
            or Q(row["native_numeric_jd"]) != epoch
        ):
            raise ValueError("Source target/epoch rebound")
        try:
            if row["body"] == "Moon":
                raw = lunar(
                    LunarSource(Path(case["source"]), case["window"]),
                    epoch,
                    "continuous_split",
                    derivative=True,
                )
                direction = [
                    R([p, v])
                    for p, v in zip(
                        raw["direction"], raw["direction_derivative_per_source_day"]
                    )
                ]
            else:
                direction = inner(case, row["body"], epoch, data, profile)
        except Exception as error:
            if row["status"] != "reference_unavailable":
                raise
            results.append(
                {
                    "case_index": row["case_index"],
                    "body": row["body"],
                    "status": "independently_unavailable",
                    "error_type": type(error).__name__,
                }
            )
            continue
        if row["status"] != "ready":
            raise ValueError("A computed independent source row was omitted")
        displayed = project(frames[row["case_index"]], direction, data)
        check_vector(direction, row["source_direction"])
        check_vector(displayed, row["displayed_direction"])
        x, y = displayed[:2]
        rate = (x.v[0][0], x.v[0][1])
        from scripts.verify_astrodice_observer_clock import (
            add,
            divide,
            mul,
            square,
            sub,
        )

        rate = divide(
            sub(mul(x.v[0], y.v[1]), mul(y.v[0], x.v[1])),
            add(square(x.v[0]), square(y.v[0])),
        )
        rate = divide(mul(rate, rounded(648000)), rounded(*independent_pi()))
        cover(rate, row["longitude_rate_arcsec_per_source_day"])
        results.append(
            {
                "case_index": row["case_index"],
                "body": row["body"],
                "status": "strict_containment_passed",
            }
        )
    return {
        "protocol_sha256": PLAN_SHA,
        "reference_sha256": sha(path),
        "split": split,
        "rows": results,
        "independent_expanded_frame_chain_verified": True,
        "physical_TT_equivalence_certified": False,
        "original_failure_records_regraded": False,
        "old_gates": plan["old_gates"],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = verify(a.run, a.reference)
    with a.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
