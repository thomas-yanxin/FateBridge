"""Directional source names, bounded example classifications and real transports."""

import asyncio
import json
import shutil
from copy import deepcopy
from itertools import product
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.qimen_gate_relations import (
    describe_gate_relations,
    gate_palace_relation,
)
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation import qimen_gate_relations as gate_audit
from fatebridge.validation.claims import CalculationClaim
from fatebridge.validation.qimen import verify_qimen_pattern_quotes
from fatebridge.validation.qimen_gate_relations import audit_gate_relations

BUNDLE = Path(__file__).parent / "fixtures/qimen_classical_v11"
REF = json.loads((BUNDLE / "sources-and-gate-relations.json").read_text())
DOORS = {
    "休门": "水",
    "生门": "土",
    "伤门": "木",
    "杜门": "木",
    "景门": "火",
    "死门": "土",
    "惊门": "金",
    "开门": "金",
}
PALACES = {
    "坎": "水",
    "坤": "土",
    "震": "木",
    "巽": "木",
    "乾": "金",
    "兑": "金",
    "艮": "土",
    "离": "火",
}
# Explicit directional matrix, in 木火土金水 order. These are internal
# exhaustive checks, not 25 independently printed source observations.
MATRIX = {
    "木": (
        "same_element",
        "door_generates_palace",
        "door_controls_palace",
        "palace_controls_door",
        "palace_generates_door",
    ),
    "火": (
        "palace_generates_door",
        "same_element",
        "door_generates_palace",
        "door_controls_palace",
        "palace_controls_door",
    ),
    "土": (
        "palace_controls_door",
        "palace_generates_door",
        "same_element",
        "door_generates_palace",
        "door_controls_palace",
    ),
    "金": (
        "door_controls_palace",
        "palace_controls_door",
        "palace_generates_door",
        "same_element",
        "door_generates_palace",
    ),
    "水": (
        "door_generates_palace",
        "door_controls_palace",
        "palace_controls_door",
        "palace_generates_door",
        "same_element",
    ),
}


def test_frozen_paragraph_keeps_four_names_and_eleven_literal_pairs():
    r = audit_gate_relations(BUNDLE)
    assert r["disagreements"] == []
    assert r["source_relation_definition_count"] == r["derived_witness_count"] == 4
    assert (
        r["literal_pair_observation_count"] == r["matched_pair_observation_count"] == 11
    )
    assert r["printed_clause_group_count"] == 7
    assert not r["same_element_source_name_added"]
    assert not r["whole_book_conformance_established"]
    assert r["finite_evidence_scope_probes"] == 64
    assert not r["source_labels_used_as_outcome_judgments"]


@pytest.mark.parametrize(
    "corruption", ["same_name", "outcome", "extra_printed_example"]
)
def test_auditor_checks_real_outputs_instead_of_declaring_limits(
    monkeypatch, corruption
):
    original = gate_audit.gate_palace_relation

    def altered(door, trigram):
        e = original(door, trigram)
        if corruption == "same_name" and e["relation"] == "same_element":
            e["prose_label"] = "比和"
        elif corruption == "outcome":
            e["prose_label_is_outcome_judgment"] = True
        elif corruption == "extra_printed_example" and (door, trigram) == (
            "景门",
            "乾",
        ):
            e["printed_example"] = {
                "category": "吉门被迫",
                "scope": "literal_door_palace_observation_not_global_door_classification",
                "outcome_inference_allowed": False,
            }
        return e

    monkeypatch.setattr(gate_audit, "gate_palace_relation", altered)
    report = gate_audit.audit_gate_relations(BUNDLE)
    assert report["disagreements"]
    if corruption == "same_name":
        assert report["same_element_source_name_added"]
    elif corruption == "outcome":
        assert report["source_labels_used_as_outcome_judgments"]
    else:
        assert any(
            e["kind"] == "unsupported_printed_example_scope"
            for e in report["disagreements"]
        )


@pytest.mark.parametrize("door,trigram", list(product(DOORS, PALACES)))
def test_all_64_pairs_preserve_direction_and_independent_naming(door, trigram):
    r = gate_palace_relation(door, trigram)
    expected = MATRIX[DOORS[door]]["木火土金水".index(PALACES[trigram])]
    assert (r["door_element"], r["palace_element"]) == (DOORS[door], PALACES[trigram])
    assert r["relation"] == expected
    assert r["verse_door_pressure"] is (expected == "door_controls_palace")
    assert r["palace_restricts_door"] is (expected == "palace_controls_door")
    labels = {d["relation"]: d["label"] for d in REF["definitions"]}
    assert r["prose_label"] == labels.get(expected)
    assert (
        not r["prose_label_is_outcome_judgment"] and not r["outcome_inference_allowed"]
    )


def test_false_verse_pressure_does_not_erase_prose_xiong_pressure():
    r = gate_palace_relation("开门", "离")
    assert r["verse_door_pressure"] is False and r["prose_label"] == "凶迫"
    assert r["palace_restricts_door"] is True


def test_ji_pressure_does_not_become_good_outcome_or_global_jing_classification():
    r = gate_palace_relation("景门", "兑")
    assert r["prose_label"] == "吉迫"
    assert r["printed_example"]["category"] == "吉门被迫"
    assert r["printed_example"]["traditional_statement"] == "吉事不成、不吉"
    assert not r["printed_example"]["outcome_inference_allowed"]
    assert gate_palace_relation("景门", "乾")["printed_example"] is None
    assert gate_palace_relation("开门", "乾")["prose_label"] is None


