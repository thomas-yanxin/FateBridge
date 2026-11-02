"""Suggest physical-leaf correspondences; image distance never certifies text.

All leaves, gaps and alternatives remain visible. This script does not calculate
charts, change source readings, or freeze the classical collection.
"""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-source-leaf-alignment-v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def distances(left, right):
    """Euclidean distance on nonnegative unit vectors, scaled to [0,1]."""
    dimension = None
    vectors = []
    for side in [left, right]:
        converted = []
        for row in side:
            value = tuple(row["vector"])
            if dimension is None:
                dimension = len(value)
            if (
                not value
                or len(value) != dimension
                or any(
                    type(x) not in {float, int}
                    or not math.isfinite(x)
                    or x < 0
                    or x > 1
                    for x in value
                )
            ):
                raise ValueError("Invalid or inconsistent image descriptor")
            norm = math.fsum(x * x for x in value)
            if norm != 0 and not math.isclose(norm, 1, abs_tol=1e-8):
                raise ValueError("Image descriptor is neither blank nor unit length")
            converted.append(value)
        vectors.append(converted)
    return [[math.dist(a, b) / math.sqrt(2) for b in vectors[1]] for a in vectors[0]]


def align(costs, gap_cost, new_count=None):
    """Exact monotone edit-path optimum; ties prefer match, old-only, new-only."""
    if (
        type(gap_cost) not in {float, int}
        or not math.isfinite(gap_cost)
        or gap_cost <= 0
    ):
        raise ValueError("Gap cost must be finite and positive")
    n = len(costs)
    m = len(costs[0]) if n else (0 if new_count is None else new_count)
    if (
        type(m) is not int
        or m < 0
        or (new_count is not None and (type(new_count) is not int or new_count != m))
    ):
        raise ValueError("New leaf count disagrees with distance matrix")
    if any(len(row) != m for row in costs) or any(
        type(x) not in {float, int} or not math.isfinite(x) or x < 0 or x > 1
        for row in costs
        for x in row
    ):
        raise ValueError("Invalid, ragged or nonfinite distance matrix")
    steps = [bytearray(m + 1) for _ in range(n + 1)]
    previous = [j * gap_cost for j in range(m + 1)]
    for j in range(1, m + 1):
        steps[0][j] = 2
    for i in range(1, n + 1):
        current = [i * gap_cost] + [0.0] * m
        steps[i][0] = 1
        for j in range(1, m + 1):
            options = (
                previous[j - 1] + costs[i - 1][j - 1],
                previous[j] + gap_cost,
                current[j - 1] + gap_cost,
            )
            choice = min(range(3), key=options.__getitem__)
            steps[i][j], current[j] = choice, options[choice]
        previous = current
    i, j, rows = n, m, []
    while i or j:
        choice = steps[i][j]
        if choice == 0:
            rows.append(
                dict(
                    action="match",
                    original=i,
                    candidate=j,
                    image_distance=costs[i - 1][j - 1],
                    status="candidate_not_text_certified",
                )
            )
            i, j = i - 1, j - 1
        elif choice == 1:
            rows.append(
                dict(
                    action="original_only",
                    original=i,
                    candidate=None,
                    status="candidate_gap_requires_reading",
                )
            )
            i -= 1
        else:
            rows.append(
                dict(
                    action="candidate_only",
                    original=None,
                    candidate=j,
                    status="candidate_gap_requires_reading",
                )
            )
            j -= 1
    rows.reverse()
    if [r["original"] for r in rows if r["original"] is not None] != list(
        range(1, n + 1)
    ) or [r["candidate"] for r in rows if r["candidate"] is not None] != list(
        range(1, m + 1)
    ):
        raise AssertionError("Physical leaf inventory was omitted or reordered")
    return dict(
        gap_cost=gap_cost,
        total_layout_cost=previous[-1],
        rows=rows,
        semantic_equality_certified=False,
        all_original_leaves_retained=n,
        all_candidate_leaves_retained=m,
    )


def run(study=STUDY, root=ROOT):
    protocol = json.loads((study / "protocol-first.json").read_text())
    spec = json.loads((study / "feature-spec-before-first.json").read_text())
    receipt = json.loads((study / "feature-extraction-first.json").read_text())
    feature_file = study / "features-first.json.gz"
    if (
        sha(feature_file) != receipt["features_sha256"]
        or sha(study / "feature-spec-before-first.json")
        != receipt["feature_spec_sha256"]
    ):
        raise ValueError("Frozen feature or extraction spec changed")
    for side in ["old_source", "new_source"]:
        if sha(root / protocol[side]["path"]) != protocol[side]["sha256"]:
            raise ValueError("Original source byte binding changed")
    data = json.loads(gzip.decompress(feature_file.read_bytes()))
    for side, count in [("original", 516), ("candidate", 521)]:
        if [r["page"] for r in data[side]] != list(range(1, count + 1)):
            raise ValueError("Full physical leaf inventory changed")
        for row in data[side]:
            path = (root / row["path"]).resolve()
            if not path.is_relative_to(root.resolve()) or sha(path) != row["sha256"]:
                raise ValueError("Rendered leaf escaped root or lost image binding")
    costs = distances(data["original"], data["candidate"])
    paths = [align(costs, gap, new_count=521) for gap in spec["gap_cost_profiles"]]
    alternatives = [
        dict(
            original=i + 1,
            candidates=[
                dict(candidate=j + 1, image_distance=costs[i][j])
                for j in sorted(range(521), key=lambda j: (costs[i][j], j))[:3]
            ],
        )
        for i in range(516)
    ]
    anchors = json.loads((study / "known-anchor-pairs-before-first.json").read_text())
    diagnostic = [
        dict(
            anchor,
            known_pair_distance=costs[anchor["original"] - 1][anchor["candidate"] - 1],
            nearest_candidates=alternatives[anchor["original"] - 1]["candidates"],
            known_anchor_not_blind_validation=True,
        )
        for anchor in anchors
    ]
    return dict(
        protocol_sha256=sha(study / "protocol-first.json"),
        feature_spec_sha256=sha(study / "feature-spec-before-first.json"),
        feature_file_sha256=sha(feature_file),
        runner_sha256=sha(Path(__file__)),
        original_pages=516,
        candidate_leaves=521,
        paths=paths,
        alternatives=alternatives,
        exposed_anchor_diagnostics=diagnostic,
        all_rows_are_candidates=True,
        source_cases_modified=0,
        source_grades_modified=0,
        source_book_text_completeness_certified=False,
        independent_annotation_review=False,
        full_goal_complete=False,
        original_gates_superseded=False,
        new_model_executions=0,
        overall_score=None,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", type=Path, default=STUDY)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError("Refuse to overwrite an earlier alignment attempt")
    result = run(args.study)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
