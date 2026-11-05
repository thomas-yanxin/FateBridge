"""Direct source observations, all-channel completion and reading fidelity."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design import bodygraph
from fatebridge.core.human_design_circuit_topology import topology_reference
from fatebridge.core.human_design_evidence import reference_table_audit
from fatebridge.core.human_design_references import clear_reference_cache
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = topology_reference()
SPEC = next(s for s in CATALOG if s.key == "human_design")
INPUT = dict(
    birth_year=1990,
    birth_month=4,
    birth_day=6,
    birth_hour=9,
    birth_minute=33,
    birth_timezone="Asia/Shanghai",
)


def test_frozen_visual_facts_retain_all_pages_ocr_errors_and_source_conflict():
    p = ROOT / "tests/fixtures/human-design-circuit-pages-observations.json"
    assert (
        hashlib.sha256(p.read_bytes()).hexdigest()
        == REFERENCE["observation_fixture_sha256"]
    )
    plan = ROOT / "tests/fixtures/human-design-circuit-pages-plan.json"
    assert hashlib.sha256(plan.read_bytes()).hexdigest() == REFERENCE["plan_sha256"]
    assert len(REFERENCE["topologies"]) == 7
    assert [
        len(t["image_read_listed_gate_pairs"]) for t in REFERENCE["topologies"]
    ] == [4, 9, 2, 7, 7, 5, 2]
    assert sum(len(t["ocr_disagreements"]) for t in REFERENCE["topologies"]) == 2
    assert REFERENCE["source"]["publisher_master_authenticity_certified"] is False
    audit = reference_table_audit()["archival_channel_pages"]
    assert audit["channels_checked"] == audit["channels_matched"] == 36
    assert audit["source_pair_sets_equal"] is True
    conflict = audit["source_label_disagreements"][0]
    assert conflict["printed_motor_names"] == ["Root", "Solar Plexus"]
    assert conflict["computed_endpoint_motor_centers"] == ["sacral", "solar_plexus"]
    assert conflict["endpoint_observation_reproduced"] is True
    assert conflict["resolved"] is conflict["publisher_erratum_obtained"] is False
    # The previous check remains intact, with its original weaker evidence scope.
    prior = reference_table_audit()["channel_classifications"]
    assert prior["direct_classifications_checked"] == 6
    assert prior["endpoint_inferences_checked"] == 30


def test_connected_definition_is_not_complete_logic_circuit():
    one = bodygraph([63, 4], [])
    assert one["definition"]["kind"] == "single"
    row = next(
        t
        for t in one["circuitry"]["topology_completion"]["topologies"]
        if t["id"] == "collective_understanding"
    )
    assert row["defined_channel_ids"] == ["4-63"]
    assert len(row["required_channel_ids"]) == 7
    assert len(row["missing_channel_ids"]) == 6
    assert row["all_channels_defined"] is False


def test_four_integration_gates_complete_only_the_separate_integration_topology():
    graph = bodygraph([10, 20, 34, 57], [])
    assert len(graph["channels"]) == 6
    summary = graph["circuitry"]["topology_completion"]
    assert summary["integration_all_four_defined"] is True
    assert summary["fully_defined_circuit_ids"] == []
    rows = {r["id"]: r for r in summary["topologies"]}
    assert rows["individual_knowing"]["defined_channel_ids"] == ["20-57"]
    assert rows["individual_centering"]["defined_channel_ids"] == ["10-34"]


def test_source_motor_heading_cannot_define_an_unconnected_center_or_override_type():
    graph = bodygraph([27, 50], [])
    assert graph["type"] == "generator" and graph["authority"] == "sacral"
    assert graph["centers"]["root"]["status"] == "completely_open"
    assert graph["centers"]["solar_plexus"]["status"] == "completely_open"
    assert graph["centers"]["sacral"]["status"] == "defined"


def test_truncated_center_reference_reports_missing_facts_without_claiming_acceptance(
    monkeypatch,
):
    from fatebridge.core import human_design_evidence as module

    truncated = deepcopy(module.source_reference())
    truncated["gates"] = truncated["gates"][:1]
    monkeypatch.setattr(module, "source_reference", lambda: truncated)
    report = module.reference_table_audit()
    assert report["numeric_table_acceptance_passed"] is False
    diagnostic = report["archival_channel_pages"]
    assert diagnostic["status"] == "mismatch_or_incomplete"
    assert diagnostic["source_label_disagreements"][0][
        "missing_endpoint_gate_facts"
    ] == [6, 27, 50, 59]
    assert (
        diagnostic["source_label_disagreements"][0]["endpoint_observation_reproduced"]
        is False
    )


def test_returned_source_observations_cannot_poison_the_reference_cache():
    first = reference_table_audit()["archival_channel_pages"]
    try:
        first["source_label_disagreements"][0]["printed_motor_names"][0] = "Tampered"
        second = reference_table_audit()["archival_channel_pages"]
        assert second["source_label_disagreements"][0]["printed_motor_names"] == [
            "Root",
            "Solar Plexus",
        ]
    finally:
        clear_reference_cache()


def test_channel_subsets_match_the_independent_source_gate_presence_oracle():
    # 824 channel-subset constructions include overlapping Integration gates.
    # The oracle uses only the visually transcribed source sets, not CHANNELS.
    expected = {
        r["id"]: {tuple(sorted(p)) for p in r["image_read_listed_gate_pairs"]}
        for r in REFERENCE["topologies"]
    }
    checked = 0
    for source_pairs in expected.values():
        pairs = sorted(source_pairs)
        for mask in range(1 << len(pairs)):
            active = {
                gate for i, pair in enumerate(pairs) if mask & (1 << i) for gate in pair
            }
            graph = bodygraph(active, [])
            result = graph["circuitry"]["topology_completion"]
            for row in result["topologies"]:
                wanted = expected[row["id"]]
                present = {p for p in wanted if set(p) <= active}
                missing = wanted - present
                assert row["all_channels_defined"] == (not missing)
                assert {
                    tuple(map(int, p.split("-"))) for p in row["defined_channel_ids"]
                } == present
                assert {
                    tuple(map(int, p.split("-"))) for p in row["missing_channel_ids"]
                } == missing
            checked += 1
    assert checked == 824


@pytest.fixture(scope="module")
def complete():
    return execute_tool(SPEC, SPEC.request_model(**INPUT))


def test_complete_reading_preserves_old_statements_and_explains_topology_and_source(
    complete,
):
    assert len(complete["interpretation"]["statements"]) == 10
    text = complete["interpretation"]["circuit_topology_meaning"]
    assert (
        "中心群连通" in text and "运动中心标题" in text and "未认证出版方母版" in text
    )
    assert (
        len(complete["bodygraph"]["circuitry"]["topology_completion"]["topologies"])
        == 7
    )
    check = verify_human_design_reading(complete)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_circuit_topology_count"] == 7
    assert complete["validation"]["all_three_axes_full_marks"] is False


@pytest.mark.parametrize(
    "tamper",
    [
        "complete",
        "missing",
        "required",
        "kind",
        "reading",
        "publisher",
        "source_conflict",
        "source_motor",
        "source_revision",
    ],
)
def test_forged_completion_and_source_certification_rejected_even_after_rehash(
    complete, tamper
):
    value = deepcopy(complete)
    completion = value["bodygraph"]["circuitry"]["topology_completion"]
    row = next(r for r in completion["topologies"] if not r["all_channels_defined"])
    if tamper == "complete":
        row["all_channels_defined"] = True
    elif tamper == "missing":
        row["missing_channel_ids"] = []
    elif tamper == "required":
        row["required_channel_ids"] = row["defined_channel_ids"]
    elif tamper == "kind":
        row["kind"] = "single_definition"
    elif tamper == "reading":
        value["interpretation"][
            "circuit_topology_meaning"
        ] = "单一定义证明全部回路齐全。"
    elif tamper == "publisher":
        completion["publisher_master_authenticity_certified"] = True
    elif tamper == "source_conflict":
        value["source_consistency"]["archival_channel_pages"][
            "source_label_disagreements"
        ] = []
    elif tamper == "source_motor":
        value["source_consistency"]["archival_channel_pages"][
            "source_label_disagreements"
        ][0]["printed_motor_names"] = ["Sacral", "Solar Plexus"]
    else:
        completion["source_revision"] = "Publisher corrected edition"
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(value)["status"] == "rejected"
