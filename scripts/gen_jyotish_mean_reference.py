"""Isolated DE421 + ERFA frame and PyMeeus mean references; no SWE/FateBridge."""

import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path


def main():
    import erfa
    import numpy as np
    from jplephem.spk import SPK
    from pymeeus.Earth import Earth
    from pymeeus.Epoch import Epoch
    from pymeeus.Jupiter import Jupiter
    from pymeeus.Mars import Mars
    from pymeeus.Mercury import Mercury
    from pymeeus.Saturn import Saturn
    from pymeeus.Venus import Venus

    versions = {
        k: importlib.metadata.version(k)
        for k in ("jplephem", "skyfield-data", "pyerfa", "PyMeeus")
    }
    assert versions == {
        "jplephem": "2.23",
        "skyfield-data": "6.0.0",
        "pyerfa": "2.0.1.5",
        "PyMeeus": "0.5.12",
    }
    spec = importlib.util.find_spec("skyfield_data")
    kernel_path = Path(spec.origin).parent / "data/de421.bsp"
    kernel_sha = hashlib.sha256(kernel_path.read_bytes()).hexdigest()
    assert (
        kernel_sha == "a20a7139da04cbc462454634918e9a9ca69127044e2cc9d4f9c16e238d2deedc"
    )
    kernel = SPK.open(str(kernel_path))
    rb = erfa.bp00(2451545.0, 0.0)[0]
    eps = erfa.obl80(2451545.0, 0.0)
    rotation = (
        np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, math.cos(eps), math.sin(eps)],
                [0.0, -math.sin(eps), math.cos(eps)],
            ]
        )
        @ rb
    )
    elements = {
        "Mercury": Mercury,
        "Venus": Venus,
        "Earth": Earth,
        "Mars": Mars,
        "Jupiter": Jupiter,
        "Saturn": Saturn,
    }
    bodies = {
        "Mercury": (1, 199),
        "Venus": (2, 299),
        "Mars": (4, 499),
        "Jupiter": (5, None),
        "Saturn": (6, None),
    }
    epochs = [
        2415020.5,
        2421882.8733333335,
        2446444.71875,
        2447987.564583333,
        2451604.260416667,
        2461335.5,
        2470172.5,
        2415554.75,
        2424384.25,
        2433637.5,
        2442572.125,
        2455294.5,
        2463912.75,
        2470172.999,
    ]
    rows = []
    for jd in epochs:
        earth = kernel[0, 3].compute(jd) + kernel[3, 399].compute(jd)
        true_points = {}
        for name, (bary, centre) in bodies.items():
            absolute = kernel[0, bary].compute(jd)
            if centre is not None:
                absolute = absolute + kernel[bary, centre].compute(jd)
            geocentric = absolute - earth
            xyz = rotation @ geocentric
            true_points[name] = {
                "longitude": math.degrees(math.atan2(xyz[1], xyz[0])) % 360,
                "latitude": math.degrees(
                    math.atan2(xyz[2], math.hypot(xyz[0], xyz[1]))
                ),
                "icrs_xyz_km": geocentric.tolist(),
            }
        rows.append(
            {
                "jd_tt_substituted_for_tdb": jd,
                "mean_j2000_degrees": {
                    name: float(cls.orbital_elements_j2000(Epoch(jd))[0]) % 360
                    for name, cls in elements.items()
                },
                "true_geocentric_j2000": true_points,
            }
        )
    result = {
        "provenance": {
            "versions": versions,
            "DE421_sha256": kernel_sha,
            "DE421_file_bytes": kernel_path.stat().st_size,
            "source": "https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de421.bsp",
            "carrier": "skyfield-data6.0.0 wheel, SHA25612c946dbd4453fb4958faf845484222ec9d8d2cac19d2cb7bffb41301aa5b526",
            "kernel_support": str(kernel),
            "generator_uses_no_production_or_Swiss_imports": True,
            "EOP_data_used": False,
        },
        "frame_rotation_icrs_to_mean_ecliptic_j2000": rotation.tolist(),
        "scope": "Geometric geocentre positions, no light-time/aberration/deflection. Jupiter/Saturn system barycentres retained, inner physical centres used. DE421 TDB epochs numerically substituted by TT (<2ms convention), no UTC or EOP calls. PyMeeus rounded mean polynomials independently check primary Simon transcription, not an independent physical mean model. No real-world events.",
        "tolerances": {
            "mean_arcsec": 0.01,
            "geometry_arcsec": 2.0,
            "matrix_absolute": 2e-15,
        },
        "rows": rows,
    }
    target = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/jyotish-mean-de421-reference.json"
    )
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
