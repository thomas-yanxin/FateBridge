"""Independent source-model reduction; deliberately imports no FateBridge code.

Run in an isolated uv --no-project environment with mpmath==1.3.0 and
pyswisseph==2.10.3.2. Native geometric states and coordinate-frame samples are
shared inputs, not an independent ephemeris. The nonlinear reduction and its
high-precision derivative do not use the candidate's sampling correction.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import re
import sys
from pathlib import Path

import mpmath as mp
import swisseph as swe

PROTOCOL_SHA256 = "e090a6be08a5bad2ff2c9d767f1c72b39de6f586e0dca3059a82768ceb94e393"
BODY_IDS = {
    "Sun": swe.SUN,
    "Earth": swe.EARTH,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Pluto": swe.PLUTO,
}


def dot(a, b):
    return mp.fsum(x * y for x, y in zip(a, b))


def cross(a, b):
    return mp.matrix(
        [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ]
    )


def unit(a):
    return a / mp.sqrt(dot(a, a))


def interpolate(samples, nodes, step, offset):
    x = offset / step
    result = samples[0] * 0
    for i, node in enumerate(nodes):
        weight = mp.mpf(1)
        for j, other in enumerate(nodes):
            if i != j:
                weight *= (x - other) / (node - other)
        result += weight * samples[i]
    return result


def collect(case, frame, step, protocol):
    epoch = case["julian_day_tt"]
    fixed = (
        swe.FLG_SWIEPH
        | swe.FLG_SPEED
        | swe.FLG_XYZ
        | swe.FLG_ICRS
        | swe.FLG_J2000
        | swe.FLG_EQUATORIAL
        | swe.FLG_TRUEPOS
    )
    display = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_XYZ | swe.FLG_TRUEPOS
    if frame == "Sidereal":
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        display |= swe.FLG_SIDEREAL
    data = []
    for node in protocol["physical_nodes"]:
        at = epoch + node * step
        assert at - epoch == node * step

        def state(body, flags):
            values, returned = swe.calc(at, BODY_IDS[body], flags)
            assert returned & swe.FLG_SWIEPH and returned & swe.FLG_SPEED
            mask = 0
            for name in (
                "FLG_XYZ",
                "FLG_ICRS",
                "FLG_J2000",
                "FLG_EQUATORIAL",
                "FLG_TRUEPOS",
                "FLG_BARYCTR",
                "FLG_HELCTR",
                "FLG_TOPOCTR",
                "FLG_SIDEREAL",
                "FLG_NONUT",
                "FLG_NOABERR",
                "FLG_NOGDEFL",
                "FLG_RADIANS",
                "FLG_JPLHOR",
                "FLG_JPLHOR_APPROX",
            ):
                mask |= getattr(swe, name)
            expected = flags | swe.FLG_NOABERR | swe.FLG_NOGDEFL
            if flags & (swe.FLG_J2000 | swe.FLG_SIDEREAL):
                expected |= swe.FLG_NONUT
            assert returned & mask == expected & mask
            assert len(values) == 6 and all(math.isfinite(v) for v in values)
            return list(values)

        raw = {
            body: state(body, fixed | swe.FLG_BARYCTR)
            for body in [case["body"], "Earth", "Sun"]
        }
        pairs = [
            {"body": body, "fixed": state(body, fixed), "display": state(body, display)}
            for body in protocol["frame_basis_bodies"]
        ]
        data.append(
            {"node": node, "epoch_jd_tt": at, "physical": raw, "frame_pairs": pairs}
        )
    return data


def reduce(case, step, data, mass, protocol):
    nodes = protocol["physical_nodes"]
    physical = {
        body: [mp.matrix(r["physical"][body]) for r in data]
        for body in [case["body"], "Earth", "Sun"]
    }
    rotations = []
    orthogonality = []
    for row in data:
        fixed = mp.matrix(3, 3)
        display = mp.matrix(3, 3)
        for column, pair in enumerate(row["frame_pairs"]):
            fixed[:, column] = unit(mp.matrix(pair["fixed"][:3]))
            display[:, column] = unit(mp.matrix(pair["display"][:3]))
        rotation = display * fixed**-1
        orthogonality.append(float(mp.norm(rotation.T * rotation - mp.eye(3))))
        rotations.append(rotation)
    assert max(orthogonality) < 1e-10
    au, light = mp.mpf("149597870700"), mp.mpf("299792458")
    gravity, solar_radius = mp.mpf("1.32712440017987e20"), mp.radians(
        mp.mpf("959.63") / 3600
    )

    def effective_mass(r):
        if r <= 0:
            return mp.mpf(0)
        if r >= 1:
            return mp.mpf(1)
        for (r0, m0), (r1, m1) in zip(mass, mass[1:]):
            if r >= r1:
                return m0 + (r - r0) * (m1 - m0) / (r1 - r0)
        raise AssertionError("Effective-mass domain changed")

    def longitude(offset):
        planet, earth, sun = [
            interpolate(physical[b], nodes, mp.mpf(step), offset)
            for b in [case["body"], "Earth", "Sun"]
        ]
        rough = planet[:3]
        for _ in range(2):
            difference = rough - earth[:3]
            delay = mp.sqrt(dot(difference, difference)) * au / light / 86400
            rough = planet[:3] - delay * planet[3:]
        # Evaluate a small epoch offset, never subtract delay from a large JD.
        retarded = interpolate(
            physical[case["body"]], nodes, mp.mpf(step), offset - delay
        )
        position = retarded[:3] - earth[:3]
        radius = mp.sqrt(dot(position, position))
        u = position / radius
        earth_helio = earth[:3] - sun[:3]
        re = mp.sqrt(dot(earth_helio, earth_helio))
        e = earth_helio / re
        q = unit(position + earth[:3] - (sun[:3] - delay * sun[3:]))
        impact = mp.sqrt(dot(cross(u, e), cross(u, e))) / (solar_radius / re)
        strength = 2 * gravity * effective_mass(impact) / light**2 / au / re
        denominator = dot(q + e, q + e) / 2
        deflected = radius * (u + strength / denominator * cross(u, cross(e, q)))
        beta = earth[3:] * au / light / 86400
        r = mp.sqrt(dot(deflected, deflected))
        b = mp.sqrt(1 - dot(beta, beta))
        f = dot(deflected, beta) / r
        apparent = (b * deflected + (1 + f / (1 + b)) * r * beta) / (1 + f)
        displayed = interpolate(rotations, nodes, mp.mpf(step), offset) * apparent
        return mp.degrees(mp.atan2(displayed[1], displayed[0]))

    derivative = mp.diff(longitude, mp.mpf(0), addprec=40)
    return {
        "rate_degrees_per_day": mp.nstr(derivative, 65),
        "rotation_orthogonality_max": max(orthogonality),
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ("protocol", "native-source", "ephemeris", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "References are append-only"
    assert hashlib.sha256(args.protocol.read_bytes()).hexdigest() == PROTOCOL_SHA256
    protocol = json.loads(args.protocol.read_text())
    mp.mp.dps = protocol["precision_decimal_digits"]
    assert (
        swe.version == protocol["native_version"]
        and importlib.metadata.version("pyswisseph") == protocol["binding_version"]
    )
    assert mp.__version__ == "1.3.0"
    source = args.native_source.read_bytes()
    assert hashlib.sha256(source).hexdigest() == protocol["native_source_sha256"]
    text = source.decode()
    start = text.index("eff_arr[]")
    table = text[start : text.index("static double meff(double r)", start)]
    mass = [
        (mp.mpf(a), mp.mpf(b))
        for a, b in re.findall(r"\{(\d+\.\d+),\s*(\d+\.\d+)\}", table)
    ]
    assert len(mass) == 101
    swe.set_ephe_path(str(args.ephemeris.resolve()))
    rows = []
    for case in protocol["cases"]:
        for frame in protocol["frames"]:
            estimates = []
            for step in protocol["physical_interpolation_steps_days"]:
                raw = collect(case, frame, step, protocol)
                estimates.append(
                    {
                        "step_days": step,
                        "raw_samples": raw,
                        **reduce(case, step, raw, mass, protocol),
                    }
                )
            disagreement = (
                abs(
                    mp.mpf(estimates[0]["rate_degrees_per_day"])
                    - mp.mpf(estimates[1]["rate_degrees_per_day"])
                )
                * 3600
            )
            rows.append(
                {
                    **case,
                    "frame": frame,
                    "estimates": estimates,
                    "reference_disagreement_arcsec_per_day": float(disagreement),
                    "reference_converged": disagreement
                    <= protocol["reference_agreement_line_arcsec_per_day"],
                }
            )
    assert not any(
        n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
    )
    files = []
    for slot in (0, 1):
        filename, start, end, de = swe.get_current_file_data(slot)
        path = Path(filename)
        assert path.is_file()
        files.append(
            {
                "slot": slot,
                "filename": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "de_number": de,
            }
        )
    report = {
        "protocol_sha256": PROTOCOL_SHA256,
        "native_source_sha256": protocol["native_source_sha256"],
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "native_binary_sha256": hashlib.sha256(
            Path(swe.__file__).read_bytes()
        ).hexdigest(),
        "precision_decimal_digits": protocol["precision_decimal_digits"],
        "physical_files": files,
        "candidate_imports": False,
        "independent_ephemeris": False,
        "independent_model_reduction": True,
        "scope": protocol["purpose"],
        "rows": rows,
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "cases": len(rows),
                "reference_converged": sum(r["reference_converged"] for r in rows),
                "maximum_reference_disagreement_arcsec_per_day": max(
                    r["reference_disagreement_arcsec_per_day"] for r in rows
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
