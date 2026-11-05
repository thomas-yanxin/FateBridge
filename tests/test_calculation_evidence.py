"""Independent interval vectors and observed dependency failure cases."""

import asyncio
import json
from fractions import Fraction
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

from fatebridge.application.execution import execute_tool
from fatebridge.core.error_budget import (
    CombinedBound,
    ErrorComponent,
    circular_sector_candidates,
    combine_bounds,
    declared_error_budget,
)
from fatebridge.core.evidence_graph import (
    EvidenceEdge,
    EvidenceGraph,
    affected_nodes,
    execution_evidence,
    shared_input_origins,
)
from fatebridge.core.method_contracts import COMPATIBILITY_INDEX
from fatebridge.services.method_registration import EXCLUDED_TOOLS
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.json_digest import digest
from tests.fixtures.surface_payloads import REST_POST_CASES


def component(name, interval, unit="seconds", status="bounded"):
    return ErrorComponent(
        component_id=name,
        source=name,
        unit=unit,
        status=status,
        interval=interval,
        correlation_group="shared_clock",
        scope="synthetic arithmetic vector; no physical accuracy claim",
    )


def test_error_budget_keeps_unknowns_units_and_correlated_sources_distinct():
    with pytest.raises(ValidationError):
        CombinedBound(
            unit="degrees", status="bounded", interval=None, unresolved_components=()
        )
    with pytest.raises(ValidationError):
        CombinedBound(
            unit="degrees",
            status="bounded",
            interval=(0, 0),
            unresolved_components=("missing_ephemeris",),
        )
    values = (
        component("a", (-2, 3)),
        component("b", (-4, 1)),
        component("angle", (-0.5, 0.5), "degrees"),
    )
    combined = combine_bounds(values, "seconds")
    assert combined.interval == (-6, 4)
    assert combined.status == "bounded"
    unknown = component("clock", None, status="unquantified")
    assert combine_bounds((*values, unknown), "seconds").interval is None
    assert combine_bounds(values, "degrees").interval == (-0.5, 0.5)
    assert combine_bounds((), "seconds").status == "not_applicable"
    with pytest.raises(ValueError, match="重复"):
        combine_bounds((values[0], values[0]), "seconds")


def test_interval_addition_rounds_outward_and_declared_range_is_conditional():
    # In binary64, .1+.2 rounds above the exact sum of the stored operands.
    result = combine_bounds(
        (component("a", (0.1, 0.1)), component("b", (0.2, 0.2))), "seconds"
    )
    exact = Fraction(0.1) + Fraction(0.2)
    assert Fraction(result.interval[0]) <= exact <= Fraction(result.interval[1])
    declared = component("record", (-60, 60), status="declared")
    assert (
        combine_bounds((declared,), "seconds").status
        == "conditional_on_declared_inputs"
    )


@pytest.mark.parametrize(
    "status,interval",
    [
        ("unquantified", (0, 0)),
        ("not_applicable", (0, 0)),
        ("bounded", None),
        ("bounded", (2, 1)),
        ("bounded", (0, float("inf"))),
    ],
)
def test_unknowns_cannot_be_encoded_as_a_zero_bound(status, interval):
    with pytest.raises(ValidationError):
        component("bad", interval, status=status)


def test_input_precision_and_root_residual_do_not_certify_physical_accuracy():
    budget = declared_error_budget(
        ("civil_clock", "ephemeris_model", "numerical_solver"),
        {"birth_minute": 0},
        "origin",
    )
    assert all(row["status"] == "unquantified" for row in budget["components"])
    assert budget["output_error_bounds"] is None
    assert budget["source_coverage_complete"] is False
    # The published birth-range option uses 0 for "not assessed".
    nominal_only = declared_error_budget(
        ("civil_clock",), {"birth_time_uncertainty_minutes": 0}, "origin"
    )
    assert nominal_only["components"][0]["interval"] is None
    assert nominal_only["components"][0]["status"] == "unquantified"
    known = declared_error_budget(
        ("civil_clock",), {"birth_time_uncertainty_minutes": 2}, "origin"
    )
    assert known["components"][0]["interval"] == [-120, 120]
    assert (
        known["source_bounds_by_unit"][0]["status"] == "conditional_on_declared_inputs"
    )
    fractional = declared_error_budget(
        ("civil_clock",), {"birth_time_uncertainty_minutes": 0.07}, "origin"
    )["components"][0]["interval"]
    exact_radius = Fraction(0.07) * 60
    assert Fraction(fractional[0]) <= -exact_radius
    assert Fraction(fractional[1]) >= exact_radius


