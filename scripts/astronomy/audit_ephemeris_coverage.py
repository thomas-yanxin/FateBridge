"""Audit pinned file coverage and native model availability, not sky accuracy."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.astro.ephemeris_files import ephemeris_files_for_years
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    verify_ephemeris_bytes,
)
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.astro.time_scales import ephemeris_time


def interval_coverage(
    rows: List[Dict[str, Any]], lower: float, upper: float
) -> Dict[str, Any]:
    intervals = sorted((r["start_tt_jd"], r["end_tt_jd"]) for r in rows)
    cursor = lower
    gaps = []
    for start, end in intervals:
        if end < cursor or start > upper:
            continue
        if start > cursor:
            gaps.append([cursor, min(start, upper)])
        cursor = max(cursor, end)
        if cursor >= upper:
            break
    if cursor < upper:
        gaps.append([cursor, upper])
    return {"domain_tt_jd": [lower, upper], "gaps": gaps, "covered": not gaps}


def audit(path: Path, start_year: int, end_year: int) -> Dict[str, Any]:
    if runtime.swe is None:
        raise RuntimeError("Swiss Ephemeris runtime is required")
    if not 1 <= start_year <= end_year <= 9999:
        raise ValueError("Require 1 <= start year <= end year <= 9999")
    selected = runtime.configure_ephemeris_path(str(path))
    # A nonempty SE_EPHE_PATH intentionally overrides explicit configuration.
    # Do not verify one directory while the native library reads another.
    if selected is None or Path(selected).resolve() != path.resolve():
        raise ValueError(
            "Effective native path differs from the directory being audited"
        )
    manifest = load_ephemeris_manifest()
    names = ephemeris_files_for_years(range(start_year, end_year + 1))
    fingerprints = []
    for name in names:
        data = (path / name).read_bytes()
        verify_ephemeris_bytes(name, data, manifest)
        fingerprints.append({"name": name, "sha256": hashlib.sha256(data).hexdigest()})
    moments = set()
    for year in range(start_year, end_year + 1):
        moments.add(datetime(year, 1, 1, tzinfo=timezone.utc))
        moments.add(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
    for year in range(600, 10000, 600):
        if start_year <= year <= end_year:
            boundary = datetime(year, 1, 1, tzinfo=timezone.utc)
            for day in range(-16, 17):
                moment = boundary + timedelta(days=day)
                if start_year <= moment.year <= end_year:
                    moments.add(moment)
    headers: Dict[str, Dict[str, Any]] = {}
    errors = []
    checked = 0
    lower, upper = math.inf, -math.inf
    started = time.monotonic()
    for index, moment in enumerate(sorted(moments), start=1):
        times = ephemeris_time(moment)
        if times.jd_tt is None:
            raise RuntimeError("TT unavailable with the native ephemeris runtime")
        lower, upper = min(lower, times.jd_tt), max(upper, times.jd_tt)
        for name, body in PLANET_SWISSEPH_IDS.items():
            try:
                coordinates, flags = runtime.ephemeris_call(
                    "calc",
                    times.jd_tt,
                    body,
                    runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
                )
                if flags < 0 or not flags & runtime.swe.FLG_SWIEPH:
                    raise ValueError(f"returned model flags {flags}")
                if not all(math.isfinite(value) for value in coordinates):
                    raise ValueError("nonfinite coordinate")
                checked += 1
            except Exception as error:
                errors.append(
                    {"utc": moment.isoformat(), "body": name, "error": str(error)}
                )
        for slot, kind in [(0, "planet"), (1, "moon")]:
            filename, first, last, denum = runtime.ephemeris_call(
                "get_current_file_data", slot
            )
            if filename:
                headers[Path(filename).name] = {
                    "name": Path(filename).name,
                    "kind": kind,
                    "start_tt_jd": first,
                    "end_tt_jd": last,
                    "jpl_de_number": denum,
                }
        if index % 2000 == 0:
            print(
                f"Checked {index} instants / {checked} native states; {len(errors)} failures",
                flush=True,
            )
    rows = list(headers.values())
    return {
        "scope": "Pinned file identity, nominal TT interval union and native model availability at every CE year endpoint plus segment-switch neighbourhoods. Not independent positional accuracy, observed historical UT1, future UTC or house accuracy certification. Mean node is analytic; its SWIEPH flag does not prove file access.",
        "year_range": [start_year, end_year],
        "manifest_id": manifest["id"],
        "source_commit": manifest["source_commit"],
        "library_version": runtime.swe.version,
        "file_fingerprints": fingerprints,
        "native_file_headers": sorted(rows, key=lambda row: row["name"]),
        "interval_coverage": {
            kind: interval_coverage(
                [row for row in rows if row["kind"] == kind], lower, upper
            )
            for kind in ["planet", "moon"]
        },
        "instants_checked": len(moments),
        "native_state_checks_passed": checked,
        "failures": errors,
        "duration_seconds": time.monotonic() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ephe-path", type=Path, required=True)
    parser.add_argument("--start-year", type=int, default=1)
    parser.add_argument("--end-year", type=int, default=9999)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.ephe_path, args.start_year, args.end_year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "instants": report["instants_checked"],
                "native_states": report["native_state_checks_passed"],
                "failures": len(report["failures"]),
                "intervals_covered": {
                    k: v["covered"] for k, v in report["interval_coverage"].items()
                },
            }
        )
    )
    if report["failures"] or any(
        not value["covered"] for value in report["interval_coverage"].values()
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
