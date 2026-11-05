"""Official coupled-channel facts and their actual structural interpretation."""

import ast
import json
import runpy
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design import bodygraph
from fatebridge.core.human_design_circuitry import (
    audit_channel_circuits,
    audit_circuit_groups,
    circuit_group_reference,
    circuit_reference,
    circuitry_summary,
)
from fatebridge.core.human_design_evidence import circuitry_reading, source_reference
from fatebridge.core.human_design_mechanics import CHANNELS
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from tests.ephemeris_context import moshier_ephemeris


@pytest.mark.parametrize("row", circuit_reference()["coupled_channels"])
def test_official_six_coupled_channel_classifications(row):
    first, second = row["gates"]
    graph = bodygraph([first], [second])
    assert len(graph["channels"]) == 1
    assert graph["channels"][0]["circuit"] == row["circuit"]
    assert graph["channels"][0]["mixed_only"] is True


def test_six_connections_are_not_six_integration_channels():
    graph = bodygraph([10, 20], [34, 57])
    assert len(graph["channels"]) == 6
    summary = graph["circuitry"]
    by_circuit = {row["id"]: row for row in summary["circuits"]}
    assert by_circuit["integration"]["channel_count"] == 4
    assert by_circuit["integration"]["group"] == "individual"
    assert by_circuit["individual_knowing"]["channel_ids"] == ["20-57"]
    assert by_circuit["individual_centering"]["channel_ids"] == ["10-34"]
    assert summary["group_channel_counts"] == {
        "individual": 6,
        "collective": 0,
        "tribal": 0,
    }
    assert summary["integration"]["all_four_channels_complete"] is True
    assert set(summary["integration"]["completed_channel_ids"]) == {
        "10-20",
        "10-57",
        "20-34",
        "34-57",
    }
    assert set(summary["integration"]["adjacent_individual_channel_ids"]) == {
        "10-34",
        "20-57",
    }
    assert graph["subtype"] == "manifesting_generator"
    assert graph["authority"] == "sacral"
    assert (
        sum(summary["group_channel_counts"].values())
        == summary["defined_channel_count"]
        == 6
    )
    assert summary["group_membership"]["integration_group"] == "individual"
    assert "个体6" in circuitry_reading(graph)


def test_brainwave_is_knowing_without_any_completed_integration_channel():
    graph = bodygraph([20], [57])
    assert graph["type"] == "projector"
    assert graph["authority"] == "splenic"
    assert graph["circuitry"]["integration"] == {
        "activated_gates": [20, 57],
        "completed_channel_ids": [],
        "all_four_channels_complete": False,
        "adjacent_individual_channel_ids": ["20-57"],
    }
    text = circuitry_reading(graph)
    assert "20-57" in text and "独特领会" in text
    assert graph["circuitry"]["circuits"][0]["id"] == "individual_knowing"


def test_hanging_gates_do_not_create_a_fixed_circuit_or_a_deficit_reading():
    graph = bodygraph([20], [])
    assert graph["circuitry"]["defined_channel_count"] == 0
    assert graph["circuitry"]["circuits"] == []
    assert graph["circuitry"]["integration"]["activated_gates"] == [20]
    assert graph["hanging_gates"] == [20]
    assert "单门仍保留" in circuitry_reading(graph)


def test_direct_source_evidence_stays_separate_from_endpoint_inferences():
    report = audit_channel_circuits(CHANNELS, source_reference()["gates"])
    assert report["status"] == "bounded_public_source_match"
    assert report["channels_matched"] == report["channels_checked"] == 36
    assert report["direct_classifications_checked"] == 6
    assert report["endpoint_inferences_checked"] == 30
    assert "推断" in report["scope"]


