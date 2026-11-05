"""Audit source inputs before attributing count disagreements to arithmetic."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.taiyi_source_alignment import count_source_assessment
from fatebridge.core.metaphysics.taiyi_year import cyclic_core

if TYPE_CHECKING:
    from scripts.taiyi.build_taiyi_source_alignment import CORPUS, source_data
from scripts.taiyi.build_taiyi_source_alignment import CORPUS, source_data


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    data = source_data(corpus)
    probes = json.loads((corpus / "arithmetic-probes.json").read_text())
    observed = [
        count_source_assessment(cyclic_core(row["ju"], yin=row["yin"]))
        for row in data["rows"]
    ]
    by_id = {r["case_id"]: r for r in observed}
    probe_checks = []
    for probe in probes:
        count = next(
            r for r in by_id[probe["id"]]["counts"] if r["camp"] == probe["camp"]
        )
        got = count["source_position_recount"]
        probe_checks.append(
            {
                **probe,
                "actual_sum": got["count"],
                "actual_terms": [p["value"] for p in got["path"]],
                "matches": got["count"] == probe["manual_sum"]
                and [p["value"] for p in got["path"]] == probe["manual_terms"],
            }
        )
    positions = [
        {**p, "case_id": row["case_id"]} for row in observed for p in row["positions"]
    ]
    counts = [
        {**p, "case_id": row["case_id"]} for row in observed for p in row["counts"]
    ]
    return {
        "completion_claim": False,
        "source_rows": len(observed),
        "required_position_observations": len(positions),
        "matching_position_observations": sum(p["matches"] for p in positions),
        "position_disagreements": [p for p in positions if not p["matches"]],
        "prior_count_observations": len(counts),
        "matching_prior_count_observations": sum(c["count_matches"] for c in counts),
        "prior_count_disagreements": [c for c in counts if not c["count_matches"]],
        "source_position_recounts": len(counts),
        "matching_source_position_recounts": sum(
            c["source_recount_matches_table"] for c in counts
        ),
        "source_position_recount_disagreements": [
            c for c in counts if not c["source_recount_matches_table"]
        ],
        "diagnosis_counts": dict(Counter(c["diagnosis"] for c in counts)),
        "manual_probe_checks": probe_checks,
        "manual_probe_checks_match": all(r["matches"] for r in probe_checks),
        "facsimile_transcription_corrections": [
            c
            for row in observed
            for c in row["facsimile_readings"]
            if c["status"] == "transcription_differs_from_facsimile"
        ],
        "initial_manual_literal_corrections": [
            {"id": row["id"], "differences": row["initial_manual_literal_differences"]}
            for row in data["rows"]
            if row["initial_manual_literal_differences"]
        ],
        "initial_manual_entry_semantic_errors": [
            c
            for row in observed
            for c in row["facsimile_readings"]
            if c["status"] == "initial_manual_entry_differs_from_source_and_facsimile"
        ],
        "required_count_and_position_values_removed": False,
        "count_policy": "576位置、原288两算、288源位置重算与12手写加数检查分别计数；12为旧行算路检查，不是新增历史课例。不得合并为准确率。",
        "selected_source_cyclic_rows": observed,
        "whole_book_conformance": "not_established",
        "full_ancient_calendar_reconstructed": False,
        "classical_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw)
    else:
        print(raw, end="")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
