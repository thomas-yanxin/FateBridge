"""Clash facts, qualified effects and explanations survive public transports."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import suggested_fields
from fatebridge.application.result_delivery import DEFAULT_MCP_RESPONSE_CHARS
from tests.support.result_delivery import assert_same_run_receipt, reconstruct, store
from tests.support.transports import SPECS, business, call_cli, native, rest


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


@pytest.mark.parametrize(
    "gua,changed,hidden_lines,changed_void_lines",
    [
        pytest.param(
            "101011", "101001", [(3, "酉", "亥")], [(5, "子")], id="with-hidden"
        ),
        pytest.param("111111", None, [], [], id="without-hidden"),
    ],
)
def test_published_void_overview_without_focus_across_transports(
    gua, changed, hidden_lines, changed_void_lines, rest, tmp_path, capsys
):
    payload = dict(
        date="2000-04-27", time="12:00:00", gua_code=gua, changed_code=changed
    )
    fields = suggested_fields(SPECS["sixyao"], view="void_conditions_overview")
    output, *_ = all_surfaces(payload, fields, rest, tmp_path, capsys)
    evidence = output["liuyao_evidence"]
    calendar = evidence["calendar_conventions"]
    assert calendar["day_ganzhi"] == "乙卯" and calendar["month_branch"] == "辰"
    assert calendar["xunkong"] == ["子", "丑"]
    void = evidence["conditional_analysis"]["void_conditions"]
    assert "focus" not in void
    assert [(row["location"], row["position"]) for row in void["lines"]] == [
        ("visible", position) for position in range(1, 7)
    ]
    assert [
        (row["position"], line["changed_branch"])
        for row, line in zip(void["lines"], output["lines"], strict=True)
        if row["changed_is_xunkong"] is True
    ] == changed_void_lines
    assert [
        (row["position"], row["branch"], row["flying_branch"]) for row in void["hidden"]
    ] == hidden_lines
    for hidden in void["hidden"]:
        assert hidden["classification"] == "requires_hidden_strength_and_horizon"
        assert hidden["is_true_void"] is None
        assert hidden["is_permanently_void"] is None
        assert hidden["not_empty_conditions"][0]["matched"] is None
        assert hidden["empty_conditions"][0]["matched"] is False
    assert "有氣不動亦爲空" in {issue["scan"] for issue in void["textual_issues"]}
    assert void["horizon_status"] == "requires_question_horizon_and_total_judgment"
    assert "近远、总旺衰及疑义未决" in void["scope"]


def test_published_void_focus_view_keeps_explicit_selection_across_transports(
    rest, tmp_path, capsys
):
    payload = dict(
        date="2000-04-27",
        time="12:00:00",
        gua_code="101011",
        changed_code="101001",
        focus_line=2,
    )
    fields = suggested_fields(SPECS["sixyao"], view="void_conditions")
    output, *_ = all_surfaces(payload, fields, rest, tmp_path, capsys)
    detail = output["liuyao_evidence"]["conditional_analysis"]
    assert set(detail["void_conditions"]) == {"focus"}
    focus = detail["void_conditions"]["focus"]
    assert (focus["location"], focus["position"], focus["branch"]) == (
        "visible",
        2,
        "丑",
    )
    assert focus["is_xunkong"] is True
    assert focus["changed_is_xunkong"] is None
    assert focus["is_true_void"] is None
    assert detail["penalty_conditions"]["focus"]["position"] == 2


def test_unfocused_void_chart_retains_null_inputs_and_selection_across_transports(
    rest, tmp_path, capsys
):
    payload = dict(
        date="2000-04-27", time="12:00:00", gua_code="101011", changed_code="101001"
    )
    fields = suggested_fields(SPECS["sixyao"], view="void_conditions")
    for output in all_surfaces(
        payload,
        [
            *fields,
            "input_normalized",
            "liuyao_evidence.conditional_analysis.focus.selected",
        ],
        rest,
        tmp_path,
        capsys,
    ):
        inputs = output["input_normalized"]
        assert inputs["focus_line"] is None
        assert inputs["focus_kinship"] is None
        assert inputs["focus_kind"] is None
        assert inputs["event_horizon"] is None
        assert type(inputs["timing_days"]) is int and inputs["timing_days"] == 0
        detail = output["liuyao_evidence"]["conditional_analysis"]
        assert detail["focus"] == {"selected": None}
        assert detail["void_conditions"] == {"focus": None}
        assert detail["penalty_conditions"] == {"focus": None}


def test_void_overview_keeps_qualification_readable_from_budgeted_receipts(
    rest, tmp_path, capsys, store
):
    payload = dict(
        date="2000-06-25",
        time="12:00:00",
        gua_code="000111",
        changed_code="000101",
        event_horizon="near",
    )
    fields = suggested_fields(SPECS["sixyao"], view="void_conditions_overview")
    for shaped in all_surfaces(
        payload, fields, rest, tmp_path, capsys, budget=DEFAULT_MCP_RESPONSE_CHARS
    ):
        result_id = shaped["result_delivery"]["result_id"]
        original = reconstruct(store, result_id)
        assert_same_run_receipt(store, shaped, original)
        assert original["input_normalized"]["event_horizon"] == "near"
        void = original["liuyao_evidence"]["conditional_analysis"]["void_conditions"]
        day_rule = next(
            rule
            for rule in void["lines"][1]["not_empty_conditions"]
            if rule["rule_id"] == "day_generate"
        )
        assert day_rule["matched"] is True and day_rule["qualified_matched"] is False
        penalty = reconstruct(store, result_id, day_rule["qualification_source_path"])
        assert penalty["position"] == 2 and penalty["day_yin_growth_allowed"] is False


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
    from tests.support.result_delivery import reconstruct

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
