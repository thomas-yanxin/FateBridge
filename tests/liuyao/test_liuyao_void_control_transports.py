"""Exact civil mapping, scoped control, strict projection and same-run hash."""

import asyncio
import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.liuyao.test_liuyao_clash_transports import all_surfaces
from tests.liuyao.test_liuyao_transports import assert_same_run_receipt
from tests.liuyao.test_liuyao_void_control_qualification import CASES, pair

ROOT = "liuyao_evidence.conditional_analysis"


def payload(case):
    return dict(
        date=case["public_date"],
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=case["base_code"],
        changed_code=case["changed_code"],
        focus_line=case["focus_line"],
        timing_days=0,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("project", [False, True])
def test_current_void_control_on_all_surfaces(case, project, rest, tmp_path, capsys):
    spec = SPECS["sixyao"]
    fields = [
        ROOT + "." + n
        for n in ["control_conditions", "clash_conditions", "void_conditions", "lines"]
    ] + ["liuyao_evidence.calendar_conventions", "snapshot_text"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    options = dict(response_char_limit=0)
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
        options.update(fields=fields, strict_fields=True, include_snapshot_text=True)
    http = rest.post(spec.rest_path, json=payload(case), params=params)
    code, cli = call_cli(spec, payload(case), tmp_path, capsys, flags=flags)
    mcp = asyncio.run(native(spec, payload(case), **options))
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [http.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for o in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(o)
        cal = o["liuyao_evidence"]["calendar_conventions"]
        assert cal["month_branch"] == case["month"]
        assert cal["day_ganzhi"] == case["day_ganzhi"]
        d = o["liuyao_evidence"]["conditional_analysis"]
        p = pair(d, case)
        assert p["condition_match"] is case["expected_control"]
        assert (
            p["source_void_fill_control_condition"]
            is case["expected_void_fill_control_qualification"]
        )
        if p["source_void_fill_used"]:
            assert "原旬空与日克事实仍保留" in o["snapshot_text"]
            assert any(h["location"] == "day" for h in p["source_calendar_oppositions"])
        assert not o.get("projection_warnings")
    evidence = os.environ.get("FATEBRIDGE_V31_EVIDENCE_DIR")
    if evidence:
        d = Path(evidence)
        d.mkdir(exist_ok=True, parents=True)
        (d / f"{case['id']}-{project}.json").write_text(
            json.dumps(
                dict(
                    input=payload(case),
                    outputs=dict(zip(["rest", "cli", "mcp"], outputs)),
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )


@pytest.mark.parametrize("valid", [True, False])
def test_qualification_nested_leaf_and_typo(valid, rest, tmp_path, capsys):
    spec = SPECS["sixyao"]
    field = (
        ROOT
        + ".control_conditions.void_fill_qualification."
        + ("ruleset_id" if valid else "rulset_id")
    )
    p = payload(CASES[0])
    params = [
        ("fields", field),
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    flags = [
        "--fields",
        field,
        "--strict-fields",
        "true",
        "--include-snapshot-text",
        "false",
        "--response-char-limit",
        "0",
    ]
    http = rest.post(spec.rest_path, json=p, params=params)
    code, cli = call_cli(spec, p, tmp_path, capsys, flags=flags)
    mcp = asyncio.run(
        native(
            spec,
            p,
            fields=[field],
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=0,
        )
    )
    if not valid:
        assert http.status_code == 422 and code == 1 and mcp.is_error
        for o in [http.json(), cli, mcp.structured_content]:
            assert o["issues"] == [{"path": field, "code": "unknown_projection_path"}]
        return
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    for o in [http.json(), cli, mcp.structured_content]:
        assert o["liuyao_evidence"]["conditional_analysis"]["control_conditions"] == {
            "void_fill_qualification": {
                "ruleset_id": "zengshan_current_void_fill_control_v31"
            }
        }


def test_same_run_control_and_raw_opposition_sha(rest, tmp_path, capsys, monkeypatch):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.integration.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "current-void-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(
        payload(CASES[0]), None, rest, tmp_path, capsys, budget=8192
    ):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        d = original["liuyao_evidence"]["conditional_analysis"]
        p = pair(d, CASES[0])
        assert p["condition_match"] is True and p["source_void_fill_used"] is True
        assert p["source_calendar_oppositions"]
        assert (
            reconstruct(store, shaped["result_delivery"]["result_id"], p["fact_path"])
            == p
        )


def test_v30_mapping_erratum_corrected_date_is_full_ganzhi(rest, tmp_path, capsys):
    for o in all_surfaces(
        dict(
            date="2000-07-01",
            time="12:00:00",
            zone="Asia/Shanghai",
            gua_code="110111",
            changed_code="010111",
            focus_line=1,
            timing_days=0,
        ),
        ["liuyao_evidence.calendar_conventions", ROOT + ".back_generation_conditions"],
        rest,
        tmp_path,
        capsys,
    ):
        cal = o["liuyao_evidence"]["calendar_conventions"]
        assert cal["month_branch"] == "午" and cal["day_ganzhi"] == "庚申"
        back = o["liuyao_evidence"]["conditional_analysis"][
            "back_generation_conditions"
        ]["focus"]
        assert back["raw_condition_match"] is True and back["condition_match"] is False