def test_returned_profile_does_not_mutate_labels():
    p = describe_gate_relations()
    p["prose_labels_by_relation"]["door_controls_palace"] = "吉利"
    assert (
        describe_gate_relations()["prose_labels_by_relation"]["door_controls_palace"]
        == "吉迫"
    )


@pytest.mark.parametrize(
    "door,trigram",
    [("中门", "中"), ("开门", "中"), ("开", "震"), (None, "震"), ("开门", "东")],
)
def test_invalid_or_missing_plane_does_not_become_no_pressure(door, trigram):
    with pytest.raises(ValueError):
        gate_palace_relation(door, trigram)


@pytest.mark.parametrize(
    "mutation",
    [
        "drop_jing",
        "drop_generation",
        "rewrite_verse",
        "name_same",
        "claim_outcome",
        "pdf",
    ],
)
def test_source_audit_cannot_shed_awkward_names_or_examples(tmp_path, mutation):
    target = tmp_path / "bundle"
    shutil.copytree(BUNDLE, target)
    path = target / "sources-and-gate-relations.json"
    ref = json.loads(path.read_text())
    if mutation == "drop_jing":
        ref["examples"] = [r for r in ref["examples"] if r["door"] != "景门"]
    elif mutation == "drop_generation":
        ref["definitions"].pop()
    elif mutation == "rewrite_verse":
        ref["verse_clause"] = "宫克门也一律门迫"
    elif mutation == "name_same":
        ref["same_element_named_in_selected_paragraph"] = True
    elif mutation == "claim_outcome":
        ref["label_is_real_world_outcome"] = True
    else:
        (target / "siku-page34.pdf").write_bytes(b"changed")
    path.write_text(json.dumps(ref))
    with pytest.raises(ValueError):
        audit_gate_relations(target)


@pytest.mark.parametrize(
    "change", ["direction", "label", "scope", "outcome", "prose_judgment"]
)
def test_whole_quote_rejects_direction_reversal_or_auspicious_rebranding(change):
    spec = next(s for s in CATALOG if s.tool_name == "qimen")
    payload = execute_tool(
        spec,
        spec.request_model.model_validate(
            {
                "analysis_year": 2026,
                "analysis_month": 1,
                "analysis_day": 15,
                "analysis_hour": 16,
                "analysis_timezone": "Asia/Hong_Kong",
                "use_true_solar_time": False,
                "qimen_options": {"ju_method": "chaibu"},
            }
        ),
        options=ExecutionOptions(as_of="2026-10-22T12:00:00+08:00"),
    )
    index, pattern = next(
        (i, p)
        for i, p in enumerate(payload["qimen"]["patterns"])
        if p["rule_id"] == "door_pressure"
    )
    claim = CalculationClaim(
        path=f"qimen.patterns.{index}",
        value=deepcopy(pattern),
        run_id=payload["run_metadata"]["run_id"],
        business_output_sha256=payload["run_metadata"]["business_output_sha256"],
    )
    assert (
        verify_qimen_pattern_quotes(payload, [claim])["status"]
        == "verified_structured_pattern_quotes"
    )
    e = claim.value["qualification"]["door_palace_evidence"]
    if change == "direction":
        e["relation"] = "palace_controls_door"
    elif change == "label":
        e["prose_label"] = "吉利"
    elif change == "scope":
        e.pop("interpretation_limit")
    elif change == "outcome":
        e["outcome_inference_allowed"] = True
    else:
        e["prose_label_is_outcome_judgment"] = True
    assert verify_qimen_pattern_quotes(payload, [claim])["status"] == "rejected"


@pytest.mark.parametrize("hour", [6, 12])
def test_gate_evidence_and_snapshot_agree_in_real_transports(monkeypatch, capsys, hour):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = ["qimen", "snapshot_text"]
    payload = dict(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=5,
        analysis_hour=hour,
        analysis_timezone="Asia/Hong_Kong",
        use_true_solar_time=False,
        qimen_options={"ju_method": "chaibu"},
    )
    controls = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        response_char_limit=0,
    )
    response = TestClient(api.app).post(
        "/api/cn/qimen",
        json=payload,
        params=[
            ("as_of", controls["as_of"]),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "qimen", {**payload, **controls}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert not native.is_error, native
    capsys.readouterr()
    code = run(
        [
            "qimen",
            "--analysis-year",
            "2026",
            "--analysis-month",
            "1",
            "--analysis-day",
            "5",
            "--analysis-hour",
            str(hour),
            "--analysis-timezone",
            "Asia/Hong_Kong",
            "--no-use-true-solar-time",
            "--qimen-options",
            json.dumps(payload["qimen_options"]),
            "--as-of",
            controls["as_of"],
            "--strict-fields",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert code == 0 and response.status_code == 200, (cli, response.text)
    bodies = [
        {k: v for k, v in b.items() if k != "run_metadata"}
        for b in [response.json(), native.structured_content, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    b = bodies[0]
    for p in b["qimen"]["palaces"]:
        if p["trigram"] == "中":
            continue
        e = p["evidence"]
        r = e["door_palace_relation"]
        assert e["door_pressure"] == r["verse_door_pressure"]
        assert e["palace_restricts_door"] == r["palace_restricts_door"]
        assert not r["prose_label_is_outcome_judgment"]
    assert "关系名不作现实吉凶结论" in b["snapshot_text"]
    assert "门宫生克" in b["snapshot_text"]
