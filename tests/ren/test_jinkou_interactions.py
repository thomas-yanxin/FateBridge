"""Classical order, simultaneous relations and faithful three-port delivery."""

import copy
import hashlib
import importlib.util
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.application.examples import evidence_views
from fatebridge.core.metaphysics.jinkou_interactions import position_interactions
from fatebridge.core.metaphysics.jinkou_strength import internal_strength
from fatebridge.core.output_jinkou_interactions import JinkouPositionInteractions
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_jinkou_analysis
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.mcp_result_delivery import assert_same_run_receipt
from tests.support.transports import AS_OF, SPECS, business, rest, surface_calls

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "jinkou_interactions_audit", ROOT / "scripts/ren/audit_jinkou_interactions.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()
PAYLOAD = dict(
    analysis_year=2026,
    analysis_month=2,
    analysis_day=20,
    analysis_hour=6,
    analysis_timezone="Asia/Shanghai",
    use_true_solar_time=False,
    di_fen="子",
)


def rows(text):
    return AUDIT.symbolic_rows(REFERENCE, list(text))


def test_frozen_clauses_and_expansions_do_not_open_full_acceptance():
    result = AUDIT.audit()
    assert result["definition_matches"] == result["source_clause_count"] == 14
    assert (
        result["synthetic_probe_matches"]
        == len(result["synthetic_clause_probes"])
        == 30
    )
    assert result["synthetic_combinations"] == 625
    assert result["derived_rule_checks"] == result["derived_rule_matches"] == 8750
    assert result["derived_pair_checks"] == result["derived_pair_matches"] == 3750
    assert not result["failures"] and result["selected_clause_checks_passed"]
    assert result["goal_complete"] is result["classical_acceptance_passed"] is False
    assert result["new_historical_examples"] == result["new_real_world_outcomes"] == 0