def test_continuous_angular_interval_covers_wrap_and_exact_sector_boundaries():
    bounds = combine_bounds((component("sky", (-1, 1), "degrees"),), "degrees")
    assert circular_sector_candidates(0, bounds, 12) == (0, 11)
    assert circular_sector_candidates(30, bounds, 12) == (0, 1)
    exact = combine_bounds((component("sky", (0, 0), "degrees"),), "degrees")
    assert circular_sector_candidates(40, exact, 27) == (3,)
    unknown = combine_bounds(
        (component("sky", None, "degrees", "unquantified"),), "degrees"
    )
    assert circular_sector_candidates(40, unknown, 27) is None


def test_execution_graph_binds_all_facts_preserves_partial_and_detects_bad_links():
    payload = {
        "summary": {"status": "partial", "score": 60},
        "detail": {"status": "conditional", "method_id": "test.source.v2", "empty": []},
    }
    value = execution_evidence(
        (COMPATIBILITY_INDEX,), {"birth_year": 1990}, payload, "input-hash"
    )
    graph = EvidenceGraph.model_validate(value["graph"])
    assert graph.business_output_sha256 == digest(payload)
    assert set(graph.output_nodes) == set(payload)
    assert {n.status for n in graph.nodes} >= {"partial", "conditional"}
    assert graph.runtime_method_ids == ("test.source.v2",)
    assert value["coverage"]["semantic_dependency_proof_complete"] is False
    assert shared_input_origins(graph, set(graph.output_nodes.values())) == {
        "input:birth_year"
    }
    assert set(graph.output_nodes.values()) <= affected_nodes(
        graph, {"input:birth_year"}
    )
    broken = graph.model_dump()
    broken["edges"] += (
        {"source": "missing", "target": "input:birth_year", "relation": "contains"},
    )
    with pytest.raises(ValidationError, match="悬空"):
        EvidenceGraph.model_validate(broken)
    cyclic = graph.model_dump()
    cyclic["edges"] += (
        EvidenceEdge(
            source=graph.output_nodes["summary"],
            target="input:birth_year",
            relation="declared_input_dependency",
        ).model_dump(),
    )
    with pytest.raises(ValidationError, match="循环"):
        EvidenceGraph.model_validate(cyclic)


def test_evidence_paths_distinguish_literal_keys_from_nested_fields():
    payload = {
        "basis": {
            "a.b": {"status": "literal-dot"},
            "a/b": {"status": "literal-slash"},
            "a~1b": {"status": "literal-tilde"},
            "a": {"b": {"status": "nested"}},
        }
    }
    evidence = execution_evidence((COMPATIBILITY_INDEX,), {}, payload, "input")
    graph = EvidenceGraph.model_validate(evidence["graph"])
    assert {node.path for node in graph.nodes if node.kind == "rule_witness"} == {
        "/basis/a.b",
        "/basis/a~1b",
        "/basis/a~01b",
        "/basis/a/b",
    }
    for node in graph.nodes:
        if node.kind not in {"result", "rule_witness"}:
            continue
        value = payload
        for token in node.path[1:].split("/"):
            value = value[token.replace("~1", "/").replace("~0", "~")]
        assert node.value_sha256 == digest(value)


def test_existing_rule_ledger_links_are_resolved_and_ambiguous_ids_stay_unknown():
    ledger = {
        "ledger": {
            "nodes": [{"id": "birth_day", "value": "甲子"}],
            "rules": [
                {
                    "id": "r1",
                    "rule_id": "original.rule",
                    "participants": ["birth_day"],
                    "status": "conditional",
                }
            ],
        }
    }
    result = execution_evidence(
        (COMPATIBILITY_INDEX,),
        {"birth_minute": 0, "gender": None},
        ledger,
        "origin",
        frozenset({"gender"}),
    )
    graph = EvidenceGraph.model_validate(result["graph"])
    statuses = {n.node_id: n.status for n in graph.nodes}
    assert (
        statuses["input:birth_minute"] == "defaulted"
        and statuses["input:gender"] == "explicit_null"
    )
    assert any(
        e.relation == "rule_input_witness"
        and e.source.endswith("/nodes/0")
        and e.target.endswith("/rules/0")
        for e in graph.edges
    )
    assert "/ledger/rules/0" in graph.resolved_rule_dependencies
    ledger["ledger"]["nodes"].append({"id": "birth_day", "value": "乙丑"})
    ambiguous = EvidenceGraph.model_validate(
        execution_evidence((COMPATIBILITY_INDEX,), {}, ledger, "origin")["graph"]
    )
    assert "/ledger/rules/0" in ambiguous.unresolved_rule_dependencies
    assert not any(e.relation == "rule_input_witness" for e in ambiguous.edges)


