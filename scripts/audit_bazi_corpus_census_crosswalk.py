"""Cross-reference source annotations without grading or running predictions."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-corpus-census-crosswalk-v1"
PROTOCOL = "0739bc5c99b0c4e5113e450a2de4a8bc0161dd207de8601274c57e6586b2a16c"
LI1947 = "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803"
ZIPING = "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620"
ORDER = ("year", "month", "day", "hour")
GRADES = {"强", "中和", "弱"}
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def source_pages(record: dict[str, Any]) -> list[int]:
    """Only explicit PDF locators, never printed pages or nearby chart guesses."""
    pages = []
    for container in (record, record.get("source", {})):
        if not isinstance(container, dict):
            continue
        for key in ("pdf_page", "source_pdf_page", "pdf_pages", "source_pdf_pages"):
            raw = container.get(key, [])
            raw = raw if isinstance(raw, list) else [raw]
            if any(type(p) is not int or p < 1 for p in raw):
                raise ValueError("Malformed explicit source PDF locator")
            pages.extend(raw)
    return sorted(set(pages))


def source_identity(document: Any) -> dict[str, Any]:
    """Direct book metadata only; overlapping studies are not book provenance."""
    hashes = []
    if isinstance(document, dict):
        for container in (document, document.get("source", {})):
            if isinstance(container, dict):
                for key in ("source_sha256", "source_pdf_sha256", "full_pdf_sha256"):
                    if key in container:
                        hashes.append(container[key])
    known = set(hashes) & {LI1947, ZIPING}
    return {
        "direct_source_hashes": hashes,
        "book_status": (
            "conflicting_book_metadata"
            if len(known) > 1
            else (
                "same_li1947_book_hash"
                if LI1947 in known
                else (
                    "different_ziping_book_hash"
                    if ZIPING in known
                    else "book_identity_not_confirmed"
                )
            )
        ),
    }


def compare_annotations(old: str | None, case: dict[str, Any]) -> str:
    new = case["expected_daymaster_strength"]
    forbidden = case["forbidden_daymaster_strengths"]
    if old not in GRADES | {None} or new not in GRADES | {None}:
        raise ValueError("Invalid source strength label")
    if not isinstance(forbidden, list) or any(v not in GRADES for v in forbidden):
        raise ValueError("Invalid source forbidden grade")
    if new in forbidden:
        raise ValueError("Census annotation is internally contradictory")
    if old is not None and old in forbidden:
        return "old_exact_excluded_by_census_bound_review_required"
    if old is not None and new is not None:
        return (
            "same_exact_annotation"
            if old == new
            else "different_exact_annotations_review_required"
        )
    if old is not None:
        return "old_exact_census_no_exact_annotation_review_required"
    if new is not None:
        return "old_unknown_census_exact_no_label_transfer"
    return "neither_has_exact_annotation"


def crosswalk_row(
    row: dict[str, Any], identity: dict[str, Any], cases: list[dict[str, Any]]
) -> dict[str, Any]:
    """Do not inspect assessment, actual_strength or matches, even if supplied."""
    values = row["pillars"]
    if len(values) != 4 or any(
        not isinstance(p, str)
        or len(p) != 2
        or p[0] not in STEMS
        or p[1] not in BRANCHES
        for p in values
    ):
        raise ValueError("Expected four complete literal pillars")
    if row["expected_strength"] not in GRADES | {None}:
        raise ValueError("Invalid old source strength label")
    pages = source_pages(row["source_record"])
    candidates = []
    for case in cases:
        if [case["literal_pillars"][p] for p in ORDER] != values:
            continue
        overlap = sorted(set(pages) & set(case["crosswalk_source_pages"]))
        candidates.append(
            {
                "census_case_id": case["case_id"],
                "census_source_pages": case["crosswalk_source_pages"],
                "intersecting_pdf_pages": overlap,
                "confirmed_same_book_and_page": identity["book_status"]
                == "same_li1947_book_hash"
                and bool(overlap),
                "annotation_comparison": compare_annotations(
                    row["expected_strength"], case
                ),
                "census_source_layer": case["source_text_layer"],
                "census_speaker_chain": case["speaker_chain"],
                "census_exact_strength": case["expected_daymaster_strength"],
                "census_forbidden_strengths": case["forbidden_daymaster_strengths"],
                "census_claim_ids": case["claim_ids"],
                "census_case_object_sha256": object_digest(case),
            }
        )
    confirmed = [c for c in candidates if c["confirmed_same_book_and_page"]]
    status = (
        "different_book_no_source_identity_join"
        if identity["book_status"] == "different_ziping_book_hash"
        else (
            "book_identity_not_confirmed"
            if identity["book_status"] != "same_li1947_book_hash"
            else (
                "confirmed_unique_book_page_literal_candidate"
                if len(confirmed) == 1
                else (
                    "multiple_book_page_literal_candidates_review_required"
                    if len(confirmed) > 1
                    else (
                        "no_exact_literal_candidate"
                        if not candidates
                        else (
                            "case_pdf_pages_not_supplied"
                            if not pages
                            else "literal_candidates_outside_case_pdf_pages_review_required"
                        )
                    )
                )
            )
        )
    )
    return {
        "group": row["group"],
        "id": row["id"],
        "pillars": values,
        "old_expected_strength": row["expected_strength"],
        "old_label_status": row["label_status"],
        "old_source_record": row["source_record"],
        "old_explicit_pdf_pages": pages,
        "source_identity": identity,
        "join_status": status,
        "literal_candidates": candidates,
        "confirmed_candidate_count": len(confirmed),
        "annotation_review": (
            confirmed[0]["annotation_comparison"]
            if len(confirmed) == 1
            else "identity_not_unique_or_confirmed"
        ),
        "source_identity_independently_certified": False,
        "source_label_adjudicated_or_changed": False,
    }


def audit(root: Path, study: Path) -> dict[str, Any]:
    protocol_path = study / "protocol-first.json"
    if digest(protocol_path) != PROTOCOL:
        raise ValueError("Crosswalk protocol changed")
    protocol = json.loads(protocol_path.read_text())

    def guard() -> None:
        for rel, expected in protocol["inputs"].items():
            # The ledger is archived protection evidence, not a join input.
            # An explicitly allowed append must retain its historical binding.
            path = (
                study / "requirements-before-first.json"
                if rel == "docs/validation/bazi-three-axis-requirements.json"
                else root / rel
            )
            if digest(path) != expected:
                raise ValueError("Crosswalk protected input changed: " + rel)
        if (
            digest(study / "census-before-first.json")
            != protocol["census_snapshot_sha256"]
        ):
            raise ValueError("Census input changed")

    guard()
    corpus = json.loads(
        gzip.decompress(
            (
                root
                / "docs/validation/bazi-source-bounds-v1/corpus-frozen-first.json.gz"
            ).read_bytes()
        )
    )
    old26 = json.loads(
        gzip.decompress(
            (
                root / "docs/validation/bazi-month-duty-scan-source-corpus-v1.json.gz"
            ).read_bytes()
        )
    )
    census = json.loads((study / "census-before-first.json").read_text())
    registry = json.loads(
        (root / "tests/fixtures/bazi_source_corpus_v8/registry.json").read_text()
    )
    cases = json.loads(json.dumps(census["resolved_source_cases"]))
    origins: dict[str, set[int]] = defaultdict(set)
    for name in census["batches_sha256"]:
        batch_path = root / "docs/validation/bazi-ditian-wholebook-census-v1" / name
        if digest(batch_path) != census["batches_sha256"][name]:
            raise ValueError("Census origin batch changed")
        for page in json.loads(batch_path.read_text())["pages"]:
            for case in page["literal_cases"]:
                origins[case["case_id"]].add(page["pdf_page"])
    for case in cases:
        case["crosswalk_source_pages"] = sorted(
            origins[case["case_id"]]
            | set(case.get("source_metadata", {}).get("source_pages", []))
        )
    rows = []
    for group, data in corpus["groups"].items():
        document = json.loads((root / registry["groups"][group]).read_text())
        identity = source_identity(document)
        for row in data["rows"]:
            rows.append(crosswalk_row(row, identity, cases))
    lookup = {(r["group"], r["id"]): r for r in rows}
    if len(rows) != 367 or len(lookup) != 367 or len(cases) != 558:
        raise ValueError("Source scope changed")
    original26 = []
    for old in old26["all_distinct_disagreements"]:
        linked = []
        for obs in old["source_observations"]:
            match = lookup[(obs["group"], obs["id"])]
            if match["pillars"] != old["pillars"]:
                raise ValueError("Original disagreement input changed")
            linked.append(
                {
                    "group": match["group"],
                    "id": match["id"],
                    "join_status": match["join_status"],
                    "annotation_review": match["annotation_review"],
                }
            )
        original26.append(
            {
                "original_object": old,
                "linked_rows": linked,
                "original_failed_result_not_regraded": True,
            }
        )
    guard()
    return {
        "scope": "Source provenance and annotation comparison only; neither annotation set is adopted as a new answer key.",
        "protocol_sha256": PROTOCOL,
        "all_old_records_retained": len(rows),
        "all_census_cases_retained": len(cases),
        "rows": rows,
        "census_cases_with_origin_pages": cases,
        "census_source_claims": census["resolved_source_claims"],
        "original26_disagreements": original26,
        "join_status_counts": dict(Counter(r["join_status"] for r in rows)),
        "annotation_review_counts": dict(Counter(r["annotation_review"] for r in rows)),
        "all_source_record_objects_retained": True,
        "model_predictions_used_for_join_or_annotation_comparison": False,
        "force_calculations_executed": 0,
        "new_model_executions": 0,
        "original_source_labels_changed": False,
        "new_labels_adopted": False,
        "original26_gate_closed": False,
        "original40219_or41_regraded": False,
        "original5_regraded": False,
        "original_gates_superseded": False,
        "independent_expert_review": False,
        "full_goal_complete": False,
        "overall_score": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to overwrite crosswalk evidence")
    result = audit(ROOT, STUDY)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(digest(args.output) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in {
                    "rows",
                    "census_cases_with_origin_pages",
                    "census_source_claims",
                    "original26_disagreements",
                }
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
