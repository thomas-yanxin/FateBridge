"""Compare a specified frozen candidate to the complete frozen Horizons grid.

Every run is an exposed-reference comparison, never a new blind trial. Output
files cannot be overwritten; source collection and missing-DUT1 records remain
separate from numerical candidate results.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument("--native-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve earlier comparison outputs")
    protocol_raw = (args.reference_dir / "protocol.json").read_bytes()
    if (
        digest(protocol_raw)
        != (args.reference_dir / "protocol.sha256").read_text().strip()
    ):
        raise ValueError("Protocol hash mismatch")
    protocol = json.loads(protocol_raw)
    manifest_raw = (args.reference_dir / "manifest.json").read_bytes()
    if (
        digest(manifest_raw)
        != (args.reference_dir / "manifest.sha256").read_text().strip()
    ):
        raise ValueError("Reference manifest hash mismatch")
    manifest = json.loads(manifest_raw)
    if manifest["protocol_sha256"] != digest(protocol_raw):
        raise ValueError("Manifest belongs to another protocol")
    for source in manifest["references"]:
        raw = (args.reference_dir / source["file"]).read_bytes()
        if (
            digest(raw) != source["sha256"]
            or digest(gzip.decompress(raw)) != source["raw_sha256"]
        ):
            raise ValueError("Original reply changed")
    raw_rows = gzip.decompress((args.reference_dir / "reference.json.gz").read_bytes())
    if digest(raw_rows) != manifest["reference_sha256"]:
        raise ValueError("Converted reference hash mismatch")
    rows = json.loads(raw_rows)
    grid_raw = (args.reference_dir / "selected-instants.json").read_bytes()
    if digest(grid_raw) != protocol["selection"]["selected_instants_sha256"]:
        raise ValueError("Selection hash mismatch")
    if [row["instant"] for row in rows] != json.loads(grid_raw) or len(
        rows
    ) != protocol["selection"]["expected_points"]:
        raise ValueError("Missing, duplicated or unselected reference points")
    candidate_hashes = {
        "src/fatebridge/utils/solar_time.py": protocol["candidate_source_sha256"],
        "src/fatebridge/core/ephemeris_runtime.py": protocol["runtime_source_sha256"],
    }
    native_expected = json.loads(args.native_manifest.read_text())
    if digest(args.native_manifest.read_bytes()) != protocol["native_inventory_sha256"]:
        raise ValueError("Native inventory is not the frozen inventory")

    def verify_candidate() -> None:
        for path, expected in candidate_hashes.items():
            if digest((args.candidate_root / path).read_bytes()) != expected:
                raise ValueError(f"Candidate changed: {path}")
        actual = {p.name: digest(p.read_bytes()) for p in args.native_dir.glob("*.se1")}
        if actual != native_expected:
            raise ValueError("Native inventory changed")

    verify_candidate()
    sys.path.insert(0, str(args.candidate_root / "src"))
    from fatebridge.core import ephemeris_runtime as runtime
    from fatebridge.utils import solar_time

    if args.candidate_root.resolve() not in Path(solar_time.__file__).resolve().parents:
        raise ValueError("Imported another candidate")
    tolerance = protocol["tolerance_seconds"]
    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "fixed-candidate exposed-reference comparison, not a new blind trial",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": digest(protocol_raw),
        "reference_manifest_sha256": digest(manifest_raw),
        "reference_sha256": manifest["reference_sha256"],
        "candidate_hashes": candidate_hashes,
        "pyswisseph_version": importlib.metadata.version("pyswisseph"),
        "tolerance_seconds": tolerance,
        "source_points": len(rows),
        "noon_overlap_with_previous_daily_reference": sum(
            r["instant"][11:19] == "12:00:00" for r in rows
        ),
        "missing_reported_dut1": sum(r["dut1_seconds"] is None for r in rows),
        "time_scale_scope": protocol["time_scale_scope"],
        "dut1_scope": "Numeric DUT1 includes Horizons predictions/extrapolation outside the header's data-based EOP coverage; availability is not measurement or future UTC truth.",
        "provider_scope": "Modes describe configured directories. time_equ returns no provider flag; calc_ut preflight flags at three dates do not prove every EOT call used that provider.",
        "modes": {},
        "whole_goal_achieved": False,
        "overall_score": None,
    }
    with tempfile.TemporaryDirectory(prefix="bazi-intraday-moshier-") as empty:
        for name, folder in (
            ("configured_native", args.native_dir),
            ("empty_directory", Path(empty)),
        ):
            os.environ["SE_EPHE_PATH"] = str(folder)
            runtime.configure_ephemeris_path(str(folder))
            preflight = []
            for year in (1900, 2000, 2100):
                jd = runtime.ephemeris_call("julday", year, 1, 1, 12.0)
                _, flags = runtime.ephemeris_call(
                    "calc_ut", jd, runtime.swe.SUN, runtime.swe.FLG_SWIEPH
                )
                preflight.append({"year": year, "retflags": flags})
            errors, failures, by_hour = (
                [],
                [],
                {
                    f"{h:02d}": {"count": 0, "failed": 0, "maximum_seconds": 0.0}
                    for h in range(24)
                },
            )
            worst = None
            for row in rows:
                value = solar_time.calculate_equation_of_time_minutes(
                    datetime.fromisoformat(row["instant"])
                )
                error = abs(value - row["equation_of_time_minutes"]) * 60
                if not math.isfinite(error):
                    raise ValueError("Nonfinite comparison")
                errors.append(error)
                hour = by_hour[row["instant"][11:13]]
                hour["count"] += 1
                hour["maximum_seconds"] = max(hour["maximum_seconds"], error)
                observation = {
                    **row,
                    "candidate_minutes": value,
                    "absolute_error_seconds": error,
                }
                if worst is None or error > worst["absolute_error_seconds"]:
                    worst = observation
                if error > tolerance:
                    failures.append(observation)
                    hour["failed"] += 1
            report["modes"][name] = {
                "count": len(rows),
                "passed": len(rows) - len(failures),
                "failed": len(failures),
                "maximum_seconds": max(errors),
                "mean_seconds": math.fsum(errors) / len(errors),
                "worst": worst,
                "failures": failures,
                "by_hour": by_hour,
                "provider_preflight": preflight,
            }
            print(
                name,
                len(rows) - len(failures),
                "passed;",
                len(failures),
                "failed; max",
                max(errors),
                "seconds",
                flush=True,
            )
    verify_candidate()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(
        digest(args.output.read_bytes()) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
