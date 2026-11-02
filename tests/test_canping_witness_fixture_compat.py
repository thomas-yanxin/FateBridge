"""A source-version compatibility check must never hide changed business facts."""

import copy
import gzip
import json

import pytest

from tests.canping_witness_fixture_compat import (
    ADDITIONS,
    REFERENCE,
    ROOT,
    rewind_reviewed_witness_summary,
    upgrade_frozen_witnesses,
)

CURRENT = json.loads(gzip.decompress((ROOT / "current-business.json.gz").read_bytes()))
LEGACY = json.loads(gzip.decompress((ROOT / "legacy-business.json.gz").read_bytes()))


def test_only_two_verified_receipts_change_in_the_entire_original_failing_result():
    before = copy.deepcopy(CURRENT)
    assert rewind_reviewed_witness_summary(CURRENT) == LEGACY
    assert CURRENT == before


@pytest.mark.parametrize(
    "field",
    [
        "version",
        "sha256",
        "source_pdf_sha256",
        "scope",
        "cells_examined",
        "clear_readings",
        "uncertain_readings",
        "registered_counterpart_cells",
        "registered_counterpart_keys",
        "ambiguous_counterpart_keys",
        "number_occurrence_ambiguities",
        "gold_tail_alignment",
        "unmatched_observations",
        "unmatched_observed_cells",
        "part_coverage",
        "primary_collation_count_increase",
    ],
)
def test_modified_new_source_fact_is_rejected_before_any_rewind(field):
    value = copy.deepcopy(CURRENT)
    summary = value["numerology_evidence"]["canping_text_collation"][
        "comparison_witness"
    ]
    summary[field] = {"unreviewed": summary[field]}
    with pytest.raises(AssertionError):
        rewind_reviewed_witness_summary(value)


def test_old_summary_cannot_pretend_to_be_a_current_verified_summary():
    value = copy.deepcopy(CURRENT)
    value["numerology_evidence"]["canping_text_collation"]["comparison_witness"] = (
        copy.deepcopy(REFERENCE["old_summary"])
    )
    with pytest.raises(AssertionError):
        rewind_reviewed_witness_summary(value)


@pytest.mark.parametrize("fault", ["hash", "id", "absent", "duplicate"])
def test_trace_must_bind_the_actual_same_source(fault):
    value = copy.deepcopy(CURRENT)
    traces = value["numerology_evidence"]["rule_trace"]
    target = next(r for r in traces if r["rule_id"] == "canping_text_selection_v1")
    if fault == "hash":
        target["facts"]["comparison_witness_sha256"] = "wrong"
    elif fault == "id":
        target["facts"]["comparison_witness_id"] = "wrong"
    elif fault == "absent":
        traces.remove(target)
    else:
        traces.append(copy.deepcopy(target))
    with pytest.raises(AssertionError):
        rewind_reviewed_witness_summary(value)


@pytest.mark.parametrize(
    "path",
    [
        ("benming", "numShun"),
        ("benming", "verses"),
        ("calendar_context", "timezone"),
        ("four_pillars", "day"),
    ],
)
def test_other_business_changes_remain_visible_to_the_original_comparison(path):
    value = copy.deepcopy(CURRENT)
    value[path[0]][path[1]] = "must remain visible"
    rewound = rewind_reviewed_witness_summary(value)
    assert rewound[path[0]][path[1]] == "must remain visible"
    assert rewound != LEGACY


def test_selected_witnesses_are_never_removed_or_accepted_as_old_values():
    value = copy.deepcopy(CURRENT)
    target = next(
        r["facts"]
        for r in value["numerology_evidence"]["rule_trace"]
        if r["rule_id"] == "canping_text_selection_v1"
    )["selectionShun"]
    target["witnesses"] = [{"text": "unreviewed new text"}]
    rewound = rewind_reviewed_witness_summary(value)
    after = next(
        r["facts"]
        for r in rewound["numerology_evidence"]["rule_trace"]
        if r["rule_id"] == "canping_text_selection_v1"
    )["selectionShun"]
    assert after["witnesses"] == target["witnesses"]
    assert rewound != LEGACY


def test_old_oracle_can_be_extended_without_changing_any_other_business_value():
    before = copy.deepcopy(LEGACY)
    assert upgrade_frozen_witnesses(LEGACY) == CURRENT
    assert LEGACY == before


def test_all30_declared_selection_additions_preserve_every_old_lookup_value():
    records = json.loads(
        gzip.decompress((ROOT.parent / "primary-lookup-before.json.gz").read_bytes())
    )
    keys = {(r["element"], r["number"], r["kind"]): r for r in ADDITIONS}
    value = copy.deepcopy(LEGACY)
    value["all_registered_selections"] = [
        record["result"]
        for record in records
        if (record["element"], record["number"], record["kind"]) in keys
    ]
    old = copy.deepcopy(value)
    current = upgrade_frozen_witnesses(value)
    assert len(current["all_registered_selections"]) == 30
    occurrences = 0
    for prior, after in zip(
        old["all_registered_selections"], current["all_registered_selections"]
    ):
        reverted = copy.deepcopy(after)
        selection = reverted["selection"]
        key = (selection["element"], selection["number"], selection["kind"])
        witnesses = selection.pop("witnesses")
        assert witnesses == keys[key]["added_witnesses"]
        occurrences += len(witnesses)
        assert reverted == prior
    assert occurrences == 33
    assert value == old


@pytest.mark.parametrize("fault", ["summary", "hash", "trace", "existing_witness"])
def test_upgrader_rejects_an_unverified_or_already_changed_old_oracle(fault):
    value = copy.deepcopy(LEGACY)
    evidence = value["numerology_evidence"]
    trace = next(
        r for r in evidence["rule_trace"] if r["rule_id"] == "canping_text_selection_v1"
    )
    if fault == "summary":
        evidence["canping_text_collation"]["comparison_witness"]["version"] = "wrong"
    elif fault == "hash":
        trace["facts"]["comparison_witness_sha256"] = "wrong"
    elif fault == "trace":
        evidence["rule_trace"].remove(trace)
    else:
        value["example_selection"] = {
            "element": "金",
            "number": 3322,
            "kind": "male",
            "cell_status": "source_cell_visually_collated",
            "witnesses": [{"text": "unreviewed"}],
        }
    with pytest.raises(AssertionError):
        upgrade_frozen_witnesses(value)
