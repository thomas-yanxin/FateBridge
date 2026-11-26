"""Independent original-DE441/CALCEPH/Skyfield solar crossings.

Run in a reference environment with Skyfield1.53, jplephem2.24, pyerfa2.0.1.5
and pyswisseph2.10.3.2. Supply an independently built CALCEPH5.0.1 library and
original JPL records. No FateBridge calculation or candidate root is imported.
"""

from __future__ import annotations

import argparse
import ctypes
import gzip
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

import erfa
import numpy as np
import swisseph as swe
from skyfield.api import load
from skyfield.vectorlib import VectorFunction


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--first-year", type=int, required=True)
    parser.add_argument("--last-year", type=int, required=True)
    parser.add_argument("--extra-event", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert args.first_year <= args.last_year
    assert not any(
        n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
    )
    versions = {
        name: importlib.metadata.version(name)
        for name in ("skyfield", "jplephem", "pyerfa", "pyswisseph", "numpy")
    }
    assert {k: versions[k] for k in versions if k != "numpy"} == {
        "skyfield": "1.53",
        "jplephem": "2.24",
        "pyerfa": "2.0.1.5",
        "pyswisseph": "2.10.3.2",
    }
    library = ctypes.CDLL(str(args.library.resolve()))
    library.calceph_open.argtypes = [ctypes.c_char_p]
    library.calceph_open.restype = ctypes.c_void_p
    library.calceph_close.argtypes = [ctypes.c_void_p]
    library.calceph_close.restype = None
    library.calceph_compute.argtypes = [
        ctypes.c_void_p,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
    ]
    library.calceph_compute.restype = ctypes.c_int
    library.calceph_getversion_str.argtypes = [ctypes.POINTER(ctypes.c_char)]
    library.calceph_getversion_str.restype = None
    library.calceph_getfileversion.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_char),
    ]
    library.calceph_getfileversion.restype = ctypes.c_int
    library.calceph_gettimescale.argtypes = [ctypes.c_void_p]
    library.calceph_gettimescale.restype = ctypes.c_int
    descriptor = library.calceph_open(str(args.kernel.resolve()).encode())
    assert descriptor
    try:
        version, file_version = ctypes.create_string_buffer(
            1024
        ), ctypes.create_string_buffer(1024)
        library.calceph_getversion_str(version)
        assert library.calceph_getfileversion(descriptor, file_version)
        assert version.value == b"5.0.1" and b"441" in file_version.value
        assert library.calceph_gettimescale(descriptor) == 1
        ephemeris = {}

        class OriginalBody(VectorFunction):
            center = 0

            def __init__(self, target: int, calceph_target: int):
                self.target = target
                self.calceph_target = calceph_target
                self.ephemeris = ephemeris

            def _at(self, t):
                whole, fraction = np.broadcast_arrays(t.whole, t.tdb_fraction)
                rows = []
                for first, second in zip(whole.ravel(), fraction.ravel()):
                    output = (ctypes.c_double * 6)()
                    assert library.calceph_compute(
                        descriptor,
                        float(first),
                        float(second),
                        self.calceph_target,
                        12,
                        output,
                    )
                    rows.append(list(output))
                values = np.moveaxis(np.array(rows).reshape(whole.shape + (6,)), -1, 0)
                return values[:3], values[3:], None, None

        for name, target, source in (
            ("earth", 399, 3),
            ("sun", 10, 11),
            ("jupiter", 5, 5),
            ("saturn", 6, 6),
        ):
            ephemeris[name] = OriginalBody(target, source)
        timescale = load.timescale(builtin=True)
        bias = erfa.bp06(2451545.0, 0.0)[0]

        def longitude(epochs):
            t = timescale.tt_jd(epochs)
            ray = ephemeris["earth"].at(t).observe(ephemeris["sun"]).apparent().xyz.au
            precession = erfa.ltp(erfa.epj(2451545.0, epochs - 2451545.0))
            rotations = []
            for tt, matrix in zip(epochs, precession):
                values, _ = swe.calc(float(tt), swe.ECL_NUT)
                epsilon, psi = np.deg2rad(values[1:3])
                ce, se, cp, sp = (
                    np.cos(epsilon),
                    np.sin(epsilon),
                    np.cos(psi),
                    np.sin(psi),
                )
                rx = np.array([[1, 0, 0], [0, ce, se], [0, -se, ce]])
                rz = np.array([[cp, -sp, 0], [sp, cp, 0], [0, 0, 1]])
                rotations.append(rz @ rx @ matrix @ bias)
            vector = np.einsum("nij,jn->in", np.array(rotations), ray)
            return np.rad2deg(np.arctan2(vector[1], vector[0])) % 360

        events = [
            (year, index)
            for year in range(args.first_year, args.last_year + 1)
            for index in range(24)
        ]
        events.extend(tuple(map(int, text.split(":"))) for text in args.extra_event)
        assert len(events) == len(set(events)) and all(
            0 <= index < 24 for _, index in events
        )
        anchors = np.array(
            [sum(erfa.cal2jd(year, index // 2 + 1, 15)) for year, index in events]
        )
        targets = np.array([(285 + 15 * index) % 360 for _, index in events])

        def residual(epochs):
            return (longitude(epochs) - targets + 180) % 360 - 180

        low, high = anchors - 30, anchors + 30
        assert np.all(residual(low) < 0) and np.all(residual(high) >= 0)
        for _ in range(48):
            mid = (low + high) / 2
            if np.all((mid == low) | (mid == high)):
                break
            negative = residual(mid) < 0
            low, high = np.where(negative, mid, low), np.where(negative, high, mid)
        left, right = residual(low), residual(high)
        assert np.all(left < 0) and np.all(right >= 0)
        assert np.all(np.nextafter(low, np.inf) == high)
        result = {
            "reference": "original DE441 / CALCEPH5.0.1 / Skyfield1.53 apparent / ERFA-Swiss native frame",
            "production_imported": False,
            "versions": versions,
            "library_version": version.value.decode(),
            "kernel_version": file_version.value.decode(),
            "input_kernel_sha256": hashlib.sha256(args.kernel.read_bytes()).hexdigest(),
            "input_library_sha256": hashlib.sha256(
                args.library.read_bytes()
            ).hexdigest(),
            "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "TT_tolerance_seconds": 1.0,
            "angular_tolerance_arcseconds": 0.001,
            "source_urls": [
                "https://ssd.jpl.nasa.gov/planets/eph_export.html",
                "https://calceph.imcce.fr/docs/latest/html/c/calceph.multiple.cusage.html",
                "https://rhodesmill.org/skyfield/positions.html",
            ],
            "scope": "Independent monthly brackets; all events solved to adjacent TT floats. The input kernel can be an original-word JPL excerpt. Its hash does not identify the whole upstream file. Skyfield includes Sun/Jupiter/Saturn deflection and its own geocentric TT/TDB approximation. Not observational or civil-UTC certification.",
            "rows": [
                dict(
                    year=year,
                    index=index,
                    longitude=int(targets[i]),
                    jd_tt=float(high[i]),
                    bracket_tt=[float(low[i]), float(high[i])],
                )
                for i, (year, index) in enumerate(events)
            ],
        }
        assert not any(
            n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules
        )
        raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(
            gzip.compress(raw, mtime=0) if args.output.suffix == ".gz" else raw
        )
        print(
            json.dumps(
                {
                    "rows": len(events),
                    "production_imported": False,
                    "output_sha256": hashlib.sha256(
                        args.output.read_bytes()
                    ).hexdigest(),
                }
            )
        )
    finally:
        library.calceph_close(descriptor)


if __name__ == "__main__":
    main()