def test_old_brainwave_misclassification_is_detected_against_unchanged_source():
    old = tuple(
        (a, b, "integration" if (a, b) == (20, 57) else c) for a, b, c in CHANNELS
    )
    report = audit_channel_circuits(old, source_reference()["gates"])
    assert report["status"] == "mismatch_or_incomplete"
    assert report["channels_matched"] == 35
    assert report["discrepancies"] == [
        {
            "gates": [20, 57],
            "implemented": "integration",
            "source_expected": "individual_knowing",
            "evidence_kind": "explicit_official_channel_classification",
        }
    ]


def test_deleting_source_facts_cannot_turn_the_check_into_full_acceptance(monkeypatch):
    from fatebridge.core import human_design_circuitry as module

    shortened = deepcopy(circuit_reference())
    shortened["coupled_channels"] = shortened["coupled_channels"][:1]
    monkeypatch.setattr(module, "circuit_reference", lambda: shortened)
    assert (
        audit_channel_circuits(CHANNELS, source_reference()["gates"])["status"]
        == "mismatch_or_incomplete"
    )


def test_unknown_circuit_never_receives_an_invented_interpretation():
    with pytest.raises(ValueError, match="回路分类"):
        circuitry_summary(
            [{"circuit": "invented", "id": "20-57", "gates": [20, 57]}], [20, 57]
        )


def test_all_channels_partition_into_three_groups_with_integration_in_individual():
    graph = bodygraph(range(1, 65), [])
    summary = graph["circuitry"]
    assert summary["defined_channel_count"] == 36
    assert summary["group_channel_counts"] == {
        "individual": 15,
        "collective": 14,
        "tribal": 7,
    }
    assert sum(summary["group_channel_counts"].values()) == 36
    assert len(summary["integration"]["completed_channel_ids"]) == 4
    report = audit_circuit_groups(CHANNELS)
    assert report["status"] == "bounded_public_group_membership_match"
    assert report["memberships_checked"] == report["memberships_matched"] == 7
    assert report["all_channel_group_counts"] == summary["group_channel_counts"]
    assert report["group_counts_partition_complete_channels"]
    assert "30条" in report["scope"]


@pytest.mark.parametrize("row", [c for c in CHANNELS if c[2] == "integration"])
def test_each_integration_channel_counts_once_in_individual_and_its_subset(row):
    a, b, _ = row
    summary = bodygraph([a], [b])["circuitry"]
    assert summary["defined_channel_count"] == 1
    assert summary["group_channel_counts"] == {
        "individual": 1,
        "collective": 0,
        "tribal": 0,
    }
    assert len(summary["integration"]["completed_channel_ids"]) == 1
    assert (
        summary["group_membership"]["integration_is_separately_reported_subset"] is True
    )


def test_old_exclusion_is_rejected_against_unchanged_official_membership(monkeypatch):
    from fatebridge.core import human_design_circuitry as module

    old = {**module.CIRCUIT_GROUP, "integration": None}
    monkeypatch.setattr(module, "CIRCUIT_GROUP", old)
    report = audit_circuit_groups(CHANNELS)
    assert report["status"] == "mismatch_or_incomplete"
    assert report["memberships_matched"] == 6
    assert report["group_counts_partition_complete_channels"] is False
    assert report["all_channel_group_counts"]["individual"] == 11


@pytest.mark.parametrize(
    "bad", ["remove_integration", "duplicate_membership", "swap_group"]
)
def test_incomplete_or_conflicting_reference_cannot_certify_group_membership(
    monkeypatch, bad
):
    from fatebridge.core import human_design_circuitry as module

    ref = deepcopy(circuit_group_reference())
    if bad == "remove_integration":
        ref["groups"]["individual"].remove("integration")
    elif bad == "duplicate_membership":
        ref["groups"]["collective"].append("integration")
    else:
        ref["groups"]["individual"].remove("integration")
        ref["groups"]["collective"].append("integration")
    monkeypatch.setattr(module, "circuit_group_reference", lambda: ref)
    assert audit_circuit_groups(CHANNELS)["status"] == "mismatch_or_incomplete"


