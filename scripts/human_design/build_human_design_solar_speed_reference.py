"""Cross-check Sun roots on the integer IEEE-754 lattice, without engine imports.

Same Swiss library and source files, a different search implementation: this
is numerical cross-checking, never independent physical ephemeris validation.
"""

import argparse
import hashlib
import json
import struct
from fractions import Fraction
from pathlib import Path

import swisseph as swe

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "tests/fixtures/human-design-solar-speed-lattice.json"
REFERENCE = ROOT / "tests/fixtures/human-design-astronomy-de440.json"


def bits(value):
    return struct.unpack(">Q", struct.pack(">d", value))[0]


def number(value):
    return struct.unpack(">d", struct.pack(">Q", value))[0]


def extract(ephe: Path):
    swe.set_ephe_path(str(ephe.resolve()))
    rows = []
    for backend, mask in (("swieph", 2), ("moshier", 4)):
        for pair in json.loads(REFERENCE.read_text())["pairs"]:
            birth = pair["personality"]["jd_tt"]
            calls = 0

            def sun(tt):
                nonlocal calls
                values, flags = swe.calc(tt, 0, mask | 256)
                calls += 1
                if flags != mask | 256:
                    raise ValueError("Unexpected coordinate or fallback flags")
                return float(values[0]) % 360

            natal = sun(birth)

            def residual(tt):
                return (Fraction(natal) - Fraction(sun(tt))) % 360 - 88

            lo, hi = bits(birth - 110), bits(birth - 70)
            assert residual(number(lo)) > 0 > residual(number(hi))
            while hi - lo > 1:
                mid = (lo + hi) // 2
                value = residual(number(mid))
                if value == 0:
                    lo = hi = mid
                    break
                if value > 0:
                    lo = mid
                else:
                    hi = mid
            candidates = [(number(i), residual(number(i))) for i in (lo, hi)]
            chosen, value = min(candidates, key=lambda p: (abs(p[1]), p[0]))
            rows.append(
                {
                    "label": pair["label"],
                    "backend": backend,
                    "request_flags": mask | 256,
                    "birth_jd_tt": birth,
                    "birth_sun_longitude": natal,
                    "lower_jd_tt": number(lo),
                    "upper_jd_tt": number(hi),
                    "selected_jd_tt": chosen,
                    "selected_sun_longitude": sun(chosen),
                    "exact_residual": [str(value.numerator), str(value.denominator)],
                    "native_calls": calls,
                }
            )
    return {
        "method_id": "human_design_sun_speed_integer_lattice_reference_v1",
        "reference_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "native_version": swe.version,
        "source_files": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(ephe.glob("sepl_*.se1"))
            if p.name in {"sepl_12.se1", "sepl_18.se1"}
        },
        "cases": rows,
        "scope": "The unchanged122reference birth epochs on2backends; integer binary64 index bisection with exact Fraction residuals and actual SPEED flags. Same library/files, not an independent sky model, source doctrine or continuous-root certificate.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ephe", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = json.dumps(extract(args.ephe), indent=2) + "\n"
    if args.check:
        if TARGET.read_text() != value:
            raise SystemExit("Native lattice reference drifted")
    else:
        TARGET.write_text(value)


if __name__ == "__main__":
    main()
