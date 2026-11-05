"""Current day qualification, old raw positions and counterexamples survive RPC."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.liuyao.test_liuyao_month_break import CASES

REFERENCE = Path(__file__).parents[1] / "fixtures/liuyao_month_break_v24"
INPUTS = json.loads((REFERENCE / "public-input-mappings.json").read_text())["mappings"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
@pytest.mark.parametrize("project", [False, True])
def test_same_day_month_break_in_rest_native_mcp_cli(
    case, project, rest, tmp_path, capsys
):
    frozen = json.loads((REFERENCE / "public-input-freeze.json").read_text())
    assert (
        hashlib.sha256(
            (REFERENCE / "public-input-mappings.json").read_bytes()
        ).hexdigest()
        == frozen["mapping_sha256"]
    )
    assert (
        hashlib.sha256((REFERENCE / "cases-r1.json").read_bytes()).hexdigest()
        == frozen["source_cases_sha256"]
    )
    mapping = next(
        x
        for x in INPUTS
        if x["month"] == case["month"] and x["day_ganzhi"] == case["day_ganzhi"]
    )
    spec = SPECS["sixyao"]
    payload = dict(
        date=mapping["civil_datetime"][:10],
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=case["base_code"],
        changed_code=case["changed_code"],
        focus_line=case["focus_line"],
        timing_days=0,
        question="虚构教学：核对月破临日值的局部资格和独立反制，不判断现实成败",
    )
    base = "liuyao_evidence.conditional_analysis"
    fields = [
        base + "." + part
        for part in [
            "month_break_conditions",
            "classical_assessment",
            "back_generation_conditions",
            "generation_conditions",
            "control_conditions",
        ]
    ] + ["snapshot_text"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "true"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "true",
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=True)
    http = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        a = body["liuyao_evidence"]["conditional_analysis"]
        p = case["focus_line"]
        fact = a["month_break_conditions"]["lines"][p - 1]
        assert fact["raw_month_break"] is case["raw_month_break"]
        assert fact["day_value_exception"] is case["day_value_exception"]
        if "expected_supported" in case:
            assert (
                a["classical_assessment"]["lines"][p - 1]["strength"].get(
                    "is_supported"
                )
                is case["expected_supported"]
            )
        if "expected_target_admission" in case:
            assert (
                a["generation_conditions"]["focus"].get("target_reception_condition")
                is case["expected_target_admission"]
            )
        if "expected_qualified_back_generation" in case:
            gate = a["back_generation_conditions"]["sources"][p - 1]
            assert (
                gate.get("raw_condition_match") is case["expected_raw_back_generation"]
            )
            assert (
                gate.get("condition_match")
                is case["expected_qualified_back_generation"]
            )
        if fact["day_value_exception"]:
            assert (
                f"第{p}爻{case['expected_branch']}：原月令月破，本日同支值日"
                in body["snapshot_text"]
            )
        if case.get("expected_qualified_back_generation") is True:
            assert (
                f"第{p}爻本位变{case['expected_own_changed_branch']}：原月破，本日同支值日"
                in body["snapshot_text"]
            )
        assert not body.get("projection_warnings")


@pytest.mark.parametrize("project", [False, True])
def test_role_raw_month_control_and_current_exemption_remain_distinct(
    project, rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    payload = dict(
        date="2004-10-03",
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code="000001",
        changed_code="000001",
        focus_line=1,
        timing_days=0,
    )
    fields = [
        "liuyao_evidence.conditional_analysis.role_effects",
        "liuyao_evidence.conditional_analysis.month_break_conditions",
        "snapshot_text",
    ]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "true"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "true",
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=True)
    http = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        a = body["liuyao_evidence"]["conditional_analysis"]
        role = next(x for x in a["role_effects"]["lines"] if x["position"] == 3)
        assert role["role"] == "忌神"
        assert role["atom_values"]["injured_relation"] is True
        assert role["conditional_atom_values"]["injured_relation"] is False
        assert role["conditional_atom_values"]["calendar_moving_controls"] is False
        assert role["conditional_atom_values"]["void_or_break"] is False
        assert "第3爻卯：原月令月破，本日同支值日" in body["snapshot_text"]
