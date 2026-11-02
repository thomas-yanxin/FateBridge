"""New reversible archive annotations preserve all historical calculation facts."""

import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from fatebridge.application.execution import validate_output
from scripts.audit_ren_golden_evidence import ORIGINALS, SLUGS, plan, reference
from scripts.jinkou_archive_proofs import ARCHIVE_SNAPSHOTS, historical_pattern_proofs
from scripts.liuren_course_archive import historical_course_conditions
from scripts.liuren_ordered_archive import historical_ordered_patterns
from tests.ren_archive_contract import (
    NOMINAL_SEASONAL_GAP,
    assert_historical_contract_gap,
)
from tests.test_agentic_nested_outputs import SPECS

ROOT = Path(__file__).resolve().parents[1]


def archived(slug="api_cn_jinkou"):
    path = ARCHIVE_SNAPSHOTS / (slug + ".json")
    return json.loads(path.read_text()), path, path.read_bytes()


@pytest.mark.parametrize("slug", SLUGS)
def test_complete_archive_supplement_keeps_all_old_fields_and_file_bytes(slug):
    value, path, before = archived(slug)
    original = copy.deepcopy(value)
    augmented, receipt = historical_pattern_proofs(value)
    assert value == original and path.read_bytes() == before
    assert (
        receipt["existing_fields_unchanged"]
        and receipt["original_object_restored_exactly"]
    )
    assert (
        receipt["golden_files_written"] is False
        and receipt["not_a_historical_or_live_receipt"]
    )
    key = {
        "api_cn_jinkou": "jinkou",
        "api_cn_liureng_gods": "liureng_gods",
        "api_cn_liureng_runyear": "liureng_runyear",
        "api_divination_sanshiunited": "sanshiunited",
    }[slug]
    current_annotations, ordered_receipt = historical_ordered_patterns(augmented)
    current_annotations, course_receipt = historical_course_conditions(
        current_annotations
    )
    assert course_receipt["original_object_restored_exactly"]
    assert ordered_receipt["original_object_restored_exactly"]
    assert_historical_contract_gap(
        SPECS[key],
        {k: v for k, v in current_annotations.items() if k != "run_metadata"},
    )
    if key == "jinkou":
        assert len(receipt["changes"]) == 132
        assert augmented["jinkou"]["ruleset"] == value["jinkou"]["ruleset"]
        assert augmented["snapshot_text"] == value["snapshot_text"]
        assert [
            r["matched"] for r in augmented["jinkou"]["patterns"]["evaluations"]
        ] == [r["matched"] for r in value["jinkou"]["patterns"]["evaluations"]]
    else:
        assert augmented == value and not receipt["changes"]


def test_adding_twice_is_idempotent_and_stripping_restores_the_exact_old_object():
    value, _, _ = archived()
    one, first = historical_pattern_proofs(value)
    two, second = historical_pattern_proofs(one)
    assert two == one and not second["changes"]
    restored, reverse = historical_pattern_proofs(two, mode="strip")
    assert restored == value and len(reverse["changes"]) == len(first["changes"]) == 132


def test_existing_migration_has_one_reverse_ledger_including_nested_trace_additions():
    value, path, before = archived()
    original = json.loads((ORIGINALS / "api_cn_jinkou.json").read_text())
    result, receipt = plan("api_cn_jinkou", value, reference())
    again, same = plan("api_cn_jinkou", result, reference())
    assert again == result
    assert not same["complete_business_output_contract_passed"]
    assert same["current_contract_error"] == NOMINAL_SEASONAL_GAP
    assert (
        receipt["original_object_restored_exactly"]
        and not receipt["complete_business_output_contract_passed"]
    )
    reverse = copy.deepcopy(result)
    for change in reversed(receipt["applied"]):
        parts = change["path"].split(".")
        parent = reverse
        for p in parts[:-1]:
            parent = parent[int(p)] if isinstance(parent, list) else parent[p]
        if change["kind"] == "added":
            del parent[parts[-1]]
        else:
            parent[parts[-1]] = copy.deepcopy(change["old"])
    assert reverse == original and path.read_bytes() == before
    assert receipt["derived_archive_pattern_proofs"]["supplement_computed_now"]


def test_derived_courses_get_separate_reversible_annotations():
    from tests.test_jinkou_pattern_proofs import complete

    value = complete()[0]
    legacy, removed = historical_pattern_proofs(value, mode="strip")
    assert len(removed["courses"]) == 3 and len(removed["changes"]) == 396
    rebuilt, added = historical_pattern_proofs(legacy)
    assert rebuilt == value and len(added["changes"]) == 396
    validate_output(SPECS["jinkou"], rebuilt)


@pytest.mark.parametrize(
    "fault",
    [
        "old_verdict",
        "old_basis",
        "raw_symbol",
        "raw_day",
        "recorded_stem",
        "empty_flag",
        "missing_trace",
        "duplicate_trace",
        "trace_mismatch",
        "proof_result",
        "missing_proof_fact",
        "missing_proof_group",
    ],
)
def test_wrong_old_or_supplied_new_facts_are_rejected_in_both_modes(fault):
    value, _, _ = archived()
    if fault.startswith("proof") or fault.startswith("missing_proof"):
        value, _ = historical_pattern_proofs(value)
    board = value["jinkou"]
    pat = board["patterns"]
    trace = next(
        t for t in board["rule_trace"] if t["rule_id"] == "jinkou.structural_patterns"
    )
    if fault == "old_verdict":
        pat["evaluations"][0]["matched"] = not pat["evaluations"][0]["matched"]
    elif fault == "old_basis":
        pat["matched"][0]["basis"] = "forged old basis"
    elif fault == "raw_symbol":
        board["rows"][0]["content"] = "甲"
    elif fault == "raw_day":
        board["calendar_policy"]["effective_day_ganzhi"] = "甲子"
    elif fault == "recorded_stem":
        board["rows"][1]["dun_stem"] = "甲"
    elif fault == "empty_flag":
        board["rows"][2]["xun_kong"] = not board["rows"][2]["xun_kong"]
    elif fault == "missing_trace":
        board["rule_trace"].remove(trace)
    elif fault == "duplicate_trace":
        board["rule_trace"].append(copy.deepcopy(trace))
    elif fault == "trace_mismatch":
        trace["result"]["evaluations"][0]["matched"] = not trace["result"][
            "evaluations"
        ][0]["matched"]
    elif fault == "proof_result":
        pat["condition_facts"][0]["matched"] = not pat["condition_facts"][0]["matched"]
    elif fault == "missing_proof_fact":
        pat["condition_facts"].pop()
    elif fault == "missing_proof_group":
        pat["evaluations"][0].pop("condition_groups")
    else:
        raise AssertionError(fault)
    for mode in ["add", "strip"]:
        with pytest.raises(ValueError):
            historical_pattern_proofs(value, mode=mode)


@pytest.mark.parametrize("fault", ["edit", "drop", "extra"])
def test_supplement_protocol_inventory_cannot_drift(fault, tmp_path, monkeypatch):
    import scripts.jinkou_archive_proofs as adapter

    folder = tmp_path / "protocol"
    shutil.copytree(adapter.CORPUS, folder)
    if fault == "edit":
        (folder / "reference.json").write_text("{}")
    elif fault == "drop":
        (folder / "protocol.json").unlink()
    else:
        (folder / "unexpected.json").write_text("{}")
    monkeypatch.setattr(adapter, "CORPUS", folder)
    with pytest.raises((ValueError, FileNotFoundError)):
        adapter.reference()
