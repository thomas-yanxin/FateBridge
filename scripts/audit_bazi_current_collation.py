"""Replay frozen predictions against historical and corrected source labels.

The corrections and their results are already exposed development evidence.
This audit does not create new cases, tune an operator or adopt a candidate.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_current_collation_v1"
DEVELOPMENT = (
    "tests/fixtures/bazi_stem_transformation_v2/development-local-conversion.json"
)
ERRATA = "tests/fixtures/bazi_classical_corrections_v2/errata.json"
FIRST = "docs/validation/bazi-stem-effects-first-v2.json"
METHODS = ("production_v6", "candidate_v1", "candidate_v2")
HISTORICAL_INPUTS = {
    "src/fatebridge/core/strength.py": ROOT
    / "tests/fixtures/bazi_topic_knowledge_v2/before/src/fatebridge/core/strength.py",
    "src/fatebridge/core/stem_effects.py": ROOT
    / "tests/fixtures/bazi_stem_transformation_v2/dependencies/src__fatebridge__core__stem_effects.py.txt",
    "src/fatebridge/core/classical_roots.py": ROOT
    / "tests/fixtures/bazi_stem_transformation_v2/dependencies/src__fatebridge__core__classical_roots.py.txt",
    "uv.lock": ROOT
    / "tests/fixtures/bazi_root_force_experiment_v4/dependencies/uv.lock",
}
HISTORICAL_RUNNER_SHA256 = (
    "c2b35b2ee99696e8a8cc7e3fede922f600ecc65e74e88dfb589dd6bf19e6947e"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text())
    if not isinstance(result, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return result


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    path = FIXTURE / "protocol.json"
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Collation protocol changed")
    protocol = read_object(path)
    if digest(FIXTURE / "first-runner.py.txt") != HISTORICAL_RUNNER_SHA256:
        raise ValueError("Original collation runner changed")
    for name, expected in protocol["input_sha256"].items():
        if digest(HISTORICAL_INPUTS.get(name, ROOT / name)) != expected:
            raise ValueError("Collation input changed: " + name)
    errata = read_object(ROOT / ERRATA)
    if errata["original_development_labels"] != DEVELOPMENT:
        raise ValueError("Correction addresses another reference")
    if errata["original_development_labels_sha256"] != digest(ROOT / DEVELOPMENT):
        raise ValueError("Wrong original development reference")
    if errata["original_first_result"] != FIRST:
        raise ValueError("Correction addresses another first report")
    if errata["original_first_result_sha256"] != digest(ROOT / FIRST):
        raise ValueError("Wrong original first result")
    if errata["source_pdf_sha256"] != protocol["primary_source_sha256"]:
        raise ValueError("Correction comes from another edition")
    return protocol, read_object(ROOT / DEVELOPMENT), errata


def corrected_reference(
    development: dict[str, Any], errata: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Apply declared corrections only after checking the exact old values."""
    original = development["exposed_source_labels"]
    current = {row["id"]: deepcopy(row) for row in original}
    if len(current) != len(original):
        raise ValueError("Duplicate reference case")
    touched = set()
    for correction in errata["corrections"]:
        case_id = correction["case_id"]
        key = (case_id, correction["field"])
        if key in touched:
            raise ValueError("Duplicate correction")
        touched.add(key)
        if case_id not in current:
            raise ValueError("Unknown correction case")
        field = {
            "local_conversion.expected_converted": "expected_converted",
            "source_anchor": "source_anchor",
        }.get(correction["field"])
        if field is None:
            raise ValueError("Unsupported correction field")
        row = current[case_id]
        old, new = correction["original_value"], correction["corrected_value"]
        if type(row[field]) is not type(old) or row[field] != old:
            raise ValueError("Original correction value no longer matches")
        if type(new) is not type(old) or new == old:
            raise ValueError("Correction has wrong type or no change")
        if correction["pdf_page"] != row["pdf_page"]:
            raise ValueError("Correction addresses another source page")
        row[field] = new
        if field == "expected_converted":
            # The final paragraph replaces the isolated hypothetical clause.
            row["source_anchor"] = correction["source_anchor"]
    if not touched:
        raise ValueError("No source corrections supplied")
    return current


