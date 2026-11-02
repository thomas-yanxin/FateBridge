"""Evaluate the frozen physical SPK Sun prototype, without production adoption."""

from __future__ import annotations

import gzip
import importlib.metadata
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.collect_bazi_boundary_probes import digest, reference_state

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_boundary_decisions_v1"


def main():
    output = ROOT / "docs/validation/bazi-spk-sun-development-first-v1.json.gz"
    if output.exists():
        raise FileExistsError("Refusing to overwrite first SPK experiment")
    protocol_path = FIXTURE / "spk-experiment-protocol.json"
    if (
        digest(protocol_path)
        != protocol_path.with_suffix(".sha256").read_text().strip()
    ):
        raise ValueError("Frozen SPK protocol changed")
    protocol = json.loads(protocol_path.read_text())
    candidate = ROOT / protocol["candidate_path"]
    if digest(candidate) != protocol["candidate_sha256"]:
        raise ValueError("Candidate changed after freeze")
    kernel = Path(protocol["kernel_path"])
    if digest(kernel) != protocol["kernel_sha256"]:
        raise ValueError("Actual kernel differs from declared official DE440")
    reference = ROOT / protocol["reference_path"]
    if digest(reference) != protocol["reference_sha256"]:
        raise ValueError("Frozen independent reference changed")
    for name, expected in protocol["dependencies"].items():
        if importlib.metadata.version(name) != expected:
            raise ValueError("Unexpected physical experiment dependency: " + name)
    probe_path = FIXTURE / "probes.json"
    if digest(probe_path) != probe_path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen minute probes changed")
    spec = importlib.util.spec_from_file_location("_spk_physical_candidate", candidate)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sun = module.SPKSun(kernel)
    roots = json.loads(reference.read_text())["rows"]
    candidate_roots, comparisons = [], []
    try:
        for index, root in enumerate(roots):
            year, month, half = root["year"], index % 24 // 2 + 1, index % 2
            low_day, high_day = (1, 12) if half == 0 else (12, 28)
            low = date(year, month, low_day).toordinal() + 1721424.5
            high = date(year, month, high_day).toordinal() + 1721424.5
            actual = sun.crossing(root["solar_longitude_degrees"], low, high)
            difference = (actual["jd_tt"] - root["jd_tt"]) * 86400
            candidate_roots.append({**root, "jd_tt": actual["jd_tt"]})
            comparisons.append(
                {
                    "year": year,
                    "name": root["name"],
                    "reference_tt": root["jd_tt"],
                    "candidate_tt": actual["jd_tt"],
                    "candidate_bracket_tt": actual["bracket_tt"],
                    "difference_seconds": difference,
                    "within_original_one_second_gate": abs(difference) <= 1.0,
                }
            )
            if index % 600 == 0:
                print({"roots_completed": index + 1, "year": year}, flush=True)
    finally:
        sun.close()
    probe_rows = []
    for probe in json.loads(probe_path.read_text())["rows"]:
        actual = reference_state(
            candidate_roots, probe["input_jd_tt_under_frozen_policy"]
        )
        expected = probe["reference_state_under_frozen_policy"]
        probe_rows.append(
            {
                "probe_id": probe["id"],
                "actual": actual,
                "reference_expected": expected,
                "matches": {
                    k: actual[k] == v if v is not None else None
                    for k, v in expected.items()
                },
            }
        )
    failures = [r for r in probe_rows if any(v is False for v in r["matches"].values())]
    root_failures = sum(not r["within_original_one_second_gate"] for r in comparisons)
    result = {
        "protocol_sha256": digest(protocol_path),
        "candidate_sha256": digest(candidate),
        "runner_sha256": digest(Path(__file__)),
        "kernel_sha256": digest(kernel),
        "reference_sha256": digest(reference),
        "probes_sha256": digest(probe_path),
        "dependencies": protocol["dependencies"],
        "root_count": len(comparisons),
        "root_comparisons": comparisons,
        "probe_count": len(probe_rows),
        "probe_comparisons": probe_rows,
        "original_one_second_gate_failures": root_failures,
        "maximum_absolute_root_difference_seconds": max(
            abs(r["difference_seconds"]) for r in comparisons
        ),
        "minute_probe_failures": len(failures),
        "failed_probe_ids": [r["probe_id"] for r in failures],
        "development_gate_passed": root_failures == 0 and not failures,
        "generic_validation": "not_run",
        "production_integration": "not_run",
        "adopted": False,
        "new_independent_reference_credit": 0,
        "full_calendar_acceptance": False,
        "overall_score": None,
        "scope": "All exposed root and minute development cases; same JPL kernel and interpolation library underpin reference. This validates distinct physical-frame/root code, not independent physical observations or complete civil UTC accuracy.",
    }
    data = (
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    with output.open("xb") as handle:
        handle.write(gzip.compress(data, mtime=0))
    output.with_suffix(".sha256").write_text(digest(output) + "\n")
    print(
        {
            k: result[k]
            for k in [
                "root_count",
                "original_one_second_gate_failures",
                "maximum_absolute_root_difference_seconds",
                "probe_count",
                "minute_probe_failures",
                "development_gate_passed",
                "adopted",
            ]
        }
    )


if __name__ == "__main__":
    main()
