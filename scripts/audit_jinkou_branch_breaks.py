"""Audit source-listed pairs without inferring break effects or changing old facts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_branch_breaks_scan_v2"
PIN = "bcd40cb10c075024f6d67c3b7c34facf6990a95a185a289a953e287d6d070ad7"
INITIAL_CORPUS = ROOT / "tests/fixtures/jinkou_branch_breaks_v1"
INITIAL_PIN = "d6ae103425f0881e6ad176ba1e1cb902dc4f752cf0137b0efc1e15f855a6a43b"
BASELINE_PIN = "2648a98b88ea9305795d54e1d78a454305ebd4003d02a9c31047485e99a8ffa2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if sha(INITIAL_CORPUS / "freeze.json") != INITIAL_PIN:
        raise ValueError("Initial incomplete reading identity changed")
    initial = json.loads((INITIAL_CORPUS / "freeze.json").read_text())
    for name, digest in initial["files"].items():
        if sha(INITIAL_CORPUS / name) != digest:
            raise ValueError("Initial incomplete reading bytes changed")
    if sha(corpus / "freeze.json") != PIN:
        raise ValueError("Frozen printed-break reference identity changed")
    manifest = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(manifest["files"]) | {"freeze.json"}:
        raise ValueError("Frozen printed-break reference inventory changed")
    for name, expected in manifest["files"].items():
        if sha(corpus / name) != expected:
            raise ValueError("Frozen printed-break reference changed: " + name)
    readings = json.loads((corpus / "readings.json").read_text())
    if (
        sha(ROOT / "tests/fixtures/jinkou_month_building_v1/source.pdf")
        != readings["source_sha256"]
    ):
        raise ValueError("Printed-break original PDF identity changed")
    return dict(
        readings=readings,
        reference=json.loads((corpus / "reference.json").read_text()),
    )


def audit() -> dict[str, Any]:
    data = reference()
    files = sorted((ROOT / "src").rglob("*.py")) + [
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
        Path(__file__),
    ]
    before = {str(p.relative_to(ROOT)): sha(p) for p in files}
    from fatebridge.core.metaphysics.jinkou_branch_breaks import (
        branch_breaks,
        pair_facts,
    )
    from fatebridge.core.output_jinkou_breaks import JinkouBranchBreaks

    matrix = []
    for expected in data["reference"]["pair_matrix"]:
        actual = pair_facts(expected["left_branch"], expected["right_branch"])
        matrix.append(
            dict(expected=expected, actual=actual, matched=actual == expected)
        )
    failures, count = [], 0
    source = data["readings"]
    expected_source = dict(
        source_url=source["source_url"],
        source_sha256=source["source_sha256"],
        original_pdf_page=source["pair_page"],
        written_pairs=[list(p) for p in source["written_pairs"]],
        transcription_url=source["transcription_url"],
        transcription_written_pairs=[
            list(p) for p in source["transcription_written_pairs"]
        ],
        scan_extra_pairs=[list(p) for p in source["scan_extra_pairs"]],
        extra_pair_author_intent=None,
        effective_break=None,
        effect_direction=None,
        complete_classical_conformance=False,
    )
    row_mismatches, metadata_mismatches = 0, 0
    for case in data["reference"]["contexts"]:
        actual = branch_breaks(*case["branches"])
        JinkouBranchBreaks.model_validate(actual)
        row_matches = actual["rows"] == case["rows"]
        metadata_matches = not any(
            type(actual.get(k)) is not type(v) or actual.get(k) != v
            for k, v in expected_source.items()
        )
        row_mismatches += not row_matches
        metadata_mismatches += not metadata_matches
        if not row_matches or not metadata_matches:
            failures.append(
                dict(
                    expected=case,
                    actual=actual,
                    row_matches=row_matches,
                    metadata_matches=metadata_matches,
                )
            )
        count += 1
    from scripts.audit_jinkou_strength import audit as strength_audit

    original = strength_audit()
    if before != {str(p.relative_to(ROOT)): sha(p) for p in files}:
        raise ValueError("Source changed during printed-break audit")
    passed = all(r["matched"] for r in matrix) and count == 1728 and not failures
    return dict(
        reference_pin=PIN,
        source=data["readings"],
        initial_incomplete_reading=dict(
            reference_pin=INITIAL_PIN,
            coverage_claim_invalidated=True,
            omitted_printed_pair=["寅", "巳"],
            original_six_pair_files_preserved=True,
        ),
        independent_source_metadata=expected_source,
        matrix=matrix,
        matrix_count=len(matrix),
        matrix_match_count=sum(r["matched"] for r in matrix),
        triple_count=count,
        row_mismatch_count=row_mismatches,
        metadata_mismatch_count=metadata_mismatches,
        position_comparison_count=count * 3,
        failures=failures,
        finite_pair_facts_passed=passed,
        original_scan={
            k: original[k]
            for k in [
                "scan_case_count",
                "scan_matched_count",
                "scan_failures",
                "older_online_matched_count",
            ]
        },
        implementation_sha256=before,
        implementation_unchanged=True,
        reciprocal_effects_adjudicated=False,
        effective_break_adjudicated=False,
        comprehensive_use_adjudicated=False,
        classical_acceptance_passed=False,
        new_independent_real_events=0,
        new_model_processes=0,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-full-conformance", action="store_true")
    options = parser.parse_args()
    result = audit()
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if options.output:
        with options.output.open("x") as stream:
            stream.write(content)
    else:
        print(content, end="")
    passed = result["finite_pair_facts_passed"] and result["legacy"].get("passed", True)
    return 0 if passed and not options.require_full_conformance else 1


if __name__ == "__main__":
    raise SystemExit(main())
