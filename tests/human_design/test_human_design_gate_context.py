"""Frozen independent graph contexts and source-qualified public terminology."""

import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design import bodygraph, longitude_activation
from fatebridge.core.human_design_gate_context import (
    classify_gate_context,
    gate_context_report,
    source_records,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

FIXTURE = Path(__file__).parents[1] / "data/human_design/gate_context"
PLAN = json.loads((FIXTURE / "plan.json").read_text())
REFERENCE = json.loads(gzip.decompress((FIXTURE / "reference.json.gz").read_bytes()))
SPEC = next(s for s in CATALOG if s.key == "human_design")


def test_preimplementation_plan_reference_and_source_disagreement_are_frozen():
    assert (
        hashlib.sha256((FIXTURE / "hashes.json").read_bytes()).hexdigest()
        == "c72404645445dd31bfe23a666efc66bf9b98e544d23e34e8864f8ab76fc3196a"
    )
    for n, d in json.loads((FIXTURE / "hashes.json").read_text()).items():
        assert hashlib.sha256((FIXTURE / n).read_bytes()).hexdigest() == d
    assert (
        REFERENCE["plan_sha256"]
        == "8a30d868b5767c37ffdb561844fc35997cfa297b47d277ae3646893c17f02942"
    )
    assert len(PLAN["cases"]) == len(REFERENCE["cases"]) == 3339
    assert REFERENCE["reference_imports_fatebridge"] is False
    assert (
        hashlib.sha256(
            gzip.decompress((FIXTURE / "reference.json.gz").read_bytes())
        ).hexdigest()
        == "35948eae3e18b5e50fee5a5f8737c9faf940f39457bc6527012c6bea811aec50"
    )


@pytest.mark.parametrize("start", range(0, 3339, 128))
def test_every_original_graph_matches_the_independent_source_table_reference(start):
    for case, fact in zip(
        PLAN["cases"][start : start + 128],
        REFERENCE["cases"][start : start + 128],
        strict=True,
    ):
        assert case["id"] == fact["id"]
        expected = {k: v for k, v in fact.items() if k != "id"}
        actual = classify_gate_context(case["personality"], case["design"])
        assert actual == expected, case["id"]
        assert set(actual["active_in_defined_centers"]).isdisjoint(
            actual["dormant_in_undefined_centers"]
        )
        assert (
            sorted(
                actual["active_in_defined_centers"]
                + actual["dormant_in_undefined_centers"]
            )
            == actual["activated_gates"]
        )


def test_both_published_hanging_conventions_are_kept_for_single_dormant_gate():
    graph = bodygraph([20], [])
    context = classify_gate_context([20], [])
    assert graph["hanging_gates"] == context["broad_unpaired_activated_gates"] == [20]
    assert context["defined_center_hanging_gates"] == []
    assert context["dormant_in_undefined_centers"] == [20]
    assert graph["type"] == "reflector" and graph["channels"] == []


def test_shared_integration_gate_keeps_completed_and_uncompleted_connections():
    context = classify_gate_context([10], [20])
    row = next(r for r in context["gates"] if r["gate"] == 10)
    assert row["completed_channel_pairs"] == [[10, 20]]
    assert [10, 34] in row["uncompleted_channel_pairs"]
    assert row["expression"] == "active_in_defined_center"
    assert context["broad_unpaired_activated_gates"] == []


def test_every_witness_uses_its_own_gate_union_and_actual_array_sources():
    def chart(p, d):
        return {
            "activations": {
                "personality": [{"gate": g} for g in p],
                "design": [{"gate": g} for g in d],
            },
            "bodygraph": bodygraph(p, d),
        }

    nominal = chart([1], [8, 20])
    alternative = chart([1], [8, 27])
    snapshot = {
        "projection_format": "gate_line_tone_personality_color_v2",
        "activations": alternative["activations"],
        "channels": alternative["bodygraph"]["channels"],
    }
    nominal["node_backend_comparison"] = {"selected_structure": snapshot}
    report = gate_context_report(nominal)
    assert report["nominal"]["defined_center_hanging_gates"] == [20]
    assert report["nominal"]["dormant_in_undefined_centers"] == []
    assert report["witnesses"][0]["dormant_in_undefined_centers"] == [27]
    assert (
        report["witnesses"][0]["source_snapshot_path"]
        == "node_backend_comparison.selected_structure"
    )
    assert all(
        b["path"].startswith("node_backend_comparison.selected_structure.")
        for b in report["witnesses"][0]["basis"]
    )


def test_three_frozen_public_sources_do_not_become_an_original_manuscript_claim():
    identities = json.loads((FIXTURE / "source-identities.json").read_text())
    for record, key in zip(
        source_records(), ["dictionary", "broad-2025", "narrow-2026"], strict=True
    ):
        assert record["url"] == identities[key]["url"]
        assert record["html_sha256"] == identities[key]["html_sha256"]
    assert "AI-assisted" in source_records()[1]["attribution"]


def test_public_longitude_example_disagreement_is_retained_without_changing_the_engine():
    record = json.loads((FIXTURE / "longitude-source-disagreement.json").read_text())
    assert record["status"] == "unresolved_public_example_disagreement"
    assert record["current_public_page_claimed_gate"] == 25
    table = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "src/fatebridge/data/human_design/rave-2001-reference.json"
        ).read_text()
    )
    row = next(r for r in table["gates"] if r["gate"] == 21)
    assert row["start_longitude"] <= record["longitude_degrees"] < row["end_longitude"]
    actual = longitude_activation(record["longitude_degrees"])
    assert actual["gate"] == record["primary2001table_gate"] == 21
    assert actual["gate"] != record["current_public_page_claimed_gate"]
    assert record["publisher_erratum_obtained"] is False