def test_no_channel_is_an_empty_partition_without_invented_group_themes():
    summary = bodygraph([10], [34])["circuitry"]
    assert summary["integration"]["completed_channel_ids"] == []
    assert summary["group_channel_counts"]["individual"] == 1
    empty = bodygraph([10], [20])
    assert empty["circuitry"]["group_channel_counts"]["individual"] == 1
    empty = bodygraph([10], [])
    assert empty["circuitry"]["group_channel_counts"] == {
        "individual": 0,
        "collective": 0,
        "tribal": 0,
    }
    assert empty["circuitry"]["circuits"] == []


def test_membership_extractor_is_independent_and_rejects_missing_source_anchors(
    tmp_path,
):
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts/build_human_design_circuit_group_reference.py"
    )
    tree = ast.parse(path.read_text())
    assert not any(
        (isinstance(n, ast.ImportFrom) and (n.module or "").startswith("fatebridge"))
        or (
            isinstance(n, ast.Import)
            and any(a.name.startswith("fatebridge") for a in n.names)
        )
        for n in ast.walk(tree)
    )
    namespace = runpy.run_path(str(path))
    dictionary = tmp_path / "dictionary.html"
    overview = tmp_path / "overview.html"
    dictionary.write_text(
        "<h4>Individual</h4><p>Knowing Circuit; Centering Circuit.</p>"
    )
    overview.write_text(
        "<p>Individual Circuit Group (Empowerment) plus the Integration Channel Collective Circuit Group (Sharing)</p>"
    )
    with pytest.raises(ValueError, match="Individual membership"):
        namespace["build"](dictionary, overview)
    reference_path = (
        Path(__file__).resolve().parents[1]
        / "src/fatebridge/data/human_design/circuit-group-2026-reference.json"
    )
    assert json.loads(reference_path.read_text()) == circuit_group_reference()


@pytest.fixture(scope="module")
def integrated_run():
    root = Path(__file__).resolve().parent / "fixtures"
    cases = json.loads((root / "human-design-official-charts.json").read_text())[
        "cases"
    ]
    cases += json.loads(
        (root / "human-design-official-authority-charts.json").read_text()
    )["cases"]
    integration = [{10, 20}, {10, 57}, {20, 34}, {34, 57}]
    case = next(
        c
        for c in cases
        if any(
            pair <= {int(x.split(".")[0]) for col in c["columns"].values() for x in col}
            for pair in integration
        )
    )
    spec = next(s for s in CATALOG if s.key == "human_design")
    with moshier_ephemeris():
        result = execute_tool(spec, spec.request_model(**case["birth_input"]))
    assert result["bodygraph"]["circuitry"]["integration"]["completed_channel_ids"]
    assert (
        verify_human_design_reading(result)["status"]
        == "verified_fixed_template_reading"
    )
    return result


@pytest.mark.parametrize(
    "bad", ["exclude", "double_count", "membership", "source", "joint", "text"]
)
def test_rehashed_group_claims_must_match_actual_structure(integrated_run, bad):
    result = deepcopy(integrated_run)
    group = result["bodygraph"]["circuitry"]
    if bad in {"exclude", "double_count"}:
        delta = len(group["integration"]["completed_channel_ids"])
        group["group_channel_counts"]["individual"] += (
            -delta if bad == "exclude" else delta
        )
    elif bad == "membership":
        group["group_membership"]["integration_group"] = "none"
    elif bad == "source":
        result["source_consistency"]["circuit_group_memberships"]["memberships"] = []
    elif bad == "joint":
        result["node_convention_comparison"]["reference_structure"]["circuitry"][
            "group_membership"
        ]["integration_group"] = "none"
    else:
        result["interpretation"][
            "circuitry_meaning"
        ] = "整合通道不属于任何群，因此从个体群全部扣除。"
    result["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in result.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(result)["status"] == "rejected"
