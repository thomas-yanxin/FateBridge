"""Vector-plane oracle over frozen inputs, without native/application imports."""

import gzip
import json
import math
from pathlib import Path

from mpmath import mp

ROOT = Path(__file__).parent
mp.dps = 100


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def setup(case):
    p, t, e = [mp.mpf(case[k]) * mp.pi / 180 for k in ("latitude", "armc", "obliquity")]
    east = [-mp.sin(t), mp.cos(t), mp.mpf(0)]
    up = [mp.cos(p) * mp.cos(t), mp.cos(p) * mp.sin(t), mp.sin(p)]
    north = [-mp.sin(p) * mp.cos(t), -mp.sin(p) * mp.sin(t), mp.cos(p)]
    pole = [mp.mpf(0), mp.mpf(0), mp.mpf(1)]
    ecliptic = [mp.mpf(0), -mp.sin(e), mp.cos(e)]

    def projected(v):
        return [x - dot(v, north) * y for x, y in zip(v, north)]

    def body(longitude):
        a = mp.mpf(longitude) * mp.pi / 180
        return [mp.cos(a), mp.sin(a) * mp.cos(e), mp.sin(a) * mp.sin(e)]

    def phase(longitude, code):
        v = body(longitude)
        q = projected(v)
        if code == "C":
            value = (
                mp.atan2(dot(north, cross(east, q)), dot(east, q)) * 180 / mp.pi % 360
            )
        else:
            equator = cross(cross(north, v), pole)
            if dot(q, projected(equator)) < 0:
                equator = [-x for x in equator]
            value = (
                mp.atan2(equator[1], equator[0]) * 180 / mp.pi
                - mp.mpf(case["armc"])
                - 90
            ) % 360
        return value

    def cusps(code):
        result = []
        for house in range(1, 13):
            if code == "C":
                a = mp.mpf(1 - house) * mp.pi / 6
                target = [mp.cos(a) * x + mp.sin(a) * y for x, y in zip(east, up)]
            else:
                a = t + mp.mpf(house - 10) * mp.pi / 6
                target = projected([mp.cos(a), mp.sin(a), mp.mpf(0)])
            v = cross(cross(north, target), ecliptic)
            if dot(v, target) < 0:
                v = [-x for x in v]
            result.append(
                float(
                    mp.atan2(v[1] * mp.cos(e) + v[2] * mp.sin(e), v[0])
                    * 180
                    / mp.pi
                    % 360
                )
            )
        return result

    return phase, cusps


if __name__ == "__main__":
    inputs = json.loads((ROOT / "inputs.json").read_text())
    count = 0
    with gzip.open(ROOT / "reference.jsonl.gz", "wt") as output:
        for case in inputs["cases"]:
            phase, cusps = setup(case)
            for code in ("R", "C"):
                probes = [("fixed-" + str(i), float(i * 30)) for i in range(12)]
                for i, value in enumerate(cusps(code)):
                    probes.extend(
                        (f"cusp-{i + 1}-{label}", x)
                        for label, x in (
                            ("below", math.nextafter(value, -math.inf)),
                            ("on", value),
                            ("above", math.nextafter(value, math.inf)),
                        )
                    )
                for label, longitude in probes:
                    value = phase(longitude, code)
                    shifted = (value + mp.mpf(1) / 3600000) % 360
                    output.write(
                        json.dumps(
                            dict(
                                id=f'{case["id"]}-{code}-{label}',
                                model_id=case["id"],
                                code=code,
                                probe=label,
                                longitude=longitude,
                                phase_degrees=mp.nstr(value, 100),
                                shifted_phase_degrees=mp.nstr(shifted, 100),
                                house_position=float(shifted / 30 + 1),
                                house=int(mp.floor(shifted / 30)) + 1,
                                mathematical_house=int(mp.floor(value / 30)) + 1,
                            )
                        )
                        + "\n"
                    )
                    count += 1
    print({"rows": count, "precision_digits": 100})