@pytest.fixture(scope="module")
def complete():
    return execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=1980,
            birth_month=9,
            birth_day=9,
            birth_hour=12,
            birth_minute=0,
            birth_timezone="Europe/London",
            birth_time_uncertainty_minutes=1,
        ),
    )


def test_complete_reading_keeps_old_statement_count_and_verifies_new_context_block(
    complete,
):
    check = verify_human_design_reading(complete)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_statement_count"] == 10
    assert check["gate_activation_context_status"] == "verified_all_current_contexts"
    report = complete["gate_activation_context"]
    assert report["context_count"] == 1 + len(report["witnesses"]) > 1
    assert (
        "休眠仍属于本命已激活"
        in complete["interpretation"]["gate_activation_context"]["text"]
    )


def test_json_object_sorting_never_changes_complete_context_verification(complete):
    sorted_value = json.loads(json.dumps(complete, sort_keys=True))
    check = verify_human_design_reading(sorted_value)
    assert check["status"] == "verified_fixed_template_reading", check
    report = sorted_value["gate_activation_context"]
    assert gate_context_report(sorted_value) == report


@pytest.mark.parametrize(
    "fault",
    ["all_regions", "report", "reading", "ruleset", "trace", "unknown_contract"],
)
def test_current_or_unknown_contract_cannot_drop_extension_after_rehash(
    complete, fault
):
    value = copy.deepcopy(complete)
    if fault in ("all_regions", "report", "unknown_contract"):
        value.pop("gate_activation_context")
    if fault in ("all_regions", "reading", "unknown_contract"):
        value["interpretation"].pop("gate_activation_context")
    if fault in ("all_regions", "ruleset", "unknown_contract"):
        value["rulesets"] = [
            r
            for r in value["rulesets"]
            if r.get("id") != "human_design_gate_activation_context_v1"
        ]
    if fault in ("all_regions", "trace", "unknown_contract"):
        value["rule_trace"] = [
            r
            for r in value["rule_trace"]
            if r.get("rule_id") != "human_design_gate_activation_context_v1"
        ]
    if fault == "unknown_contract":
        value["run_metadata"]["contract_sha256"] = "0" * 64
    check = verify_human_design_reading(value)
    assert check["status"] == "rejected", check
    assert check["gate_activation_context_status"] == "not_verified"


@pytest.mark.parametrize(
    "fault",
    [
        "dormant_as_active",
        "narrow_as_broad",
        "wrong_side",
        "wrong_center",
        "source_identity",
        "source_author",
        "missing_witness",
        "copy_nominal",
        "basis_rebinding",
        "wrong_prose",
        "fake_physical_certificate",
    ],
)
def test_rehashing_does_not_accept_false_states_sources_or_cross_witness_explanations(
    complete, fault
):
    value = copy.deepcopy(complete)
    report = value["gate_activation_context"]
    nominal = report["nominal"]
    if fault == "dormant_as_active":
        g = nominal["dormant_in_undefined_centers"].pop()
        nominal["active_in_defined_centers"].append(g)
    elif fault == "narrow_as_broad":
        assert (
            nominal["defined_center_hanging_gates"]
            != nominal["broad_unpaired_activated_gates"]
        )
        nominal["defined_center_hanging_gates"] = list(
            nominal["broad_unpaired_activated_gates"]
        )
    elif fault == "wrong_side":
        r = nominal["gates"][0]
        r["source_sides"] = []
    elif fault == "wrong_center":
        nominal["gates"][0]["center"] = "not_a_center"
    elif fault == "source_identity":
        report["ruleset"]["source_records"][0]["html_sha256"] = "0" * 64
    elif fault == "source_author":
        report["ruleset"]["source_records"][1][
            "attribution"
        ] = "Ra Uru Hu original2001manuscript"
    elif fault == "missing_witness":
        report["witnesses"].pop()
    elif fault == "copy_nominal":
        report["witnesses"][0] = copy.deepcopy(nominal)
    elif fault == "basis_rebinding":
        nominal["basis"][0]["path"] = "profile"
    elif fault == "wrong_prose":
        value["interpretation"]["gate_activation_context"][
            "text"
        ] = "所有激活门都已定义、无休眠，原典与现实有效性全部认证。"
    else:
        report["scope"] = "physically_certified_empirical_neutrino_mechanism"
    assert verify_human_design_reading(value)["status"] == "rejected"
