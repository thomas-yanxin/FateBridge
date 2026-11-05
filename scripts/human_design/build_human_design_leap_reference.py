"""Generate an independent UTC leap oracle using unmodified official SOFA C.

No FateBridge engine imports. The planned labels are frozen before executing
the reference routines. Neither failed labels nor rows may be omitted.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from scripts.astronomy.build_utc1960_reference import (
    ARCHIVE_SHA256,
    ARCHIVE_URL,
    SOURCE_FILES,
    SOURCE_SHA256,
    SOURCE_URL,
)

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "tests/fixtures/human-design-leap-plan.json"
TARGET = ROOT / "tests/fixtures/human-design-leap-sofa.json"


def plan_from_source(source: Path) -> dict:
    text = (source / "dat.c").read_text()
    array = text.split("} changes[] = {", 1)[1].split("};", 1)[0]
    dates = re.findall(r"\{\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\}", array)
    steps = [
        (int(y), int(m), float(offset)) for y, m, offset in dates if int(y) >= 1972
    ]
    labels = []
    for previous, following in zip(steps, steps[1:]):
        y, m, offset = following
        if offset - previous[2] != 1:
            raise ValueError("Unexpected SOFA leap step; retain and investigate")
        midnight = datetime(y, m, 1)
        day = midnight - timedelta(days=1)
        for second in (59, 60):
            labels.append(f"{day:%Y-%m-%d}T23:59:{second:02d}+00:00")
        labels.append(midnight.isoformat() + "+00:00")
    if len(labels) != 81:
        raise ValueError(
            "The pinned release must yield all 27 known positive leap seconds"
        )
    return {
        "method_id": "human_design_all_27_sofa_leap_labels_v1",
        "source_url": SOURCE_URL,
        "dat_c_sha256": SOURCE_SHA256["dat.c"],
        "selection": "All post-1972 +1-second steps in the pinned official SOFA dat.c; one second before, inserted second, and following midnight. No chart-feedback selection.",
        "tolerance_seconds": 0.0002,
        "scope": "UTC label to TT only; no UT1, ephemeris, interpretation or birth-record certification.",
        "utc_labels": labels,
    }


def build(source: Path, compiler: str) -> dict:
    hashes = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in SOURCE_FILES
    }
    if hashes != SOURCE_SHA256:
        raise ValueError("SOFA source differs from the pinned official release")
    plan = json.loads(PLAN.read_text())
    if plan != plan_from_source(source):
        raise ValueError("Frozen leap plan differs from the source-defined coverage")
    cases = []
    with tempfile.TemporaryDirectory(prefix="fatebridge-hd-leap-sofa-") as work:
        library = Path(work) / "sofa.so"
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
        sofa.iauDtf2d.argtypes = (
            [ctypes.c_char_p] + [ctypes.c_int] * 5 + [number, pointer, pointer]
        )
        sofa.iauUtctai.argtypes = [number, number, pointer, pointer]
        sofa.iauTaitt.argtypes = [number, number, pointer, pointer]
        for label in plan["utc_labels"]:
            year, month, day = map(int, label[:10].split("-"))
            hour, minute, second = map(int, label[11:19].split(":"))
            u1, u2, a1, a2, t1, t2 = (number() for _ in range(6))
            statuses = [
                sofa.iauDtf2d(
                    b"UTC",
                    year,
                    month,
                    day,
                    hour,
                    minute,
                    second,
                    ctypes.byref(u1),
                    ctypes.byref(u2),
                )
            ]
            statuses.append(sofa.iauUtctai(u1, u2, ctypes.byref(a1), ctypes.byref(a2)))
            statuses.append(sofa.iauTaitt(a1, a2, ctypes.byref(t1), ctypes.byref(t2)))
            cases.append(
                {
                    "utc_label": label,
                    "tt_jd1": t1.value,
                    "tt_jd2": t2.value,
                    "statuses": statuses,
                }
            )
    if any(case["statuses"] != [0, 0, 0] for case in cases):
        raise ValueError("SOFA returned a warning or error; do not discard a case")
    return {
        "method_id": "official_sofa_c_utc_tai_tt_v1",
        "source_url": SOURCE_URL,
        "archive_url": ARCHIVE_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "source_file_sha256": hashes,
        "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "scope": plan["scope"],
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--compiler", default="cc")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.plan_only:
        if PLAN.exists():
            raise ValueError("Never overwrite the frozen plan")
        hashes = {
            n: hashlib.sha256((args.source / n).read_bytes()).hexdigest()
            for n in SOURCE_FILES
        }
        if hashes != SOURCE_SHA256:
            raise ValueError("Unexpected SOFA source")
        PLAN.write_text(
            json.dumps(plan_from_source(args.source), ensure_ascii=False, indent=2)
            + "\n"
        )
        return
    rendered = (
        json.dumps(build(args.source, args.compiler), ensure_ascii=False, indent=2)
        + "\n"
    )
    if args.check:
        if TARGET.read_text() != rendered:
            raise ValueError("SOFA reference drift")
    else:
        if TARGET.exists():
            raise ValueError("Never overwrite existing reference output")
        TARGET.write_text(rendered)


if __name__ == "__main__":
    main()
