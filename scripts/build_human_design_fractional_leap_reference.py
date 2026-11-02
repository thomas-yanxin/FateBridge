"""Reproduce all135 frozen fractional-leap UTC-to-TT facts with official SOFA C.

Maintenance only; no FateBridge engine import, online download or test-time
compiler. Original plan, rejected outputs and scalar-TT tolerance stay frozen.
"""

import argparse
import ctypes
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from scripts.build_utc1960_reference import SOURCE_SHA256

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/human_design_fractional_leap_v1"


def derive(source: Path, compiler: str) -> dict:
    identity = {
        n: hashlib.sha256((source / n).read_bytes()).hexdigest() for n in SOURCE_SHA256
    }
    if identity != SOURCE_SHA256:
        raise ValueError("Official pinned SOFA source files differ")
    plan_bytes = (FIXTURE / "plan.json").read_bytes()
    plan = json.loads(plan_bytes)
    rows = []
    with tempfile.TemporaryDirectory(prefix="fatebridge-fractional-leap-") as directory:
        path = Path(directory) / "sofa.so"
        subprocess.run(
            [
                compiler,
                "-shared",
                "-fPIC",
                "-O2",
                "-I",
                str(source),
                *[str(source / n) for n in identity if n.endswith(".c")],
                "-lm",
                "-o",
                str(path),
            ],
            check=True,
        )
        so = ctypes.CDLL(str(path))
        number = ctypes.c_double
        pointer = ctypes.POINTER(number)
        so.iauDtf2d.argtypes = [
            ctypes.c_char_p,
            *[ctypes.c_int] * 5,
            number,
            pointer,
            pointer,
        ]
        so.iauUtctai.argtypes = [number, number, pointer, pointer]
        so.iauTaitt.argtypes = [number, number, pointer, pointer]
        for case in plan["cases"]:
            p = case["input"]
            a, b, e, f, g, h = [number() for _ in range(6)]
            seconds = 60 + case["utc_fraction_microseconds"] / 1000000
            statuses = [
                so.iauDtf2d(
                    b"UTC",
                    p["birth_year"],
                    p["birth_month"],
                    p["birth_day"],
                    23,
                    59,
                    seconds,
                    ctypes.byref(a),
                    ctypes.byref(b),
                ),
                so.iauUtctai(a.value, b.value, ctypes.byref(e), ctypes.byref(f)),
                so.iauTaitt(e.value, f.value, ctypes.byref(g), ctypes.byref(h)),
            ]
            if statuses != [0, 0, 0]:
                raise ValueError("SOFA did not confirm a planned UTC leap label")
            rows.append(
                {
                    "id": case["id"],
                    "utc_label": case["expected_utc_label"],
                    "tt_jd1": g.value,
                    "tt_jd2": h.value,
                    "statuses": statuses,
                }
            )
    return {
        "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "source_url": "https://www.iausofa.org/2023-10-11c",
        "archive_sha256": "d9c10833cae8b4d9361a0ffda31ec361fd1262362025bec4d4e51a880150ace2",
        "source_files": identity,
        "reference_imports_fatebridge": False,
        "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--compiler", default="cc")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(derive(args.source, args.compiler), indent=2) + "\n").encode()
    target = FIXTURE / "reference.json"
    if args.check:
        if target.read_bytes() != raw:
            raise SystemExit("Frozen fractional-leap reference bytes differ")
    else:
        target.write_bytes(raw)
    print(
        json.dumps(
            {
                "cases": 135,
                "reference_sha256": hashlib.sha256(raw).hexdigest(),
                "checked": args.check,
            }
        )
    )


if __name__ == "__main__":
    main()
