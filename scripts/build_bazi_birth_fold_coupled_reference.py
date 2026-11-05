"""Freeze all fold probes whose existing solar-term reference states differ.

Only archived IANA transition arithmetic and already frozen DE440/clock-policy
roots label the cohort. This is coupled software verification, not a new
independent astronomical observation or a classical/reality label.
"""

import bisect
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/bazi_birth_fold_v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = FIXTURE / "coupled-reference.json"
    assert not output.exists(), "Keep the first frozen labels"
    clock_path = FIXTURE / "reference.json.gz"
    root_path = ROOT / "tests/data/bazi_boundary_decisions_v1/probes.json"
    clocks = json.loads(gzip.decompress(clock_path.read_bytes()))
    roots = sorted(
        [
            r
            for r in json.loads(root_path.read_text())["rows"]
            if r["side"] == "next_minute"
        ],
        key=lambda r: r["reference_civil_under_frozen_policy"],
    )
    epochs = [
        datetime.fromisoformat(r["reference_civil_under_frozen_policy"]).timestamp()
        for r in roots
    ]

    def label(row):
        results = []
        for expected in row["expected"]:
            instant = datetime.fromisoformat(expected["utc"])
            index = bisect.bisect_right(epochs, instant.timestamp()) - 1
            assert index >= 0 and index + 1 < len(roots)
            results.append(
                {
                    **expected,
                    "term_state": roots[index]["reference_state_under_frozen_policy"],
                }
            )
        return {**row, "expected": results}

    folds = [r for r in clocks["rows"] if r["kind"] == "fold"]
    crossing = []
    for row in folds:
        annotated = label(row)
        if (
            annotated["expected"][0]["term_state"]
            != annotated["expected"][1]["term_state"]
        ):
            crossing.append(annotated)
    # Three fixed points per event were already declared. Include one midpoint
    # for every source shift magnitude, with stable lexicographic tie-breaking.
    magnitudes = {}
    for row in sorted(folds, key=lambda r: r["id"]):
        start, end = row["birth_range_clipped_wall_interval_seconds"]
        wall_epoch = int(
            datetime.fromisoformat(row["wall"]).replace(tzinfo=timezone.utc).timestamp()
        )
        if wall_epoch == (start + end - 1) // 2:
            magnitudes.setdefault(row["shift_seconds"], label(row))
    jie_names = {
        "小寒",
        "立春",
        "惊蛰",
        "清明",
        "立夏",
        "芒种",
        "小暑",
        "立秋",
        "白露",
        "寒露",
        "立冬",
        "大雪",
    }
    result = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "clock_reference_sha256": digest(clock_path),
        "term_reference_sha256": digest(root_path),
        "selection": "All frozen fold points whose last/next term or BaZi year/month state differs; plus the first lexicographic midpoint for every fold magnitude. No candidate code used.",
        "crossing_count": len(crossing),
        "crossing_zones": len({r["zone"] for r in crossing}),
        "crossing_events": len({(r["zone"], r["transition_epoch"]) for r in crossing}),
        "crossing_rows": crossing,
        "magnitude_count": len(magnitudes),
        "magnitude_rows": [magnitudes[k] for k in sorted(magnitudes)],
        "dayun_reference_jie": [
            {"name": r["name"], "civil_utc": r["reference_civil_under_frozen_policy"]}
            for r in roots
            if r["name"] in jie_names
        ],
        "elapsed_seconds_absolute_tolerance": 0.1,
        "dayun_policy": "Existing gender/year-stem direction; physical birth-to-jie UTC elapsed seconds; age=seconds/(86400*3). Both genders, both folds. Timeline retains the IANA zone, not the selected fixed birth offset.",
        "cache_gate": "Compare year/month and last/next terms in both fold visitation orders; raw day/hour must agree for the same wall label. True-solar clocks checked separately by same-instant controls.",
        "named_controls": [
            "Havana HKO 2021-11-07T00:30:00 -04:00/-05:00",
            "Shanghai 1991-09-15T01:30:00 +09:00/+08:00",
            "New York 2015-11-01T01:30:00 -04:00/-05:00",
            "Lord Howe 2020-04-05T01:45:00 +11:00/+10:30",
        ],
        "limits": "Term clock policy and astronomical frame are shared with prior references; aliases and repeated probes are dependent. Future transitions are conditional on tzdb 2026e, not observations. No new classical, model, expert or real prediction evidence.",
        "new_independent_observation_credit": 0,
        "full_goal_complete": False,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    output.with_suffix(".sha256").write_text(digest(output) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if not isinstance(v, list)},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
