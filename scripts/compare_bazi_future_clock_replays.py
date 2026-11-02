"""Compare every sequential/cohort record, allowing only the shard index field."""

import argparse
import gzip
import hashlib
import json
from itertools import zip_longest
from pathlib import Path


def compare_rows(sequential, merged):
    seen = set()
    for index, (left, right) in enumerate(zip_longest(sequential, merged)):
        if left is None or right is None:
            raise ValueError("Replay lengths differ")
        right = dict(right)
        if right.pop("cohort_index", None) != index:
            raise ValueError("Cohort order/index differs")
        if left["id"] in seen:
            raise ValueError("Repeated source identifier")
        seen.add(left["id"])
        if left != right:
            raise ValueError("Record differs: " + left["id"])
    return len(seen)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequential", type=Path, required=True)
    parser.add_argument("--merged", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    root = Path(__file__).resolve().parents[1]
    summaries = []
    for path in (args.sequential, args.merged):
        assert sha(path) == path.with_suffix(".sha256").read_text().strip()
        summary = json.loads(path.read_text())
        assert sha(root / summary["records"]) == summary["records_sha256"]
        assert not summary["source_drift"]
        summaries.append(summary)
    left, right = summaries
    assert left["counts"] == right["counts"]
    assert left["reference_sha256"] == right["reference_sha256"]
    with (
        gzip.open(root / left["records"], "rt") as a,
        gzip.open(root / right["records"], "rt") as b,
    ):
        count = compare_rows(map(json.loads, a), map(json.loads, b))
    assert count == left["registered_rows"] == left["counts"]["completed_rows"]
    result = {
        "rows": count,
        "all_records_equal_except_cohort_index": True,
        "source_summaries_sha256": [sha(args.sequential), sha(args.merged)],
        "runner_sha256": sha(Path(__file__)),
        "strict_envelope_failures": left["counts"][
            "probe_envelopes_not_covering_safe_source_witnesses"
        ],
        "strict_envelope_gate_passed": left["counts"][
            "probe_envelopes_not_covering_safe_source_witnesses"
        ]
        == 0,
        "full_goal_complete": False,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
