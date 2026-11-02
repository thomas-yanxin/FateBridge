"""Re-adjudicate frozen boundary receipts against their actual 12-Jie contract.

The original full engine execution and its erroneous 24-term liuri checks are
retained in audit-first.py.txt and bazi-boundary-decisions-first-v1.json.gz.
This entrypoint reads those same receipts; it does not recalculate production.
"""

from __future__ import annotations

import argparse
import bisect
import gzip
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.collect_bazi_boundary_probes import JIE_BRANCHES, digest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_boundary_decisions_v1"


def audit():
    protocol_path = FIXTURE / "window-adjudication-protocol.json"
    if (
        digest(protocol_path)
        != protocol_path.with_suffix(".sha256").read_text().strip()
    ):
        raise ValueError("Frozen window-adjudication protocol changed")
    protocol = json.loads(protocol_path.read_text())
    source = ROOT / protocol["first_observation"]
    if digest(source) != protocol["first_sha256"]:
        raise ValueError("Original observed receipts changed")
    first = json.loads(gzip.decompress(source.read_bytes()))
    if digest(FIXTURE / "audit-first.py.txt") != first["runner_sha256"]:
        raise ValueError("First evaluator not retained exactly")
    old_protocol = json.loads((FIXTURE / "protocol.json").read_text())
    reference = ROOT / old_protocol["reference_path"]
    if digest(reference) != first["reference_sha256"]:
        raise ValueError("Independent reference changed")
    roots = json.loads(reference.read_text())["rows"]
    jie = [r for r in roots if r["name"] in JIE_BRANCHES]
    times = [r["jd_tt"] for r in jie]
    probes = json.loads((FIXTURE / "probes.json").read_text())
    probe_ids = [p["id"] for p in probes["rows"]]
    results = []
    changed_keys = {"liuri_last_term", "liuri_next_term"}
    for arm in first["arms"]:
        if [r["probe_id"] for r in arm["comparisons"]] != probe_ids or len(
            probe_ids
        ) != 9744:
            raise ValueError("Original complete probe cohort changed")
        rows = []
        for original in arm["comparisons"]:
            index = bisect.bisect_right(times, original["actual_input_jd_tt"]) - 1
            expected = {
                "liuri_last_term": jie[index]["name"] if index >= 0 else None,
                "liuri_next_term": (
                    jie[index + 1]["name"] if index + 1 < len(jie) else None
                ),
            }
            corrected = dict(original["matches"])
            corrected.update(
                {
                    k: original["actual"][k] == v if v is not None else None
                    for k, v in expected.items()
                }
            )
            if any(
                corrected[k] != original["matches"][k]
                for k in corrected
                if k not in changed_keys
            ):
                raise ValueError("A protected unrelated criterion changed")
            rows.append(
                {
                    "probe_id": original["probe_id"],
                    "actual_input_jd_tt": original["actual_input_jd_tt"],
                    "original_matches": original["matches"],
                    "corrected_12jie_expected": expected,
                    "actual_liuri_window": {
                        k: original["actual"][k] for k in changed_keys
                    },
                    "matches": corrected,
                }
            )
        counts = {
            key: {
                "matched": sum(r["matches"][key] is True for r in rows),
                "mismatched": sum(r["matches"][key] is False for r in rows),
                "not_applicable_reference_endpoint": sum(
                    r["matches"][key] is None for r in rows
                ),
            }
            for key in rows[0]["matches"]
        }
        for key in counts:
            if key not in changed_keys and counts[key] != arm["counts"][key]:
                raise ValueError("A protected original count changed")
        results.append(
            {
                "arm": arm["arm"],
                "probe_count": len(rows),
                "comparisons": rows,
                "counts": counts,
                "original_one_second_root_gate_failures": arm[
                    "original_one_second_root_gate_failures"
                ],
                "maximum_root_difference_seconds": arm[
                    "maximum_root_difference_seconds"
                ],
                "mismatched_probe_ids": [
                    r["probe_id"]
                    for r in rows
                    if any(v is False for v in r["matches"].values())
                ],
                "all_other_check_vectors_exactly_preserved": True,
            }
        )
    return {
        "protocol_sha256": digest(protocol_path),
        "first_observation_sha256": digest(source),
        "first_runner_sha256": first["runner_sha256"],
        "current_runner_sha256": digest(Path(__file__)),
        "reference_sha256": digest(reference),
        "arms": results,
        "production_values_recomputed_or_changed": False,
        "reference_or_old_gate_changed": False,
        "new_independent_reference_credit": 0,
        "full_calendar_acceptance": False,
        "overall_score": None,
        "scope": "Only two liuri expectations corrected to their existing12Jie month-window contract. Raw24termmischecks remain immutable; all other7vectors and all actual values unchanged. This is evaluator repair, not a numerical improvement or authority score.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite window adjudication")
    result = audit()
    data = (
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    with args.output.open("xb") as handle:
        handle.write(gzip.compress(data, mtime=0))
    args.output.with_suffix(".sha256").write_text(digest(args.output) + "\n")
    for arm in result["arms"]:
        print(
            json.dumps(
                {k: v for k, v in arm.items() if k != "comparisons"}, ensure_ascii=False
            )
        )


if __name__ == "__main__":
    main()
