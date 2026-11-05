"""Reproduce the frozen Decimal/SOFA offset facts without the calculation engine.

Maintenance only. Ordinary tests read the pre-edit reference and never compile
or download. All planned rows, including future-date warnings, are retained.
"""

import argparse
import ctypes
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

from scripts.build_utc1960_reference import (
    ARCHIVE_SHA256,
    SOURCE_FILES,
    SOURCE_SHA256,
    SOURCE_URL,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/human_design/decimal_offset"


def build(source: Path, compiler: str) -> dict:
    if {
        n: hashlib.sha256((source / n).read_bytes()).hexdigest() for n in SOURCE_FILES
    } != SOURCE_SHA256:
        raise ValueError("SOFA source differs from the pinned official release")
    raw_plan = (FIXTURE / "plan.json").read_bytes()
    plan = json.loads(raw_plan)
    expected_clocks = []
    with localcontext() as context:
        context.prec = 100
        for case in plan["valid_cases"]:
            values = case["input"]
            hours = Decimal(values["birth_timezone"])
            micros = hours * Decimal(3600000000)
            if abs(hours) > 15 or micros != micros.to_integral_exact():
                raise ValueError("Planned decimal offset cannot be represented exactly")
            local = datetime(
                *(
                    values["birth_" + k]
                    for k in ("year", "month", "day", "hour", "minute", "second")
                )
            )
            utc = (local - timedelta(microseconds=int(micros))).replace(
                tzinfo=timezone.utc
            )
            if (
                int(micros) != case["expected_offset_microseconds"]
                or utc.isoformat() != case["expected_utc_label"]
            ):
                raise ValueError(
                    "Frozen plan disagrees with independent Decimal arithmetic"
                )
            expected_clocks.append(utc)
    cases = []
    with tempfile.TemporaryDirectory(prefix="fatebridge-decimal-sofa-") as directory:
        library = Path(directory) / "sofa.so"
        result = subprocess.run(
            [
                compiler,
                "-shared",
                "-fPIC",
                "-O2",
                "-I",
                str(source),
                *[str(source / n) for n in SOURCE_FILES if n.endswith(".c")],
                "-lm",
                "-o",
                str(library),
            ],
            capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(
                "SOFA reference compiler failed: "
                + result.stderr.decode(errors="replace")
            )
        sofa = ctypes.CDLL(str(library))
        number = ctypes.c_double
        pointer = ctypes.POINTER(number)
        sofa.iauDtf2d.argtypes = (
            [ctypes.c_char_p] + [ctypes.c_int] * 5 + [number, pointer, pointer]
        )
        sofa.iauUtctai.argtypes = [number, number, pointer, pointer]
        sofa.iauTaitt.argtypes = [number, number, pointer, pointer]
        sofa.iauCal2jd.argtypes = [ctypes.c_int] * 3 + [pointer, pointer]
        for case, moment in zip(plan["valid_cases"], expected_clocks, strict=True):
            a, b, c, d, e, f = (number() for _ in range(6))
            if moment.year < 1960:
                status = sofa.iauCal2jd(
                    moment.year,
                    moment.month,
                    moment.day,
                    ctypes.byref(a),
                    ctypes.byref(b),
                )
                if status != 0:
                    raise ValueError("SOFA rejected a planned civil calendar label")
                exact = (
                    Fraction(a.value)
                    + Fraction(b.value)
                    + Fraction(
                        ((moment.hour * 60 + moment.minute) * 60 + moment.second)
                        * 1000000
                        + moment.microsecond,
                        86400000000,
                    )
                )
                fact = {
                    "axis": "historical_UT1_calendar_only",
                    "jd_numerator": str(exact.numerator),
                    "jd_denominator": str(exact.denominator),
                    "statuses": [status],
                }
            else:
                statuses = [
                    sofa.iauDtf2d(
                        b"UTC",
                        moment.year,
                        moment.month,
                        moment.day,
                        moment.hour,
                        moment.minute,
                        moment.second + moment.microsecond / 1e6,
                        ctypes.byref(a),
                        ctypes.byref(b),
                    )
                ]
                statuses.append(
                    sofa.iauUtctai(a.value, b.value, ctypes.byref(c), ctypes.byref(d))
                )
                statuses.append(
                    sofa.iauTaitt(c.value, d.value, ctypes.byref(e), ctypes.byref(f))
                )
                if any(status < 0 for status in statuses):
                    raise ValueError("SOFA rejected a planned UTC label")
                fact = {
                    "axis": "UTC_TAI_TT",
                    "tt_jd1": e.value,
                    "tt_jd2": f.value,
                    "statuses": statuses,
                    "future_warning": any(statuses),
                }
            cases.append({"id": case["id"], **fact})
    return {
        "method_id": "decimal_integer_offset_and_official_SOFA_C_v1",
        "plan_sha256": hashlib.sha256(raw_plan).hexdigest(),
        "source_url": SOURCE_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "source_file_sha256": SOURCE_SHA256,
        "independent_generator_imports_fatebridge": False,
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--compiler", default="cc")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = json.dumps(build(args.source, args.compiler), indent=2) + "\n"
    target = FIXTURE / "reference.json"
    if args.check:
        if target.read_text() != result:
            raise SystemExit(
                "Frozen decimal/SOFA reference differs; retain and investigate"
            )
    else:
        target.write_text(result)


if __name__ == "__main__":
    main()
