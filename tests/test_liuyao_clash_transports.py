"""Clash facts, qualified effects and explanations survive public transports."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_liuyao_transports import assert_same_run_receipt


def all_surfaces(payload, fields, rest, tmp_path, capsys, budget=0):
    spec = SPECS["sixyao"]
    options = {"response_char_limit": budget}
    flags = ["--response-char-limit", str(budget)]
    params = [("response_char_limit", str(budget))]
    if fields:
        options.update(fields=fields, strict_fields=True, include_snapshot_text=False)
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
    response = rest.post(spec.rest_path, json=payload, params=params)
    code, local = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **options))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    if not budget:
        assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
    return outputs


@pytest.mark.parametrize(
    "day,code,changed,focus,fill,broken,scatter",
    [
        ("2000-08-15", "110110", "110010", 4, False, False, False),
        ("2000-09-27", "010010", None, 3, True, False, None),
        ("2000-10-04", "000000", None, 4, False, None, None),
    ],
)
def test_clash_tristates_and_void_membership_across_transports(
    day, code, changed, focus, fill, broken, scatter, rest, tmp_path, capsys
):
    root = "liuyao_evidence.conditional_analysis"
    payload = dict(
        date=day, time="12:00:00", zone="Asia/Shanghai", gua_code=code, focus_line=focus
    )
    if changed:
        payload["changed_code"] = changed
    for output in all_surfaces(
        payload,
        [f"{root}.clash_conditions", f"{root}.void_conditions", f"{root}.lines"],
        rest,
        tmp_path,
        capsys,
    ):
        detail = output["liuyao_evidence"]["conditional_analysis"]
        clash = detail["clash_conditions"]["focus"]
        assert clash.get("day_void_fill_condition") is fill
        assert clash.get("day_break_condition") is broken
        assert clash.get("moving_scatter_condition") is scatter
        assert clash["day_break_status"] and clash["scatter_status"]
        if fill:
            assert detail["void_conditions"]["focus"]["is_xunkong"] is True
            assert detail["lines"][focus - 1]["activity_condition_match"] is True
        if broken is None:
            assert detail["lines"][focus - 1].get("activity_condition_match") is None


def test_false_clash_leaf_does_not_require_sibling_fields(rest, tmp_path, capsys):
    field = "liuyao_evidence.conditional_analysis.clash_conditions.focus.moving_scatter_condition"
    for output in all_surfaces(
        dict(
            date="2000-08-15",
            time="12:00:00",
            gua_code="110110",
            changed_code="110010",
            focus_line=4,
        ),
        [field],
        rest,
        tmp_path,
        capsys,
    ):
        assert output["liuyao_evidence"]["conditional_analysis"][
            "clash_conditions"
        ] == {"focus": {"moving_scatter_condition": False}}


def test_clash_and_faithful_snapshot_restore_from_same_run(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "clash-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2000-08-15",
        time="12:00:00",
        gua_code="110110",
        changed_code="110010",
        focus_line=2,
    )
    restored = []
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"]
        water = next(r for r in detail["role_effects"]["lines"] if r["position"] == 4)
        assert water["atom_values"]["injured_relation"] is True
        assert water["conditional_atom_values"]["injured_relation"] is False
        path = "liuyao_evidence.conditional_analysis.clash_conditions"
        assert (
            reconstruct(store, shaped["result_delivery"]["result_id"], path)
            == detail["clash_conditions"]
        )
        assert detail["clash_conditions"]["scope"] in original["snapshot_text"]
        restored.append(business(original))
    assert restored[0] == restored[1] == restored[2]