@pytest.mark.parametrize("change", ["edit", "missing", "extra"])
def test_source_inventory_cannot_remove_an_uncomfortable_condition(tmp_path, change):
    target = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, target)
    if change == "edit":
        p = target / "reference.json"
        data = json.loads(p.read_text())
        data["rules"][2]["quantifier"] = "any"
        p.write_text(json.dumps(data))
    elif change == "missing":
        (target / "source-pages.pdf").unlink()
    else:
        (target / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen interaction"):
        AUDIT.reference(target)


def test_deleted_rule_still_keeps_all_8750_required_comparisons(monkeypatch):
    import fatebridge.core.metaphysics.jinkou_interactions as module

    original = module.position_interactions

    def incomplete(subject):
        result = original(subject)
        result["rule_evaluations"].pop()
        return result

    monkeypatch.setattr(module, "position_interactions", incomplete)
    result = AUDIT.audit()
    assert not result["selected_clause_checks_passed"]
    assert result["derived_rule_checks"] == 8750
    assert result["derived_rule_matches"] == 8125
    assert result["failures"]


def test_generation_chain_does_not_remove_separated_controls():
    actual = position_interactions(rows("木火土金"))
    assert "top_down_generation" in actual["matched_rule_ids"]
    assert (
        actual["has_any_control"] and internal_strength(rows("木火土金"))["has_control"]
    )
    assert [
        (p["upper_position"], p["lower_position"])
        for p in actual["pairs"]
        if p["relation"] == "上克下"
    ] == [("人元", "将神"), ("贵神", "地分")]
    heju = position_interactions(rows("木火木水"))
    assert "heju" in heju["matched_rule_ids"] and heju["has_any_control"]
    incomplete = position_interactions(rows("木火木金"))
    assert "heju" not in incomplete["matched_rule_ids"]


@pytest.mark.parametrize("elements", ["木土金水", "土木金水"])
def test_outer_battle_accepts_either_control_direction(elements):
    result = position_interactions(rows(elements))
    battle = next(r for r in result["rule_evaluations"] if r["id"] == "outer_battle")
    assert (
        battle["matched"] and sum(c["matched"] for c in battle["condition_checks"]) == 1
    )


@pytest.mark.parametrize("bad", ["missing", "duplicate", "reversed", "phase"])
def test_invalid_position_inputs_are_rejected(bad):
    subject = rows("木火土金")
    if bad == "missing":
        subject.pop()
    elif bad == "duplicate":
        subject[1]["label"] = "人元"
    elif bad == "reversed":
        subject.reverse()
    else:
        subject[0]["element"] = "甲"
    with pytest.raises(ValueError):
        position_interactions(subject)


@pytest.mark.parametrize("project", [False, True])
def test_real_board_has_both_generation_and_control_on_all_ports(
    project, surface_calls
):
    spec = SPECS["jinkou"]
    fields = [
        "jinkou.position_interactions",
        "jinkou.rows",
        "jinkou.internal_strength",
        "jinkou.use_evidence",
        "jinkou.ruleset",
    ]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options.update(fields=fields, strict_fields=True, include_snapshot_text=False)
    http, protocol, code, cli = surface_calls(
        spec, PAYLOAD, params=params, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for body in (http.json(), protocol.structured_content, cli):
        spec.output_model.model_validate(body)
        board = body["jinkou"]
        assert [r["element"] for r in board["rows"]] == list("火土金水")
        interaction = board["position_interactions"]
        assert "top_down_generation" in interaction["matched_rule_ids"]
        assert (
            interaction["has_any_control"] and board["internal_strength"]["has_control"]
        )
        assert not board["use_evidence"]["no_control_principle_applies"]
        assert board["use_evidence"]["comprehensive_position"] is None
        assert not board["internal_strength"]["source_evidence"][
            "daily_five_states_adjudicated"
        ]
        assert board["ruleset"]["version"] == "1.16.0"
        if not project:
            assert "位置结构：自上次第生下，命中" in body["snapshot_text"]
            assert "四位任意位置有克：是" in body["snapshot_text"]
            trace = next(
                t
                for t in board["rule_trace"]
                if t["rule_id"] == "jinkou.position_interactions"
            )
            assert trace["result"] == interaction
    assert "jinkou.position_interactions" in evidence_views(spec)["core"]["fields"]


FAULTS = [
    "full_claim",
    "numeric_claim",
    "duplicate_rule",
    "missing_pair",
    "flip_match",
    "summary",
    "control",
    "adjacency",
    "order",
]


def corrupt(data, name):
    result = copy.deepcopy(data)
    if name == "full_claim":
        result["complete_classical_conformance"] = True
    elif name == "numeric_claim":
        result["complete_classical_conformance"] = 0
    elif name == "duplicate_rule":
        result["rule_evaluations"][0]["id"] = result["rule_evaluations"][1]["id"]
    elif name == "missing_pair":
        result["pairs"].pop()
    elif name == "flip_match":
        result["rule_evaluations"][0]["matched"] = not result["rule_evaluations"][0][
            "matched"
        ]
    elif name == "summary":
        result["matched_rule_ids"] = []
    elif name == "control":
        result["has_any_control"] = not result["has_any_control"]
    elif name == "adjacency":
        result["pairs"][0]["adjacent"] = False
    else:
        result["position_order"].reverse()
    return result


@pytest.mark.parametrize("fault", FAULTS)
@pytest.mark.parametrize("project", [False, True])
def test_complete_business_envelope_rejects_corruption_before_projection(
    fault, project, monkeypatch, surface_calls
):
    spec = SPECS["jinkou"]
    valid = calculate_jinkou_analysis(**PAYLOAD)
    execution.validate_output(spec, valid)
    bad = copy.deepcopy(valid)
    bad["jinkou"]["position_interactions"] = corrupt(
        bad["jinkou"]["position_interactions"], fault
    )
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(bad)
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == spec.key:
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(bad), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = dict(as_of=AS_OF, response_char_limit=0)
    options = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        options.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http, protocol, code, out = surface_calls(
        spec, PAYLOAD, params=params, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert out["error_code"] == "internal_error"


@pytest.mark.parametrize(
    "field",
    [
        "pairs",
        "rule_evaluations",
        "matched_rule_ids",
        "has_any_control",
        "complete_classical_conformance",
    ],
)
def test_sparse_projections_preserve_complete_arrays_and_false(field, surface_calls):
    spec = SPECS["jinkou"]
    path = "jinkou.position_interactions." + field
    http, protocol, code, cli = surface_calls(
        spec,
        PAYLOAD,
        params=dict(
            as_of=AS_OF,
            fields=path,
            strict_fields="true",
            include_snapshot_text="false",
            response_char_limit=0,
        ),
        options={
            "fields": [path],
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=[
            "--response-char-limit",
            "0",
            "--fields",
            path,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    spec.output_model.model_validate(cli)


def test_selected_four_position_section_and_same_run_claims_are_faithful(surface_calls):
    spec = SPECS["jinkou"]
    payload = {**PAYLOAD, "selected_sections": ["金口诀四位"]}
    http, protocol, code, cli = surface_calls(
        spec,
        payload,
        params=dict(as_of=AS_OF, response_char_limit=0),
        flags=["--response-char-limit", "0"],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    exported = cli["snapshot_export"]
    assert exported["selected_sections"] == ["金口诀四位"]
    assert "[起盘信息]" not in exported["export_text"]
    assert "位置结构：自上次第生下，命中" in exported["export_text"]
    assert "四位任意位置有克：是" in exported["export_text"]
    receipt = cli["run_metadata"]
    claim = CalculationClaim(
        path="jinkou.position_interactions.has_any_control",
        value=True,
        run_id=receipt["run_id"],
    )
    assert (
        verify_calculation_claims(cli, [claim])["status"] == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(cli, [claim.model_copy(update={"value": False})])[
            "status"
        ]
        == "rejected"
    )


def test_whole_rule_output_models_accept_all_625_phase_combinations():
    from itertools import product

    for phases in product("木火土金水", repeat=4):
        JinkouPositionInteractions.model_validate(
            position_interactions(rows("".join(phases)))
        )


@pytest.mark.asyncio
async def test_published_first_view_recovers_all_relations_from_the_same_run():
    contract = json.loads((ROOT / "docs/contracts/jinkou.json").read_text())
    async with Client(create_mcp_app()) as client:
        response = await client.call_tool(
            "jinkou",
            {
                **PAYLOAD,
                **contract["first_view"],
                "as_of": AS_OF,
                "response_char_limit": 6000,
            },
        )
        assert not response.is_error
        inline = response.structured_content
        reference = inline["result_delivery"]
        pieces = []
        uri = reference["first_page_uri"]
        while uri:
            page = json.loads((await client.read_resource(uri))[0].text)
            pieces.append(page["text"])
            uri = page["next_uri"]
    assert len(pieces) > 1
    text = "".join(pieces)
    assert hashlib.sha256(text.encode()).hexdigest() == reference["sha256"]
    complete = json.loads(text)
    assert_same_run_receipt(
        inline["run_metadata"],
        complete["run_metadata"],
        deferred_fields=reference["deferred_fields"],
    )
    actual = complete["jinkou"]["position_interactions"]
    assert len(actual["pairs"]) == 6 and len(actual["rule_evaluations"]) == 14
    assert (
        "top_down_generation" in actual["matched_rule_ids"]
        and actual["has_any_control"]
    )
