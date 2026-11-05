"""Freeze 1960 UTC coefficients and independent, compiled IAU SOFA epochs.

Maintenance only: provide the unmodified official SOFA 2023-10-11 c/src
directory. Ordinary tests use frozen numeric facts and never compile or fetch.
No FateBridge or Swiss Ephemeris code is imported by this generator.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "src/fatebridge/data/knowledge/western-utc1960.json"
REFERENCE = ROOT / "tests/fixtures/historical-utc-sofa.json"
SOURCE_URL = "https://www.iausofa.org/2023-10-11c"
ARCHIVE_URL = "https://www.iausofa.org/s/sofa_c-20231011tar.gz"
ARCHIVE_SHA256 = "d9c10833cae8b4d9361a0ffda31ec361fd1262362025bec4d4e51a880150ace2"
SOURCE_FILES = (
    "cal2jd.c",
    "jd2cal.c",
    "dat.c",
    "dtf2d.c",
    "utctai.c",
    "taitt.c",
    "sofa.h",
    "sofam.h",
)
SOURCE_SHA256 = {
    "cal2jd.c": "996773197e46c7dd7d7559a05281542b14694d781828fc8fa019829e059730b5",
    "jd2cal.c": "1c117cd6fc2106a94e85b8ccaca2a84dad264752841300cb05c63eb5b0c0616c",
    "dat.c": "c269b897cba4f204af65fb874ec7769fcf38b284735d9a6b76c03c51a462fab8",
    "dtf2d.c": "c6ac29b8c2934be0f18ab72a691c3cfde76da1ee5c4f5344d25cbf2f5d12028b",
    "utctai.c": "dc98532a2a6fa8361efec3593e9aaa0055de80d00f093b49000a97d79176dd31",
    "taitt.c": "bddf4ff4f702d28569d455c840d077af21edbdf7069018bd5f303b626ea0845b",
    "sofa.h": "e67c48b17565a060b4b2505a352e5c5eaf4e17aa4c2666d04525716f2ed8249b",
    "sofam.h": "21d8617d5eddaf8e9ed4fa3fc92bff54acebd633e93ad257c01311687ce69f71",
}


def coefficients(text: str) -> list[dict]:
    """Extract factual array values; do not transcribe the calculator's table."""
    drift = text.split("static const double drift[][2] = {", 1)[1].split("};", 1)[0]
    changes = text.split("} changes[] = {", 1)[1].split("};", 1)[0]
    rates = re.findall(r"\{\s*([\d.]+),\s*([\d.]+)\s*\}", drift)
    dates = re.findall(r"\{\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\}", changes)
    if len(rates) != 14 or len(dates) < 15 or int(dates[14][0]) != 1972:
        raise ValueError("Unrecognized SOFA pre-1972 coefficient arrays")
    return [
        {
            "effective_date": f"{int(year):04d}-{int(month):02d}-01",
            "offset_seconds": float(offset),
            "reference_mjd": int(float(reference)),
            "rate_seconds_per_day": float(rate),
        }
        for (year, month, offset), (reference, rate) in zip(dates[:14], rates)
    ]


def planned_clocks(rows: list[dict]) -> list[datetime]:
    """All months and every coefficient boundary, fixed without chart feedback."""
    clocks = {
        datetime(year, month, 15, 12, 34, 56, 125000, tzinfo=timezone.utc)
        for year in range(1960, 1972)
        for month in range(1, 13)
    }
    for row in [*rows, {"effective_date": "1972-01-01"}]:
        boundary = datetime.fromisoformat(row["effective_date"]).replace(
            tzinfo=timezone.utc
        )
        for seconds in (-1, 0, 0.001, 0.003, 0.006, 1):
            moment = boundary + timedelta(seconds=seconds)
            if moment.year >= 1960:
                clocks.add(moment)
    return sorted(clocks)


