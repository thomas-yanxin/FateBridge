"""Literal source questions remain unresolved; no software result is an oracle."""

import hashlib
import json
from pathlib import Path

DATA = Path(__file__).parent / "data/bazi"


def test_current_primary_source_collation_preserves_unknowns_and_questions():
    source = json.loads((DATA / "ditian-source-census.json").read_text())
    assert (
        hashlib.sha256((DATA / "primary/ditian-1947.pdf").read_bytes()).hexdigest()
        == source["source_pdf_sha256"]
    )
    cases, claims = source["resolved_source_cases"], source["resolved_source_claims"]
    assert len(cases) == len({row["case_id"] for row in cases}) == 558
    assert len(claims) == len({row["claim_id"] for row in claims.values()}) == 1380
    assert sum(row["expected_daymaster_strength"] is None for row in cases) == 532
    assert len(source["remaining_case_input_questions"]) == 3
    assert len(source["remaining_transcription_warnings"]) == 22
    assert source["all_physical_pages_scanned"] is True
    assert source["whole_book_collection_frozen"] is False
    assert source["candidate_evaluation_allowed"] is False
    assert source["independent_annotation_review"] == "not_certified"
    assert source["semantic_annotation_correctness"] == "not_certified"
