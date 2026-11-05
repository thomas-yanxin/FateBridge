"""Preserve pending/partial events and physical carrier scope across entries."""

import asyncio
import json
from copy import deepcopy
from dataclasses import replace

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.application.examples import suggested_fields
from fatebridge.core.classical_passage import build_passage_evidence
from fatebridge.core.output_passage_relations import PassageRelationContext
from fatebridge.core.passage_relations import build_passage_relation_context
from tests.bazi.test_bazi_complete_anchors import TOOLS, base, projection
from tests.integration.test_result_delivery import reconstruct
from tests.integration.test_result_delivery import store as _store_fixture
from tests.support.transports import AS_OF, SPECS, business, call_cli, native
from tests.support.transports import rest as _rest_fixture

rest = _rest_fixture
store = _store_fixture


def controlled(assessment=None):
    # Synthetic supplied receipt; no civil birth instant or strength claim.
    pillars = dict(
        year=("甲", "辰"), month=("己", "卯"), day=("庚", "申"), hour=("乙", "酉")
    )
    if assessment is None:
        assessment = {
            "hidden_stem_ledger": [
                {
                    "pillar": "month",
                    "stem": "乙",
                    "element": "木",
                    "remaining_mass": 0.0,
                },
                {"pillar": "day", "stem": "庚", "element": "金", "remaining_mass": 1.0},
            ],
            "relations": [
                {
                    "kind": "天干合",
                    "positions": ["year", "month"],
                    "status": "day_master_or_contested_review",
                },
                {
                    "kind": "六冲",
                    "positions": ["month", "hour"],
                    "status": "active",
                    "root_multipliers": {"month": 0.0},
                },
            ],
        }
    passage = build_passage_evidence(pillars, assessment)
    return build_passage_relation_context(passage, assessment)


def test_visible_combination_does_not_bind_hidden_stems_and_zero_remaining_root_keeps_context():
    c = controlled()
    PassageRelationContext.model_validate(c)
    nodes = {n["node_id"]: n for n in c["nodes"]}
    assert nodes["year:stem:甲"]["visible_relation_refs"] == ["assessment.relations:0"]
    assert nodes["year:stem:甲"]["root_carrier_positions"] == ["month"]
    assert nodes["year:stem:甲"]["root_relation_refs"] == ["assessment.relations:1"]
    assert nodes["month:hidden:乙"]["visible_relation_refs"] == []
    assert nodes["month:hidden:乙"]["root_relation_refs"] == ["assessment.relations:1"]
    assert nodes["year:hidden:戊"]["root_relation_refs"] == []
    assert c["events"][1]["receipt"]["root_multipliers"]["month"] == 0.0
    assert c["effective_passage"] == "not_adjudicated"


def test_missing_and_supplied_empty_receipts_are_distinct_and_partial_reads_remain_valid():
    missing = controlled({})
    empty = controlled({"relations": [], "hidden_stem_ledger": []})
    assert missing["events"] is None and missing["source_relation_count"] is None
    assert empty["events"] == [] and empty["source_relation_count"] == 0
    assert missing["nodes"][0]["root_carrier_positions"] is None
    assert empty["nodes"][0]["root_carrier_positions"] == []
    for c in (missing, empty, controlled()):
        PassageRelationContext.model_validate(c)
        for key, value in c.items():
            PassageRelationContext.model_validate({key: value})
        for n in c["nodes"]:
            for key in n:
                PassageRelationContext.model_validate(
                    {"nodes": [{"node_id": n["node_id"], key: n[key]}]}
                )


def test_unknown_event_kind_is_retained_without_guessing_plane_or_effect():
    c = controlled(
        {
            "relations": [
                {
                    "kind": "未来未分类关系",
                    "positions": ["year", "month"],
                    "status": "pending_new_scope",
                }
            ]
        }
    )
    PassageRelationContext.model_validate(c)
    assert c["events"][0]["plane"] == "unclassified"
    assert c["unclassified_event_refs"] == ["assessment.relations:0"]
    assert c["effective_passage"] == "not_adjudicated"


def test_returned_receipts_do_not_share_mutable_event_objects_with_assessment():
    a = {
        "relations": [
            {
                "kind": "六冲",
                "positions": ["month", "hour"],
                "status": "active",
                "nested": {"value": 0},
            }
        ]
    }
    original = deepcopy(a)
    c = controlled(a)
    c["events"][0]["receipt"]["nested"]["value"] = 1
    assert a == original


