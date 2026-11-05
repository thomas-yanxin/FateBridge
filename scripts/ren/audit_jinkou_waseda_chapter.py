"""Keep the complete visible heading inventory distinct from 64 clean cases."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_waseda_chapter_v1"
PIN = "bed79fa873f4f806a7dc4d0dc6c290fc54012e5ac92bfc3b364adad4f3417d05"
WATCH = (
    "src/fatebridge/core/metaphysics/jinkou_definitions.py",
    "src/fatebridge/core/output_jinkou_definitions.py",
    "src/fatebridge/core/output_ren_anchors.py",
    "src/fatebridge/data/jinkou_waseda_chapter.json",
    "scripts/ren/audit_jinkou_definitions.py",
    "scripts/ren/audit_jinkou_waseda_chapter.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if sha(corpus / "freeze.json") != PIN:
        raise ValueError("Frozen chapter protocol changed")
    freeze = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(freeze["files"]) | {"freeze.json"}:
        raise ValueError("Frozen chapter inventory changed")
    if any(sha(corpus / n) != d for n, d in freeze["files"].items()):
        raise ValueError("Frozen chapter source or transcription changed")
    value: dict[str, Any] = json.loads((corpus / "inventory.json").read_text())
    return value


def audit() -> dict[str, Any]:
    ref = reference()
    before = {n: sha(ROOT / n) for n in WATCH}
    from fatebridge.core.metaphysics.jinkou_definitions import chapter_provenance
    from scripts.ren.audit_jinkou_definitions import audit as original_definition_audit
    from scripts.ren.audit_jinkou_patterns import audit as original_pattern_audit

    published = chapter_provenance()
    inventory = published["chapter_inventory"]
    counts = Counter(r["raw_heading"] for r in ref["entries"])
    checks = dict(
        full_pdf_hash=published["full_scan_sha256"]
        == sha(CORPUS / "waseda06.pdf")
        == ref["source_sha256"],
        full_pdf_url=published["full_scan_url"] == ref["full_scan_url"],
        raw_inventory_hash=inventory["raw_inventory_sha256"]
        == sha(CORPUS / "inventory.json"),
        source_pdf_pages=inventory["source_pdf_pages"] == ref["source_pdf_pages"],
        all_visible_headings_preserved=inventory["headings"] == ref["entries"],
        heading_count=inventory["observed_heading_occurrences"]
        == len(ref["entries"])
        == 53,
        unique_heading_count=inventory["unique_raw_headings"] == len(counts) == 52,
        duplicates_retained=inventory["duplicate_raw_headings"]
        == [name for name, count in counts.items() if count > 1]
        == ["鎖課"],
        observations_preserved=inventory["direct_observations"]
        == ref["direct_observations"],
        reviewed_pages=inventory["reviewed_pdf_pages"] == ref["reviewed_pdf_pages"],
        no_predicate_adjudication=inventory["classical_predicates_adjudicated"] == 0,
        no_full_book_claim=inventory["whole_volume_transcription_complete"] is False
        and inventory["full_classical_conformance"] is False,
    )
    old_definitions = original_definition_audit()
    old_patterns = original_pattern_audit()
    after = {n: sha(ROOT / n) for n in WATCH}
    return dict(
        audit_id="jinkou_waseda_chapter_v1",
        frozen_reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=after,
        implementation_unchanged_during_audit=before == after,
        source_checks=checks,
        observed_heading_occurrences=53,
        unique_raw_headings=52,
        selected_definition_transcriptions=ref["selected_definition_count"],
        selected_diagram_transcriptions=ref["selected_diagram_count"],
        source_pdf_pages=90,
        whole_volume_transcription_complete=False,
        single_reviewer=True,
        previous_outcomes_known_when_transcribing=True,
        independent_transmission_established=False,
        chronological_priority_established=False,
        original_definition_audit=old_definitions,
        original_classical_counts=dict(
            cases=old_patterns["corpus_case_count"],
            matched=old_patterns["matched_semantic_cases"],
            unresolved=old_patterns["unevaluated_definitions"],
            source_day_matched=old_patterns["matched_source_day_cases"],
        ),
        engineering_checks_passed=all(checks.values())
        and before == after
        and old_definitions["engineering_checks_passed"],
        original_classical_acceptance_passed=False,
        new_original_predicates_adjudicated=0,
        new_independent_historical_events=0,
        new_model_processes=0,
        real_world_validation="deferred_by_user",
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "observed_heading_occurrences",
                    "unique_raw_headings",
                    "engineering_checks_passed",
                    "goal_complete",
                ]
            }
        )
    )
    return 0 if result["engineering_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
