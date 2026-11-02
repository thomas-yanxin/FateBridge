"""Historical additions stay explicit, reversible and separate from live gates."""

import copy
import json
from pathlib import Path

import pytest

from scripts.jinkou_archive_proofs import ARCHIVE_SNAPSHOTS, historical_pattern_proofs
from scripts.liuren_course_archive import historical_course_conditions
from scripts.liuren_cross_harmony_archive import historical_cross_harmony
from scripts.liuren_day_placement_archive import (
    historical_day_placements,
    legacy_candidate_day_placements,
    restore,
)
from scripts.liuren_ordered_archive import historical_ordered_patterns
from tests.ren_archive_contract import (
    NOMINAL_SEASONAL_GAP,
    assert_historical_contract_gap,
)
from tests.test_agentic_nested_outputs import SPECS
from tests.test_liuren_ordered_patterns import raw

ROOT = Path(__file__).resolve().parents[1]
SLUGS = {
    "api_cn_liureng_gods": "liureng_gods",
    "api_cn_liureng_runyear": "liureng_runyear",
    "api_cn_jinkou": "jinkou",
    "api_divination_sanshiunited": "sanshiunited",
}


@pytest.mark.parametrize("slug", SLUGS)
def test_existing_offline_golden_plan_keeps_all_original_migration_gates(slug):
    from scripts.audit_ren_golden_evidence import plan, reference

    candidate, path = archived(slug)
    before = path.read_bytes()
    migrated, receipt = plan(slug, candidate, reference())
    assert receipt["original_object_restored_exactly"]
    assert not receipt["complete_business_output_contract_passed"]
    assert receipt["current_contract_error"] == NOMINAL_SEASONAL_GAP
    assert receipt["derived_archive_day_placements"]["existing_fields_unchanged"]
    assert migrated["liureng"]["day_placement_patterns"]["unresolved_ids"] == [
        "D11",
        "D12",
    ]
    assert path.read_bytes() == before


def archived(slug="api_cn_liureng_gods"):
    path = ARCHIVE_SNAPSHOTS / (slug + ".json")
    return json.loads(path.read_text()), path


@pytest.mark.parametrize("slug", SLUGS)
def test_existing_fields_versions_and_files_are_preserved_exactly(slug):
    value, path = archived(slug)
    before = path.read_bytes()
    original = copy.deepcopy(value)
    augmented, proof = historical_day_placements(value)
    assert (
        proof["existing_fields_unchanged"] and proof["original_object_restored_exactly"]
    )
    assert (
        proof["not_a_historical_or_live_receipt"] and not proof["golden_files_written"]
    )
    assert value == original and path.read_bytes() == before
    assert augmented["liureng"]["ruleset"] == value["liureng"]["ruleset"]
    assert augmented["snapshot_text"] == value["snapshot_text"]
    restored, _ = historical_day_placements(augmented, mode="strip")
    assert restored == value
    twice, second = historical_day_placements(augmented)
    assert twice == augmented and second["changes"] == []
    for helper in (
        historical_pattern_proofs,
        historical_ordered_patterns,
        historical_course_conditions,
        historical_cross_harmony,
    ):
        augmented, _ = helper(augmented)
    assert_historical_contract_gap(
        SPECS[SLUGS[slug]], {k: v for k, v in augmented.items() if k != "run_metadata"}
    )


@pytest.mark.parametrize("mode", ["add", "strip"])
@pytest.mark.parametrize(
    "fault",
    [
        "missing_block",
        "missing_trace",
        "duplicate",
        "match",
        "unknown",
        "source",
        "numeric_bool",
        "different_day",
    ],
)
def test_bad_supplied_annotations_cannot_disappear(mode, fault):
    value, _ = archived()
    value, _ = historical_day_placements(value)
    board = value["liureng"]
    evidence = board["day_placement_patterns"]
    trace = next(
        t
        for t in board["rule_trace"]
        if t["rule_id"] == "liuren.day_placement_patterns"
    )
    if fault == "missing_block":
        board.pop("day_placement_patterns")
    elif fault == "missing_trace":
        board["rule_trace"].remove(trace)
    elif fault == "duplicate":
        board["rule_trace"].append(copy.deepcopy(trace))
    elif fault == "match":
        evidence["evaluations"][0]["matched"] = not evidence["evaluations"][0][
            "matched"
        ]
    elif fault == "unknown":
        evidence["evaluations"][10]["matched"] = False
    elif fault == "source":
        evidence["source_sha256"] = "invented"
    elif fault == "numeric_bool":
        evidence["evaluations"][0]["matched"] = int(
            evidence["evaluations"][0]["matched"]
        )
    else:
        evidence["day_ganzhi"] = "乙丑" if evidence["day_ganzhi"] != "乙丑" else "甲子"
    with pytest.raises(ValueError):
        historical_day_placements(value, mode=mode)


@pytest.mark.parametrize("fault", ["day", "layout", "positions"])
def test_absent_annotations_do_not_allow_repair_of_old_inputs(fault):
    value, _ = archived()
    board = value["liureng"]
    if fault == "day":
        board["calendar_policy"]["effective_day_ganzhi"] = "甲丑"
    elif fault == "positions":
        board["twelve_board"].pop()
    else:
        board["twelve_board"][0]["sky_branch"] = board["twelve_board"][1]["sky_branch"]
    with pytest.raises(ValueError):
        historical_day_placements(value)


@pytest.mark.parametrize("key", SLUGS.values())
def test_offline_live_compatibility_keeps_a_reversible_metadata_ledger(
    key, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    value = raw(key)
    old = copy.deepcopy(value)
    preceding, cross_proof = historical_cross_harmony(value, mode="strip")
    compatible, proof = legacy_candidate_day_placements(preceding)
    assert value == old and proof["original_candidate_restored_exactly"]
    assert not proof["old_gates_redefined"] and not proof["live_validation_bypassed"]
    assert compatible["liureng"]["ruleset"]["version"] == "1.14.0"
    assert "day_placement_patterns" not in compatible["liureng"]
    changes = proof["annotation_check"]["changes"] + proof["metadata_changes"]
    restored_preceding = restore(compatible, changes)
    assert restored_preceding == preceding
    assert restore(restored_preceding, cross_proof["changes"]) == old


def test_offline_compatibility_rejects_undeclared_source_metadata(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    value = raw("liureng_gods")
    value, _ = historical_cross_harmony(value, mode="strip")
    value["liureng"]["ruleset"]["conventions"]["day_placement_patterns"] = "invented"
    with pytest.raises(ValueError):
        legacy_candidate_day_placements(value)
