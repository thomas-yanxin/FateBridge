"""Explicit horizons and unresolved progression survive all three transports."""

import asyncio
import json

import pytest
from jsonschema import Draft202012Validator

from fatebridge.cli import run as cli_run
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.liuyao.test_liuyao_transports import assert_same_run_receipt

PAYLOAD = {
    "date": "2026-08-07",
    "time": "12:00:00",
    "zone": "Asia/Shanghai",
    "gua_code": "111110",
    "changed_code": "111100",
    "focus_line": 4,
}


@pytest.mark.parametrize(
    "horizon,state,now",
    [
        ("near", "retreat_held_for_near_event", False),
        ("long_term", "retreat_waits_for_weakness", None),
        (None, "requires_event_horizon", None),
    ],
)
@pytest.mark.parametrize("invalid_array_leaf", [False, True])
def test_progression_uses_shared_whole_array_projection_contract(
    horizon,
    state,
    now,
    invalid_array_leaf,
    rest,
    tmp_path,
    capsys,
):
    spec = SPECS["sixyao"]
    payload = {**PAYLOAD, **({"event_horizon": horizon} if horizon else {})}
    root = "liuyao_evidence.conditional_analysis"
    fields = (
        [f"{root}.lines.progress_conditions.state"]
        if invalid_array_leaf
        else [f"{root}.lines", f"{root}.role_effects"]
    )
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
    code, local = call_cli(
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
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    if invalid_array_leaf:
        # The shared API selects arrays whole, never by implicit traversal.
        assert response.status_code == 422 and code != 0 and protocol.is_error
        return
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        progress = output["liuyao_evidence"]["conditional_analysis"]["lines"][4][
            "progress_conditions"
        ]
        assert progress["state"] == state
        assert progress.get("condition_now") is now
        assert len(progress["clauses"]) == 4
        assert all(
            c["status"] in ("matched", "not_matched", "unresolved")
            for c in progress["clauses"]
        )


def test_explicit_horizon_flag_and_snapshot_keep_the_computed_condition(capsys):
    args = ["sixyao"]
    for key, value in PAYLOAD.items():
        args.extend(["--" + key.replace("_", "-"), str(value)])
    code = cli_run([*args, "--event-horizon", "near", "--response-char-limit", "0"])
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["input_normalized"]["event_horizon"] == "near"
    assert "第5爻退神配对：近事有扶，按已列条件不退" in output["snapshot_text"]


def test_invalid_horizon_is_rejected_by_rest_mcp_and_cli(rest, tmp_path, capsys):
    spec = SPECS["sixyao"]
    payload = {**PAYLOAD, "event_horizon": "guess"}
    response = rest.post(spec.rest_path, json=payload)
    code, _ = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 422 and code != 0 and protocol.is_error


def test_same_run_delivery_contains_progression_and_adjusted_atoms(
    rest, tmp_path, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.integration.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "progress-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    response = rest.post(
        SPECS["sixyao"].rest_path,
        json={**PAYLOAD, "event_horizon": "near"},
        params={"response_char_limit": 8192},
    )
    assert response.status_code == 200
    shaped = response.json()
    original = reconstruct(store, shaped["result_delivery"]["result_id"])
    assert_same_run_receipt(store, shaped, original)
    detail = original["liuyao_evidence"]["conditional_analysis"]
    assert (
        detail["lines"][4]["progress_conditions"]["state"]
        == "retreat_held_for_near_event"
    )
    role = next(r for r in detail["role_effects"]["lines"] if r["position"] == 5)
    assert role["atom_values"]["retreat"] is True
    assert role["progress_atom_values"]["retreat"] is False
