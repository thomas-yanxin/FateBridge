"""Declared source scenarios gate clauses, not geometry or real outcomes."""

import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

FIXTURE = Path(__file__).parent / "fixtures/meihua_matter_scenario_v1"
CASES = json.loads((FIXTURE / "cases.json").read_text())["cases"]
TIME = {
    "analysis_year": 2026,
    "analysis_month": 10,
    "analysis_day": 22,
    "analysis_hour": 12,
    "analysis_timezone": "Asia/Shanghai",
}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_manual_scenario_conditions(case):
    plain = calculate_meihua_cast(casting=case["casting"])
    assert plain["meihua"]["body_trigram"]["name"] == case["body"]
    assert [r["relation"] for r in plain["meihua"]["stage_relations"]] == case[
        "stage_relations"
    ]
    out = (
        calculate_meihua_cast(casting=case["casting"], matter_scenario=case["scenario"])
        if case["scenario"] is not None
        else plain
    )
    assert out["meihua"] == plain["meihua"]
    layer = out["interpretation"]["stage_emphasis"]
    assert layer["matter_scenario"] == (case["scenario"] or "not_collected")
    # Preserve the frozen historical answers; only the predeclared missing-
    # scenario / impossible-structure null -> false correction is applied.
    generation, control = case["generation_roles"], case["control_roles"]
    relative_expected = list(case["relative_clause_applies"])
    mixed_expected = case["mixed_clause_applies"]
    scenario_expected = list(case["scenario_clause_applies"])
    if case["scenario"] is None:
        relative_expected = [
            None if "use" in generation else False,
            (
                None
                if any(r in generation for r in ["body_mutual", "use_mutual"])
                else False
            ),
            None if "changed_use" in generation else False,
        ]
        mixed_expected = None if generation and control else False
        scenario_expected = [
            None if not generation and control else False,
            None if generation else False,
            None if not generation else False,
        ]
    assert [
        r["full_clause_applies"] for r in layer["relative_generation_clauses"]
    ] == relative_expected
    assert layer["mixed_generation_control"]["full_clause_applies"] is mixed_expected
    assert [
        r["full_clause_applies"] for r in layer["scenario_clauses"]
    ] == scenario_expected
    assert (
        layer["event_time"]
        is layer["real_outcome"]
        is layer["net_effect_weight"]
        is None
    )
    if case["scenario"] is not None:
        decl = layer["scenario_declaration"]
        assert decl["status"] == "caller_declared_unverified"
        assert decl["fact_path"] == "input_normalized.matter_scenario"
        assert out["input_normalized"]["matter_scenario"] == case["scenario"]
        assert "此项未采集" not in layer["summary"]


def test_frozen_reference_bytes_and_reused_diagram_scope():
    m = json.loads((FIXTURE / "manifest.json").read_text())
    assert m["request_field_not_present"] is True
    assert m["production_generated_expected_values"] is False
    for name, digest in m["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("value", [True, 0, "", "bad", "favorable", {}, []])
def test_unknown_scenario_values_are_rejected(value):
    with pytest.raises(ValidationError):
        MeihuaCastRequest.model_validate(
            {"casting": CASES[0]["casting"], "matter_scenario": value}
        )


@pytest.mark.parametrize("scenario", ["favorable_matter", "unfavorable_matter"])
def test_weather_cannot_receive_human_matter_scenario(scenario):
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"],
        interpretation_topic="weather",
        matter_scenario=scenario,
    )
    assert out["error_code"] == "validation_error"


def test_negative_question_words_and_topic_do_not_replace_declaration():
    for topic in ["general", "planning", "reputation", "wealth", "transaction"]:
        out = calculate_meihua_cast(
            casting=CASES[0]["casting"],
            interpretation_topic=topic,
            question="我担心失败，也盼望成功，请别替我选所问类别",
        )
        layer = out["interpretation"]["stage_emphasis"]
        assert layer["matter_scenario"] == "not_collected"
        for clause in layer["scenario_clauses"]:
            assert clause["scenario_condition_met"] is None
            assert clause["full_clause_applies"] is (
                None if clause["structural_condition_met"] else False
            )