def collate_groups(
    groups: dict[str, Any],
    development: dict[str, Any],
    errata: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    original = {r["id"]: r for r in development["exposed_source_labels"]}
    corrected = corrected_reference(development, errata)
    changed = {key for key in corrected if corrected[key] != original[key]}
    current = deepcopy(groups)
    deltas = []
    seen = set()
    for group, rows in current.items():
        for row in rows:
            case_id = row["id"]
            if case_id not in changed:
                continue
            pair = original[case_id]["positions"]
            claims = [
                p for p in row["source_checks"] if p["reference"]["positions"] == pair
            ]
            if len(claims) != 1 or claims[0]["reference"] != original[case_id]:
                raise ValueError("Historical pair reference changed: " + case_id)
            for correction in errata["corrections"]:
                if correction["case_id"] == case_id and "pillars" in correction:
                    if correction["pillars"] != row["pillars"]:
                        raise ValueError("Correction addresses another literal chart")
            seen.add(case_id)
            claim = claims[0]
            before = deepcopy(claim)
            claim["reference"] = deepcopy(corrected[case_id])
            expected = claim["reference"]["expected_converted"]
            for observation in claim["observations"].values():
                actual = observation["converted"]
                if observation["applicable"] and type(actual) is not bool:
                    raise ValueError("Applicable pair lacks an actual boolean")
                observation["matches"] = (
                    actual == expected
                    if observation["applicable"] and expected is not None
                    else None
                )
            deltas.append(
                {
                    "group": group,
                    "id": case_id,
                    "pillars": row["pillars"],
                    "historical_check": before,
                    "current_check": deepcopy(claim),
                }
            )
    if seen != changed:
        raise ValueError("Not every declared correction was applied")
    return current, deltas


def summarize(groups: dict[str, Any]) -> dict[str, Any]:
    """Count records and distinct physical pairs separately, including unknowns."""
    rows = [r for group in groups.values() for r in group]
    unique: dict[tuple[tuple[str, ...], tuple[str, ...]], dict[str, Any]] = {}
    occurrences = 0
    for row in rows:
        for pair in row["source_checks"]:
            occurrences += 1
            key = (tuple(row["pillars"]), tuple(pair["reference"]["positions"]))
            if key in unique:
                previous = unique[key]
                if (
                    previous["reference"]["expected_converted"]
                    != pair["reference"]["expected_converted"]
                    or previous["observations"] != pair["observations"]
                ):
                    raise ValueError("Conflicting references for one physical pair")
            else:
                unique[key] = pair
    known = [
        p for p in unique.values() if p["reference"]["expected_converted"] is not None
    ]
    return {
        "groups": len(groups),
        "records": len(rows),
        "distinct_literal_charts": len({tuple(r["pillars"]) for r in rows}),
        "strength_known_records": sum(r["expected_strength"] is not None for r in rows),
        "strength_unknown_records": sum(r["expected_strength"] is None for r in rows),
        "pair_occurrences": occurrences,
        "distinct_pairs": len(unique),
        "distinct_known_pairs": len(known),
        "distinct_unknown_pairs": len(unique) - len(known),
        "methods": {
            name: {
                "matching": sum(
                    p["observations"][name]["matches"] is True for p in known
                ),
                "mismatching": sum(
                    p["observations"][name]["matches"] is False for p in known
                ),
                "unsupported": sum(
                    not p["observations"][name]["applicable"] for p in known
                ),
            }
            for name in METHODS
        },
    }


def audit() -> dict[str, Any]:
    protocol, development, errata = load_inputs()
    with tempfile.TemporaryDirectory(prefix="bazi-current-collation-") as folder:
        path = Path(folder) / "historical-replay.json"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/audit_bazi_stem_effects_v2.py"),
                "--output",
                str(path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError("Frozen historical replay failed: " + result.stderr)
        historical = read_object(path)
    first = read_object(ROOT / FIRST)
    for key in (
        "groups",
        "summaries",
        "adoption_gates",
        "protocol_sha256",
        "reference_sha256",
    ):
        if historical[key] != first[key]:
            raise ValueError("Historical reproduction drifted: " + key)
    current, deltas = collate_groups(historical["groups"], development, errata)
    before, after = summarize(historical["groups"]), summarize(current)
    for name, expected in protocol["input_sha256"].items():
        if digest(HISTORICAL_INPUTS.get(name, ROOT / name)) != expected:
            raise ValueError("Input changed during collation: " + name)
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "input_sha256": protocol["input_sha256"],
        "runner_sha256": digest(Path(__file__)),
        "historical_runner_sha256": HISTORICAL_RUNNER_SHA256,
        "source_state": "post_comparison_current_labels",
        "historical_first_result": FIRST,
        "historical_full_replay_matches_first": True,
        "historical_groups": historical["groups"],
        "historical_summary": before,
        "historical_adoption_gates": historical["adoption_gates"],
        "current_groups": current,
        "current_summary": after,
        "label_and_anchor_deltas": deltas,
        "current_explicit_development_references": corrected_reference(
            development, errata
        ),
        "default_changed": False,
        "adopted": False,
        "new_independent_cases": 0,
        "operator_gain": False,
        "classical_acceptance_passed": False,
        "full_goal_complete": False,
        "overall_score": None,
        "scope": "Complete historical predictions replayed without numerical changes. Final paragraph corrections update current expected conversion and anchors, never original freezes, unknowns or predictions. Duplicate group copies are deduplicated by literal chart and physical pair. This is exposed source-truth maintenance, not new accuracy or classical acceptance.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(".sha256").exists():
        parser.error("Existing outputs are reserved; never overwrite a first result")
    report = audit()
    encoded = json.dumps(report, ensure_ascii=False, indent=2).encode()
    with args.output.open("xb") as stream:
        stream.write(gzip.compress(encoded, mtime=0))
    with args.output.with_suffix(".sha256").open("x") as stream:
        stream.write(digest(args.output) + "\n")
    print(
        json.dumps(
            {
                "historical": report["historical_summary"],
                "current": report["current_summary"],
                "adopted": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
