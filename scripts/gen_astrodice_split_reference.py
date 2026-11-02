"""Independent split-TDB lunar reference using CALCEPH and ERFA.

Maintenance only, outside the project. No FateBridge or Swiss import. This
reference does not convert TT to TDB and cannot replace earlier TT studies.
All steps, physics choices, dependency hashes and dates precede sampling.
"""

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import math
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

C_AU_DAY = 299792458.0 * 86400.0 / 149597870700.0


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def shifted(jd0, fraction, offset):
    """Keep the small part separate even across Gregorian year0/year10000."""
    small = math.fsum((fraction, offset))
    carry = math.floor(small)
    return jd0 + carry, small - carry


def unit(vector):
    radius = math.hypot(*vector)
    if radius <= 0 or not math.isfinite(radius):
        raise ValueError("Invalid physical vector")
    return [x / radius for x in vector]


class Reader:
    def __init__(self, library, kernel):
        self.lib = lib = ctypes.CDLL(str(library))
        ptr = ctypes.c_void_p
        lib.calceph_open.argtypes = [ctypes.c_char_p]
        lib.calceph_open.restype = ptr
        lib.calceph_compute.argtypes = [
            ptr,
            ctypes.c_double,
            ctypes.c_double,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_double),
        ]
        lib.calceph_compute.restype = ctypes.c_int
        lib.calceph_gettimescale.argtypes = [ptr]
        lib.calceph_gettimescale.restype = ctypes.c_int
        lib.calceph_gettimespan.argtypes = [
            ptr,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.calceph_gettimespan.restype = ctypes.c_int
        lib.calceph_close.argtypes = [ptr]
        lib.calceph_getversion_str.argtypes = [ctypes.c_char_p]
        version = ctypes.create_string_buffer(256)
        lib.calceph_getversion_str(version)
        if version.value != b"5.0.1":
            raise ValueError("Unfrozen CALCEPH version")
        self.handle = lib.calceph_open(str(kernel).encode())
        if not self.handle or lib.calceph_gettimescale(self.handle) != 1:
            raise ValueError("Expected a TDB kernel")
        start, end, continuous = ctypes.c_double(), ctypes.c_double(), ctypes.c_int()
        if not lib.calceph_gettimespan(
            self.handle,
            ctypes.byref(start),
            ctypes.byref(end),
            ctypes.byref(continuous),
        ):
            raise ValueError("Missing kernel range")
        self.coverage = {
            "start_jd_tdb": start.value,
            "end_jd_tdb": end.value,
            "continuous": continuous.value,
        }

    def state(self, epoch, target, center=12):
        values = (ctypes.c_double * 6)()
        if not self.lib.calceph_compute(self.handle, *epoch, target, center, values):
            raise ValueError("CALCEPH state unavailable")
        result = list(values)
        if not all(math.isfinite(v) for v in result):
            raise ValueError("Nonfinite independent source state")
        return result

    def close(self):
        self.lib.calceph_close(self.handle)


def sample(reader, epoch, protocol):
    import erfa

    earth = reader.state(epoch, 3)
    geometric = reader.state(epoch, 10, 3)
    delay = math.hypot(*geometric[:3]) / C_AU_DAY
    iterations = []
    for _ in range(protocol["maximum_light_time_iterations"]):
        emission = shifted(*epoch, -delay)
        moon = reader.state(emission, 10)
        ray = [a - b for a, b in zip(moon[:3], earth[:3])]
        next_delay = math.hypot(*ray) / C_AU_DAY
        iterations.append(
            {
                "delay_days": delay,
                "emission_jd0_tdb": emission[0],
                "emission_fraction_tdb": emission[1],
                "moon_barycentric_pv": moon,
                "next_delay_days": next_delay,
            }
        )
        if abs(next_delay - delay) <= protocol["light_time_convergence_days"]:
            break
        delay = next_delay
    else:
        raise ValueError(
            {
                "reason": "Independent reception solution did not converge",
                "epoch_tdb": epoch,
                "iterations": iterations,
            }
        )
    natural = unit(ray)
    sun = reader.state(epoch, 11)
    solar_observer = [a - b for a, b in zip(earth[:3], sun[:3])]
    solar_target = [a - b for a, b in zip(moon[:3], sun[:3])]
    distance_sun = math.hypot(*solar_observer)
    finite_deflected = erfa.ld(
        1.0,
        natural,
        unit(solar_target),
        unit(solar_observer),
        distance_sun,
        protocol["solar_deflection_limiter"],
    )
    beta = [v / C_AU_DAY for v in earth[3:]]
    bm1 = math.sqrt(1 - math.fsum(v * v for v in beta))
    apparent = list(
        map(float, erfa.ab(unit(finite_deflected), beta, distance_sun, bm1))
    )
    no_deflection = list(map(float, erfa.ab(natural, beta, distance_sun, bm1)))
    return {
        "jd0_tdb": epoch[0],
        "fraction_tdb": epoch[1],
        "earth_barycentric_pv": earth,
        "moon_geometric_pv": geometric,
        "sun_barycentric_pv": sun,
        "reception_iterations": iterations,
        "selected_direction": apparent,
        "without_finite_solar_deflection": no_deflection,
    }


def collect(protocol_path, kernel, library, output):
    protocol = json.loads(protocol_path.read_text())
    if protocol["time_scale"] != "TDB" or protocol["tt_tdb_conversion_applied"]:
        raise ValueError("This study does not supply a TT reference")
    for name, expected in protocol["dependency_versions"].items():
        if importlib.metadata.version(name) != expected:
            raise ValueError("Independent numerical dependency changed")
    if (
        digest(kernel) != protocol["kernel_sha256"]
        or digest(library) != protocol["reader_library_sha256"]
    ):
        raise ValueError("Frozen source identity changed")
    reader = Reader(library, kernel)
    weights = {
        k: float(
            Fraction((-1) ** (k + 1), k)
            * Fraction(
                math.factorial(6) ** 2, math.factorial(6 - k) * math.factorial(6 + k)
            )
        )
        for k in range(1, 7)
    }
    rows = []
    journal = output.with_suffix(".journal.jsonl").open("x")
    try:
        for center in protocol["centers"]:
            date = datetime.fromisoformat(center["date_tdb"])
            integer = date.toordinal() + 1721424
            fraction = 0.5 + (date.hour * 3600 + date.minute * 60 + date.second) / 86400
            epoch = shifted(integer, fraction, 0)
            offsets = sorted(
                {0, *(k * h for h in protocol["steps_days"] for k in range(-6, 7) if k)}
            )
            samples = {
                str(offset): sample(reader, shifted(*epoch, offset), protocol)
                for offset in offsets
            }
            derivatives = {
                str(h): [
                    math.fsum(
                        weights[k]
                        * (
                            samples[str(k * h)]["selected_direction"][axis]
                            - samples[str(-k * h)]["selected_direction"][axis]
                        )
                        for k in range(1, 7)
                    )
                    / h
                    for axis in range(3)
                ]
                for h in protocol["steps_days"]
            }
            rows.append(
                {
                    **center,
                    "jd0_tdb": epoch[0],
                    "fraction_tdb": epoch[1],
                    "samples": samples,
                    "derivatives_per_tdb_day": derivatives,
                    "selected_direction_derivative_per_tdb_day": derivatives[
                        str(protocol["chosen_step_days"])
                    ],
                    "step_difference_arcsec_per_day": math.degrees(
                        math.dist(*derivatives.values())
                    )
                    * 3600,
                }
            )
            journal.write(json.dumps(rows[-1], allow_nan=False) + "\n")
            journal.flush()
            print("Collected split-TDB", center["date_tdb"], flush=True)
    finally:
        journal.close()
        reader.close()
    if (
        digest(kernel) != protocol["kernel_sha256"]
        or digest(library) != protocol["reader_library_sha256"]
    ):
        raise ValueError("Source changed during reference collection")
    assert not any(
        k == "fatebridge" or k.startswith("fatebridge.") or k == "swisseph"
        for k in sys.modules
    )
    result = {
        "protocol_sha256": digest(protocol_path),
        "generator_sha256": digest(Path(__file__)),
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "kernel_sha256_before_and_after": protocol["kernel_sha256"],
        "reader_library_sha256_before_and_after": protocol["reader_library_sha256"],
        "coverage": reader.coverage,
        "dependency_versions": protocol["dependency_versions"],
        "candidate_imported": False,
        "candidate_compared": False,
        "time_scale": "TDB",
        "tt_tdb_conversion_applied": False,
        "rows": rows,
        "scope": "Independent CALCEPH/ERFA numerical reference under the declared TDB reception model. Shared DE441 physics is not independent observational evidence. Solar body uses observation epoch,not an iterated closest-approach epoch. Earlier TT and Horizons endpoint failures remain unchanged; no TT accuracy or authority certification.",
    }
    with output.open("x") as handle:
        handle.write(
            json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["protocol", "kernel", "library", "output"]:
        parser.add_argument("--" + name, required=True, type=Path)
    arguments = parser.parse_args()
    collect(arguments.protocol, arguments.kernel, arguments.library, arguments.output)
