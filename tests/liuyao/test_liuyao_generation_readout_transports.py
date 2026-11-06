"""Actual REST/native MCP/CLI payloads, strict fields and same-run SHA."""

import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.liuyao.test_liuyao_clash_transports import all_surfaces
from tests.liuyao.test_liuyao_generation_readout import (
    CASES,
    assert_returned_gate_readout,
)
from tests.support.result_delivery import assert_same_run_receipt
from tests.support.transports import SPECS, business, native, surface_calls


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("project", [False, True])
def test_generation_readout_full_and_strict_protocols(case, project, surface_calls):
    spec = SPECS["sixyao"]
    fields = [
        "liuyao_evidence.conditional_analysis.generation_conditions",
        "liuyao_evidence.calendar_conventions",
        "snapshot_text",
    ]
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
    http, mcp, code, cli = surface_calls(
        spec, case["payload"], params=params, options=options, flags=flags
    )
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [http.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for o in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(o)
        assert_returned_gate_readout(o, case)
        assert not o.get("projection_warnings")
    if evidence := os.environ.get("FATEBRIDGE_V33_EVIDENCE_DIR"):
        p = Path(evidence)
        p.mkdir(exist_ok=True, parents=True)
        (p / f"{case['id']}-{project}.json").write_text(
            json.dumps(
                dict(
                    input=case["payload"],
                    outputs=dict(zip(["rest", "cli", "mcp"], outputs)),
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )


def test_generation_readout_same_run_full_payload_sha(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.support.result_delivery import reconstruct

    case = CASES[0]
    store = delivery.ResultStore(tmp_path / "generation-readout-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(
        case["payload"], None, rest, tmp_path, capsys, budget=8192
    ):
        restored = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, restored)
        assert_returned_gate_readout(restored, case)


def test_published_first_view_retains_qualification_without_snapshot(surface_calls):
    from fatebridge.application.examples import evidence_views, suggested_fields

    spec = SPECS["sixyao"]
    fields = suggested_fields(spec)
    assert fields == evidence_views(spec)["line_reading"]["fields"]
    case = CASES[0]
    http, mcp, code, cli = surface_calls(
        spec,
        case["payload"],
        projection={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        },
    )
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [http.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for o in outputs:
        assert "snapshot_text" not in o
        assert_returned_gate_readout(o, case, check_snapshot=False)
        assert not o.get("projection_warnings")
    if evidence := os.environ.get("FATEBRIDGE_V33_EVIDENCE_DIR"):
        (Path(evidence) / "published-first-view-no-snapshot.json").write_text(
            json.dumps(
                dict(fields=fields, outputs=dict(zip(["rest", "cli", "mcp"], outputs))),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )


@pytest.mark.parametrize("kind", ["whole_array", "array_child", "unknown_object"])
def test_generation_array_and_invalid_projection_paths(kind, surface_calls):
    from tests.liuyao.test_liuyao_generation_readout import edge

    spec = SPECS["sixyao"]
    root = "liuyao_evidence.conditional_analysis.generation_conditions."
    field = (
        root
        + {
            "whole_array": "generations",
            "array_child": "generations.qualification_explanation",
            "unknown_object": "qualification_explanaton",
        }[kind]
    )
    fields = [field]
    case = CASES[0]
    http, mcp, code, cli = surface_calls(
        spec,
        case["payload"],
        projection={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        },
    )
    outputs = [http.json(), cli, mcp.structured_content]
    if kind != "whole_array":
        assert http.status_code == 422 and code == 1 and mcp.is_error
        expected_code = (
            "non_object_projection_path"
            if kind == "array_child"
            else "unknown_projection_path"
        )
        for o in outputs:
            assert o["issues"] == [{"path": field, "code": expected_code}]
    else:
        assert http.status_code == 200 and code == 0 and not mcp.is_error
        for o in outputs:
            p = edge(o, case)
            assert (
                p["benefit_now"] is False
                and p["target_yin_generation_allowed"] is False
            )
            assert "本条生扶路径条件未匹配" in p["qualification_explanation"]
            assert "snapshot_text" not in o and not o.get("projection_warnings")
    if evidence := os.environ.get("FATEBRIDGE_V33_EVIDENCE_DIR"):
        (Path(evidence) / f"qualification-selection-{kind}.json").write_text(
            json.dumps(
                dict(fields=fields, outputs=dict(zip(["rest", "cli", "mcp"], outputs))),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