@pytest.mark.parametrize("fault", range(11))
def test_suppressed_pending_conditions_wrong_planes_and_invented_effects_are_rejected(
    fault,
):
    c = controlled()
    if fault == 0:
        c["events"][0]["plane"] = "branch"
    elif fault == 1:
        c["events"].append(deepcopy(c["events"][0]))
    elif fault == 2:
        c["source_relation_count"] += 1
    elif fault == 3:
        c["events"][0]["id"] = "assessment.relations:9"
    elif fault == 4:
        c["nodes"][0]["visible_relation_refs"] = []
    elif fault == 5:
        c["nodes"][0]["root_relation_refs"] = []
    elif fault == 6:
        c["nodes"][1]["visible_relation_refs"] = ["assessment.relations:0"]
    elif fault == 7:
        c["nodes"][1]["root_carrier_positions"] = ["month"]
    elif fault == 8:
        c["effective_passage"] = "effective"
    elif fault == 9:
        c["relations_status"] = "not_supplied"
    else:
        c["nodes"].append(deepcopy(c["nodes"][0]))
    with pytest.raises(ValidationError):
        PassageRelationContext.model_validate(c)


@pytest.mark.parametrize("tool", TOOLS)
def test_all_actual_surfaces_return_same_relation_context_and_partial_schema(
    tool, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    fields = suggested_fields(spec, view="passage_relations")
    payload = base(tool)["arguments"]
    opts = dict(
        as_of=AS_OF,
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    protocol = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert not protocol.is_error and code == 0
    assert business(protocol.structured_content) == business(cli)
    if spec.rest_path is not None:
        http = rest.post(spec.rest_path, json=payload, params=opts)
        assert http.status_code == 200 and business(http.json()) == business(cli)
    else:
        assert tool == "analyze_destiny"
    spec.output_model.model_validate(cli)


@pytest.mark.parametrize("tool", TOOLS)
def test_new_version_missing_context_fails_before_unrelated_projection(
    tool, rest, tmp_path, capsys, monkeypatch
):
    spec = SPECS[tool]
    original = execution.execute_spec

    def corrupt(actual, parsed):
        if actual.key == tool:
            function, args, kwargs = actual.bind(parsed)

            def missing():
                result = function(*args, **kwargs)
                if tool == "analyze_destiny":
                    chain = result["structure_profile"]["evidence_chain"]
                elif tool == "bazi_birth":
                    chain = result["bazi_birth"]["structure_profile"]["evidence_chain"]
                else:
                    chain = result[tool.removeprefix("bazi_") + "_analysis"][
                        "evidence_chain"
                    ]
                assert chain["method_id"] == "bazi_position_prerequisites_v2"
                del chain["classical_passage_relations"]
                return result

            actual = replace(actual, bind=lambda _: (missing, (), {}))
        return original(actual, parsed)

    monkeypatch.setattr(execution, "execute_spec", corrupt)
    payload = base(tool)["arguments"]
    path = projection(tool)
    opts = dict(
        as_of=AS_OF, fields=[path], strict_fields=True, include_snapshot_text=False
    )
    protocol = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--fields", path, "--strict-fields", "true"],
    )
    assert protocol.is_error and code == 1
    assert (
        protocol.structured_content["error_code"]
        == cli["error_code"]
        == "internal_error"
    )
    if spec.rest_path is not None:
        http = rest.post(spec.rest_path, json=payload, params=opts)
        assert http.status_code == 500 and http.json()["error_code"] == "internal_error"


@pytest.mark.parametrize("tool", TOOLS)
def test_small_budget_restores_exact_same_run_relation_context_without_recalculation(
    tool, store
):
    spec = SPECS[tool]
    fields = suggested_fields(spec, view="passage_relations")
    result = asyncio.run(
        native(
            spec,
            base(tool)["arguments"],
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=4096,
        )
    )
    assert not result.is_error
    first = result.structured_content
    assert len(json.dumps(first, ensure_ascii=False, separators=(",", ":"))) <= 4096
    ref = first["result_delivery"]
    complete = reconstruct(store, ref["result_id"])
    assert complete["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
    context = complete
    for part in fields[-1].split("."):
        context = context[part]
    PassageRelationContext.model_validate(context)
    assert context["effective_passage"] == "not_adjudicated"
    assert "ephemeris" in complete["run_metadata"]["runtime"]