def build(source: Path, compiler: str) -> tuple[dict, dict]:
    digests = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in SOURCE_FILES
    }
    if digests != SOURCE_SHA256:
        raise ValueError("SOFA source bytes differ from the pinned official release")
    rows = coefficients((source / "dat.c").read_text())
    if rows[0]["effective_date"] != "1960-01-01":
        raise ValueError("SOFA reference does not begin at 1960 UTC")
    provenance = {
        "source_url": SOURCE_URL,
        "source_title": "IAU SOFA 2023-10-11 iauDat and UTC/TAI/TT routines",
        "source_sha256": digests["dat.c"],
        "archive_url": ARCHIVE_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "source_file_sha256": digests,
    }
    supplement = {
        **provenance,
        "scope": "1960 UTC rate/offset convention from SOFA; does not authenticate a local birth clock or national time-signal realization. Pre-1960 civil labels remain an explicit UT1 assumption. The 1961-1971 IERS source is preserved separately.",
        "formula": "TAI-UTC seconds = offset_seconds + (MJD_UTC - reference_mjd) * rate_seconds_per_day",
        "valid_until": "1961-01-01",
        "entries": rows[:1],
    }
    cases = []
    with tempfile.TemporaryDirectory(prefix="fatebridge-sofa-reference-") as work:
        library = Path(work) / "sofa-utc.so"
        subprocess.run(
            [
                compiler,
                "-shared",
                "-fPIC",
                "-O2",
                "-I",
                str(source),
                *[str(source / name) for name in SOURCE_FILES if name.endswith(".c")],
                "-lm",
                "-o",
                str(library),
            ],
            check=True,
            capture_output=True,
        )
        sofa = ctypes.CDLL(str(library))
        number = ctypes.c_double
        pointer = ctypes.POINTER(number)
        sofa.iauDat.argtypes = [ctypes.c_int] * 3 + [number, pointer]
        sofa.iauDtf2d.argtypes = (
            [ctypes.c_char_p] + [ctypes.c_int] * 5 + [number, pointer, pointer]
        )
        sofa.iauUtctai.argtypes = [number, number, pointer, pointer]
        sofa.iauTaitt.argtypes = [number, number, pointer, pointer]
        for moment in planned_clocks(rows):
            dat, u1, u2, a1, a2, t1, t2 = (number() for _ in range(7))
            clock_seconds = (
                moment.hour * 3600
                + moment.minute * 60
                + moment.second
                + moment.microsecond / 1e6
            )
            statuses = [
                sofa.iauDat(
                    moment.year,
                    moment.month,
                    moment.day,
                    clock_seconds / 86400,
                    ctypes.byref(dat),
                ),
                sofa.iauDtf2d(
                    b"UTC",
                    moment.year,
                    moment.month,
                    moment.day,
                    moment.hour,
                    moment.minute,
                    moment.second + moment.microsecond / 1e6,
                    ctypes.byref(u1),
                    ctypes.byref(u2),
                ),
            ]
            statuses.append(sofa.iauUtctai(u1, u2, ctypes.byref(a1), ctypes.byref(a2)))
            statuses.append(sofa.iauTaitt(a1, a2, ctypes.byref(t1), ctypes.byref(t2)))
            if any(status != 0 for status in statuses):
                raise ValueError(f"SOFA rejected planned clock {moment}: {statuses}")
            cases.append(
                {
                    "utc": moment.isoformat(),
                    "tai_minus_utc_seconds": dat.value,
                    "utc_quasi_jd_parts": [u1.value, u2.value],
                    "tt_jd_parts": [t1.value, t2.value],
                    "statuses": statuses,
                }
            )
    return supplement, {
        **provenance,
        "method": "Unmodified official C: iauDtf2d(UTC) -> iauUtctai -> iauTaitt; iauDat separately. No FateBridge or Swiss import.",
        "sampling_plan": "1960-1971 every month on day 15 at 12:34:56.125; every pre-1972 coefficient boundary and 1972 start at offsets -1,0,.001,.003,.006,1 seconds, excluding pre-1960 clocks. Not a blind population benchmark or birth-record authentication.",
        "comparison_tolerance_seconds": 0.0002,
        "historical_coefficients": rows,
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="official SOFA c/src directory")
    parser.add_argument("--compiler", default="cc")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for target, data in zip((DATA, REFERENCE), build(args.source, args.compiler)):
        if args.check:
            if json.loads(target.read_text()) != data:
                raise SystemExit(f"Frozen SOFA numeric facts differ: {target}")
        else:
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(
        "SOFA coefficients and compiled UTC/TT reference match"
        if args.check
        else "Saved SOFA numeric facts and compiled UTC/TT reference"
    )


if __name__ == "__main__":
    main()
