"""Rewind two exact source-version receipts for comparisons of older facts.

The original snapshot is never rewritten. Both the complete new summary and
its matching rule-trace hash must equal frozen reviewed values. No primary
text, selected witness, calendar result or unknown field is removed.
"""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).parent / "fixtures/canping_gold_wenming_v1/compatibility"
RAW = (ROOT / "summary-version-pair.json").read_bytes()
assert (
    hashlib.sha256(RAW).hexdigest()
    == "788e794270f0eed5df3e3b390966abb9962fd985bde0b6c223c3e18205e04780"
)
REFERENCE = json.loads(RAW)
ADDITIONS_RAW = (ROOT / "selection-additions.json").read_bytes()
assert (
    hashlib.sha256(ADDITIONS_RAW).hexdigest()
    == "b764b36e82c975d3efcc5fb8f384b2cc04a8a3a82bbfefd2b45ee60fc68217b8"
)
ADDITIONS = json.loads(ADDITIONS_RAW)


def rewind_reviewed_witness_summary(current):
    output = deepcopy(current)
    evidence = output["numerology_evidence"]
    collation = evidence["canping_text_collation"]
    old, new = REFERENCE["old_summary"], REFERENCE["new_summary"]
    assert collation["comparison_witness"] == new
    traces = [
        row
        for row in evidence["rule_trace"]
        if row["rule_id"] == "canping_text_selection_v1"
    ]
    assert len(traces) == 1
    facts = traces[0]["facts"]
    assert facts["comparison_witness_id"] == old["corpus_id"] == new["corpus_id"]
    assert facts["comparison_witness_sha256"] == new["sha256"]
    collation["comparison_witness"] = deepcopy(old)
    facts["comparison_witness_sha256"] = old["sha256"]
    return output


def upgrade_frozen_witnesses(prior):
    """Add exactly reviewed source facts to a copy of an immutable old oracle.

    Existing numbers, text, calendar data, selected verse metadata and narrative
    remain intact. Per-selection witnesses are added to the expected object,
    never deleted from the actual result.
    """
    output = deepcopy(prior)
    evidence = output["numerology_evidence"]
    collation = evidence["canping_text_collation"]
    old, new = REFERENCE["old_summary"], REFERENCE["new_summary"]
    assert collation["comparison_witness"] == old
    traces = [
        row
        for row in evidence["rule_trace"]
        if row["rule_id"] == "canping_text_selection_v1"
    ]
    assert len(traces) == 1
    facts = traces[0]["facts"]
    assert facts["comparison_witness_id"] == old["corpus_id"] == new["corpus_id"]
    assert facts["comparison_witness_sha256"] == old["sha256"]
    collation["comparison_witness"] = deepcopy(new)
    facts["comparison_witness_sha256"] = new["sha256"]
    return add_reviewed_selection_witnesses(output)


def add_reviewed_selection_witnesses(prior):
    """Only extend old expected selections using the fixed page-bound literals."""
    output = deepcopy(prior)
    additions = {
        (row["element"], row["number"], row["kind"]): row["added_witnesses"]
        for row in ADDITIONS
    }
    seen = set()

    def add(value):
        if isinstance(value, dict):
            if id(value) in seen:
                return
            seen.add(id(value))
            key = (value.get("element"), value.get("number"), value.get("kind"))
            if "cell_status" in value and key in additions:
                assert "witnesses" not in value
                value["witnesses"] = deepcopy(additions[key])
            for child in value.values():
                add(child)
        elif isinstance(value, list):
            for child in value:
                add(child)

    add(output)
    return output