def test_candidate_scenario_shared_but_relation_and_clause_match_not_shared():
    cast = {
        "method": "sound_groups",
        "first_count": 12,
        "second_count": 5,
        "hour_branch": "酉",
    }
    out = calculate_meihua_cast(casting=cast, matter_scenario="unfavorable_matter")
    rows = out["interpretation"]["casting_readings"]
    assert [r["stage_emphasis"]["generation_roles"] for r in rows] == [
        ["changed_use"],
        [],
    ]
    assert [
        [r["full_clause_applies"] for r in c["stage_emphasis"]["scenario_clauses"]]
        for c in rows
    ] == [[False, True, False], [False, False, True]]
    assert all(
        r["stage_emphasis"]["scenario_declaration"]["fact_path"]
        == "input_normalized.matter_scenario"
        for r in rows
    )


def test_support_under_control_keeps_both_clause_and_existing_qualification():
    out = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "011101", "moving_line": 1},
        matter_scenario="favorable_matter",
    )
    layer = out["interpretation"]["stage_emphasis"]
    assert layer["relative_generation_clauses"][0]["full_clause_applies"] is True
    assert (
        len(
            layer["roles"][0]["countercontrol_qualification"][
                "incoming_controller_roles"
            ]
        )
        == 3
    )
    assert layer["real_outcome"] is None


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
def test_declared_scenario_agrees_on_rest_mcp_cli(tool, rest, tmp_path, capsys):
    from fatebridge.application.examples import suggested_fields

    spec = SPECS[tool]
    payload = {"casting": CASES[0]["casting"]} if tool == "meihua_cast" else dict(TIME)
    payload["matter_scenario"] = "unfavorable_matter"
    fields = suggested_fields(spec, view="stage_emphasis")
    fields = fields + [
        (
            "input_normalized.matter_scenario"
            if tool == "meihua_cast"
            else "analysis_context.matter_scenario"
        )
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    mcp = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
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
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(mcp.structured_content) == business(cli)
    )


CACHE_SCRIPT = r"""
import importlib,importlib.util,json,sys
from pathlib import Path
fixture=Path(sys.argv[1]);importlib.import_module('fatebridge.core.requests')
name='fatebridge.core.requests.meihua';spec=importlib.util.spec_from_file_location(name,fixture/'v21-request-meihua.py');module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);setattr(sys.modules['fatebridge.core.requests'],'meihua',module)
assert 'matter_scenario' not in module.MeihuaInterpretationOptions.model_fields
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.services.divination import calculate_meihua_analysis
results=[]
for tool,func,args in [('cast',calculate_meihua_cast,{'casting':{'method':'existing','hexagram_code':'111111','moving_line':6}}),('time',calculate_meihua_analysis,{'analysis_year':2026,'analysis_month':10,'analysis_day':22,'analysis_hour':12,'analysis_timezone':'Asia/Shanghai'})]:
 for mode in ['omitted','none','provided']:
  kw=dict(args)
  if mode!='omitted':kw['matter_scenario']=None if mode=='none' else 'favorable_matter'
  out=func(**kw);results.append({'tool':tool,'mode':mode,'success':'error' not in out,'error_code':out.get('error_code')})
print(json.dumps(results))
"""


def test_archived_v21_cached_model_keeps_default_calls_and_rejects_new_field():
    proc = subprocess.run(
        [sys.executable, "-c", CACHE_SCRIPT, str(FIXTURE)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    results = json.loads(proc.stdout.splitlines()[-1])
    assert len(results) == 6
    for row in results:
        assert row["success"] is (row["mode"] != "provided")
        if row["mode"] == "provided":
            assert row["error_code"] == "validation_error"
