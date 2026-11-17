"""Independent exhaustive finite binary64 contact oracle; no FateBridge imports.

All seven-point sign/zero patterns are included. Every admissible initial
bracket/zero is enumerated before running either root implementation.
"""

import argparse
import hashlib
import itertools
import json
import struct
from fractions import Fraction
from pathlib import Path

PHASE = Path(__file__).parent
ANCHORS = (1700000.0, 2451545.0, 5373484.5)
ORIGINS = (100.0, 272.0)


def bits(value):
    return struct.unpack(">Q", struct.pack(">d", value))[0]


def number(index):
    return struct.unpack(">d", struct.pack(">Q", index))[0]


def sun_value(tt, center, origin, pattern):
    offset = bits(tt) - bits(center)
    if -3 <= offset <= 3:
        unit = Fraction(number(bits(origin) + 1)) - Fraction(origin)
        return float((Fraction(origin) - pattern[offset + 3] * unit) % 360)
    return float((Fraction(origin) + Fraction(tt) - Fraction(center)) % 360)


def generate():
    output = PHASE / "finite-contact-reference.jsonl"
    functions = windows = zeros = forward = 0
    with output.open("w") as stream:
        for birth, origin, pattern in itertools.product(
            ANCHORS, ORIGINS, itertools.product((-1, 0, 1), repeat=7)
        ):
            center = birth - 88
            base = bits(center)
            birth_sun = sun_value(birth, center, origin, pattern)
            # Include the widest 4-ULP halo of any possible initial contact.
            residuals = {
                i: (
                    Fraction(birth_sun)
                    - Fraction(sun_value(number(base + i), center, origin, pattern))
                )
                % 360
                - 88
                for i in range(-8, 9)
            }
            initial = [(i, i) for i in range(-3, 4) if residuals[i] == 0]
            initial += [
                (i, i + 1) for i in range(-4, 4) if residuals[i] > 0 > residuals[i + 1]
            ]
            assert initial
            expectations = []
            for lo, hi in initial:
                # Independent integer encoding, not the product nextafter helper.
                window = tuple(range(lo - 4, hi + 5))
                admissible = [(i, i, i) for i in window if residuals[i] == 0]
                for left, right in zip(window, window[1:]):
                    if residuals[left] > 0 > residuals[right]:
                        selected = (
                            left
                            if abs(residuals[left]) <= abs(residuals[right])
                            else right
                        )
                        admissible.append((left, right, selected))
                best = sorted(
                    admissible, key=lambda row: (abs(residuals[row[2]]), row[2])
                )[0]
                expectations.append({"initial": [lo, hi], "preferred": list(best)})
                windows += 1
                zeros += lo == hi
                forward += lo != hi
            record = {
                "birth_tt": birth,
                "origin": origin,
                "pattern": pattern,
                "windows": expectations,
            }
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
            functions += 1
    assert functions == 3 * 2 * 3**7
    manifest = {
        "reference": output.name,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "functions": functions,
        "initial_windows": windows,
        "initial_zero_windows": zeros,
        "initial_forward_windows": forward,
        "criterion": "Exact selected TT and forward bracket/zero for every enumerated initial finite window. Original initial bracket is a subset; absolute exact residual may not increase.",
        "scope": "Finite binary64 numeric-function quality only. No global-domain, physical-time, ephemeris, source doctrine or predictive certification.",
        "no_fatebridge_imports": True,
        "all_ternary_seven_point_patterns_included": True,
    }
    (PHASE / "finite-contact-reference-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    PHASE = parser.parse_args().output_dir
    PHASE.mkdir(parents=True, exist_ok=True)
    generate()