def test_standalone_resolution_policies_and_named_rule_dependencies_are_retained():
    payload = {
        "basis": {
            "policy": {"resolution_policy": "keep_unresolved.v1"},
            "rule": {"rule_id": "source.only.rule"},
            "conclusion": {"status": "partial", "depends_on": ["source.only.rule"]},
        }
    }
    value = execution_evidence((COMPATIBILITY_INDEX,), {}, payload, "origin")
    graph = EvidenceGraph.model_validate(value["graph"])
    assert graph.runtime_method_ids == ("keep_unresolved.v1",)
    assert "/basis/conclusion" in graph.resolved_rule_dependencies
    assert any(
        edge.relation == "rule_input_witness"
        and edge.source == "result:/basis/rule"
        and edge.target == "result:/basis/conclusion"
        for edge in graph.edges
    )


def test_all_in_scope_catalog_methods_have_real_sources_and_exclusions_stay_explicit():
    root = Path(__file__).resolve().parents[1]
    for spec in CATALOG:
        if spec.key in EXCLUDED_TOOLS:
            assert not spec.methods
            continue
        assert spec.methods, spec.key
        assert len({m.method_id for m in spec.methods}) == len(spec.methods)
        for method in spec.methods:
            for path in (*method.implementation_refs, *method.source_refs):
                assert (root / path).is_file(), (spec.key, path)
            assert (
                method.as_manifest()["validation_scope"]["real_world_validity"]
                == "not_established"
            )


def test_evidence_and_unknown_error_budget_are_equal_on_real_transports(
    monkeypatch, capsys
):
    import fatebridge.api as api
    from fatebridge.cli import run
    from fatebridge.mcp_server import app

    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == "qimen")
    inputs = REST_POST_CASES[spec.rest_path]()
    response = TestClient(api.app).post(spec.rest_path, json=inputs)
    args = [spec.tool_name, "--response-char-limit", "0"]
    for key, value in inputs.items():
        if isinstance(value, list):
            args += ["--" + key.replace("_", "-"), *map(str, value)]
            continue
        args += [
            "--" + key.replace("_", "-"),
            (
                json.dumps(value)
                if isinstance(value, dict)
                else str(value).lower() if isinstance(value, bool) else str(value)
            ),
        ]
    assert run(args) == 0
    local = json.loads(capsys.readouterr().out)

    async def call():
        async with Client(app) as client:
            return await client.call_tool(
                spec.tool_name, {**inputs, "response_char_limit": 0}
            )

    protocol = asyncio.run(call())
    assert response.status_code == 200 and not protocol.is_error
    evidence = [
        r["run_metadata"]["calculation_evidence"]
        for r in (response.json(), local, protocol.structured_content)
    ]
    assert evidence[0] == evidence[1] == evidence[2]
    graph = EvidenceGraph.model_validate(evidence[0]["graph"])
    environment_node = next(n for n in graph.nodes if n.kind == "environment")
    for value in (response.json(), local, protocol.structured_content):
        runtime = value["run_metadata"]["runtime"]
        assert environment_node.value_sha256 == digest(runtime)
        assert environment_node.value_sha256 != runtime["environment_sha256"]
    assert graph.unresolved_rule_dependencies
    assert evidence[0]["error_budget"]["output_error_bounds"] is None


def test_large_evidence_remains_available_in_same_run(monkeypatch, tmp_path):
    import fatebridge.application.result_delivery as delivery
    from fatebridge.application.projection import project_fields
    from fatebridge.application.result_delivery import ResultStore, bound_response

    monkeypatch.setattr(delivery, "RESULT_STORE", ResultStore(tmp_path))
    spec = next(s for s in CATALOG if s.key == "qimen")
    request = spec.request_model.model_validate(REST_POST_CASES[spec.rest_path]())
    result = execute_tool(spec, request)
    selected = project_fields(
        result,
        fields=["qimen.dun_type", "qimen.ju_number"],
        strict_fields=True,
    )
    bounded = bound_response(selected, 4096)
    assert len(json.dumps(bounded, ensure_ascii=False, separators=(",", ":"))) <= 4096
    assert (
        "run_metadata.calculation_evidence"
        in bounded["result_delivery"]["deferred_fields"]
    )
    restored = delivery.RESULT_STORE.page(
        bounded["result_delivery"]["result_id"],
        path="run_metadata.calculation_evidence",
    )
    pieces = [restored["text"]]
    while restored["next_offset"] is not None:
        restored = delivery.RESULT_STORE.page(
            bounded["result_delivery"]["result_id"],
            offset=restored["next_offset"],
            path="run_metadata.calculation_evidence",
        )
        pieces.append(restored["text"])
    evidence = json.loads("".join(pieces))
    assert evidence == result["run_metadata"]["calculation_evidence"]
    assert digest(evidence) == bounded["run_metadata"]["calculation_evidence"]["sha256"]
    assert (
        result["run_metadata"]["calculation_evidence"]["graph"][
            "business_output_sha256"
        ]
        == result["run_metadata"]["business_output_sha256"]
    )
