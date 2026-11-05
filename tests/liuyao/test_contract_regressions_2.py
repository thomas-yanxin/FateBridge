"""Related contract regressions with shared imports; original cases retained."""

from datetime import datetime, timedelta

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year
from tests.evaluation.test_agentic_nested_outputs import business, rest
from tests.liuyao.test_liuyao_clash_transports import all_surfaces
from tests.liuyao.test_liuyao_model_boundary import (
    CASES,
    ROOT,
    SOURCE_CASES,
    analytic_environment,
    assert_comparison,
)
from tests.liuyao.test_liuyao_transports import assert_same_run_receipt


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["id"])
@pytest.mark.parametrize("project", [False, True])
def test_same_completed_path_comparison_in_rest_native_mcp_cli(
    case, project, rest, tmp_path, capsys
):
    for output in all_surfaces(
        case["input"], [ROOT] if project else None, rest, tmp_path, capsys
    ):
        assert_comparison(output, case)


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["id"])
def test_source_adjudicated_current_month_change_survives_strict_projection(
    case, rest, tmp_path, capsys
):
    for output in all_surfaces(
        case["input"], [ROOT + ".month_changed"], rest, tmp_path, capsys
    ):
        value = output["liuyao_evidence"]["calendar_conventions"][
            "month_model_comparison"
        ]
        assert value == {
            "month_changed": SOURCE_CASES[case["id"]][
                "current_month_changed_between_completed_paths"
            ]
        }


@pytest.mark.parametrize("case", CASES[:2], ids=lambda x: x["id"])
def test_completed_probe_comparison_restores_the_same_hash_verified_run(
    case, rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.integration.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "model-choice-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(
        case["input"], None, rest, tmp_path, capsys, budget=8192
    ):
        result_id = shaped["result_delivery"]["result_id"]
        original = reconstruct(store, result_id)
        assert_same_run_receipt(store, shaped, original)
        assert_comparison(original, case)
        assert (
            reconstruct(store, result_id, ROOT)
            == original["liuyao_evidence"]["calendar_conventions"][
                "month_model_comparison"
            ]
        )


@pytest.mark.parametrize(
    "day,base,changed,source,target,back,control",
    [
        ("2002-01-29", "010011", "010010", 6, 4, True, True),
        ("2002-05-27", "100110", "100101", 5, 2, True, True),
        ("2000-02-29", "110110", "110100", 5, 2, False, None),
        ("2000-02-29", "110110", "110101", 5, 2, True, True),
    ],
)
def test_shared_back_support_and_control_across_transports(
    day, base, changed, source, target, back, control, rest, tmp_path, capsys
):
    payload = dict(
        date=day,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=base,
        changed_code=changed,
        focus_line=target,
    )
    # Modern synthetic input labels only, never ancient civil years.
    root = "liuyao_evidence.conditional_analysis"
    fields = [
        f"{root}.back_generation_conditions",
        f"{root}.control_conditions",
        f"{root}.generation_conditions",
        f"{root}.lines",
    ]
    for output in all_surfaces(payload, fields, rest, tmp_path, capsys):
        detail = output["liuyao_evidence"]["conditional_analysis"]
        support = detail["back_generation_conditions"]["sources"][source - 1]
        assert support.get("condition_match") is back
        pair = next(
            c
            for c in detail["control_conditions"]["controls"]
            if (c["source_position"], c["target_position"]) == (source, target)
        )
        assert pair.get("condition_match") is control
        assert pair["back_generation_source_path"] == support["source_path"]
        assert (
            detail["generation_conditions"]["sources"][source - 1][
                "back_generation_source_path"
            ]
            == support["source_path"]
        )
        if changed == "110101":
            assert detail["lines"][3]["activity_condition_match"] is True


def test_static_false_back_support_leaf_needs_no_siblings(rest, tmp_path, capsys):
    field = "liuyao_evidence.conditional_analysis.back_generation_conditions.focus.condition_match"
    payload = dict(
        date="2000-08-15",
        time="12:00:00",
        gua_code="110110",
        changed_code="110010",
        focus_line=5,
    )
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        assert output["liuyao_evidence"]["conditional_analysis"][
            "back_generation_conditions"
        ] == {"focus": {"condition_match": False}}


def test_same_run_back_support_control_and_snapshot_preserve_original_harm(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.integration.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "rescue-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2002-01-29",
        time="12:00:00",
        gua_code="010011",
        changed_code="010010",
        focus_line=4,
    )
    restored = []
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"]
        pair = next(
            c
            for c in detail["control_conditions"]["controls"]
            if (c["source_position"], c["target_position"]) == (6, 4)
        )
        assert pair["condition_match"] is True and pair["source_rescue_used"] is True
        assert any(h["location"] == "day" for h in pair["source_calendar_oppositions"])
        assert (
            detail["classical_assessment"]["lines"][5]["strength"].get("is_supported")
            is None
        )
        support = detail["back_generation_conditions"]["sources"][5]
        assert support["changed_calendar_relations"] == {"month": "克爻", "day": "生爻"}
        assert "第6爻卯本位化子：回头生空破门槛匹配" in original["snapshot_text"]
        assert "本位回头生支持该条件，原日月反制仍保留" in original["snapshot_text"]
        assert (
            detail["back_generation_conditions"]["scope"] in original["snapshot_text"]
        )
        path = "liuyao_evidence.conditional_analysis.back_generation_conditions"
        assert (
            reconstruct(store, shaped["result_delivery"]["result_id"], path)
            == detail["back_generation_conditions"]
        )
        restored.append(business(original))
    assert restored[0] == restored[1] == restored[2]


@pytest.mark.parametrize("offset", [-1, 0])
def test_fractional_boundary_clock_on_all_surfaces(offset, rest, tmp_path, capsys):
    term = next(t for t in get_solar_terms_for_year(2026) if t.name == "立春")
    moment = term.moment + timedelta(microseconds=offset)
    payload = dict(
        date=str(moment.date()),
        time=moment.time().isoformat(),
        zone="Asia/Shanghai",
        gua_code="111111",
    )
    fields = [
        "nongli.birth",
        "nongli.monthGanZi",
        "calendar_context.solar_datetime",
        "calendar_context.lunar_calendar.birth",
        "calendar_context.lunar_calendar.solar_datetime",
        "calendar_context.bazi_month_boundary",
        "liuyao_evidence.calendar_conventions",
    ]
    for result in all_surfaces(payload, fields, rest, tmp_path, capsys):
        expected = moment.replace(tzinfo=None)
        calendar = result["calendar_context"]
        for text in [
            result["nongli"]["birth"],
            calendar["solar_datetime"],
            calendar["lunar_calendar"]["birth"],
            calendar["lunar_calendar"]["solar_datetime"],
        ]:
            assert datetime.fromisoformat(text) == expected
        assert result["nongli"]["monthGanZi"][1] == ("丑" if offset < 0 else "寅")


def test_fractional_clock_same_run_delivery(rest, tmp_path, capsys, monkeypatch):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.integration.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "solar-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2026-02-04",
        time="04:02:07.500001",
        zone="Asia/Shanghai",
        gua_code="111111",
    )
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        assert original["nongli"]["birth"] == "2026-02-04 04:02:07.500001"
        assert "04:02:07.500001" in original["snapshot_text"]


def test_fractional_clock_leaf_projection(rest, tmp_path, capsys):
    for result in all_surfaces(
        dict(date="2026-02-04", time="04:02:07.500001", gua_code="111111"),
        ["calendar_context.solar_datetime"],
        rest,
        tmp_path,
        capsys,
    ):
        assert result["calendar_context"] == {
            "solar_datetime": "2026-02-04 04:02:07.500001"
        }


@pytest.mark.parametrize(
    "day,code,position,reception,stage,unknown",
    [
        ("2001-03-04", "111001", 2, True, False, False),
        ("2003-03-02", "111001", 2, None, True, False),
        ("2000-12-23", "001111", 2, True, False, False),
        ("2001-03-04", "000011", 5, False, True, False),
    ],
)
def test_stage_truths_and_admission_on_rest_cli_mcp(
    day, code, position, reception, stage, unknown, rest, tmp_path, capsys
):
    payload = dict(
        date=day,
        time="12:00:00",
        gua_code=code,
        focus_kind="hidden",
        focus_line=position,
    )
    root = "liuyao_evidence.conditional_analysis"
    for output in all_surfaces(
        payload,
        [root + ".stage_knowledge", root + ".hidden_conditions"],
        rest,
        tmp_path,
        capsys,
    ):
        detail = output["liuyao_evidence"]["conditional_analysis"]
        assert detail["stage_knowledge"]["known_stages"]["火"] == {
            "寅": "长生",
            "戌": "墓",
        }
        assert detail["stage_knowledge"]["table_complete"] is False
        h = next(h for h in detail["hidden_conditions"] if h["position"] == position)
        assert h["reception"].get("condition_match") is reception
        assert (
            h["stage_conditions"]["hidden_tomb_cessation"].get("condition_match")
            is stage
        )
        assert h["stage_conditions"]["has_relevant_unknown"] is unknown


def test_incomplete_table_false_leaf_has_no_sibling_requirement(rest, tmp_path, capsys):
    field = "liuyao_evidence.conditional_analysis.stage_knowledge.table_complete"
    payload = dict(
        date="2001-03-04",
        time="12:00:00",
        gua_code="111001",
        focus_kind="hidden",
        focus_line=2,
    )
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        assert output["liuyao_evidence"]["conditional_analysis"]["stage_knowledge"] == {
            "table_complete": False
        }


def test_same_run_known_tomb_text_does_not_turn_a_position_into_final_entry(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.integration.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "stage-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2003-03-02",
        time="12:00:00",
        gua_code="111001",
        focus_kind="hidden",
        focus_line=2,
    )
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        h = next(
            h
            for h in original["liuyao_evidence"]["conditional_analysis"][
                "hidden_conditions"
            ]
            if h["position"] == 2
        )
        assert h["stage_conditions"]["hidden_tomb_cessation"]["condition_match"] is True
        assert h["reception"]["condition_match"] is None
        assert "fire_stage_table_gap" not in h["reception"]["pending_reasons"]
        assert "伏神墓绝位置关系已核，尚未认定真墓真绝。" in original["snapshot_text"]
        path = h["stage_conditions"]["hidden_tomb_cessation"]["source_path"]
        assert (
            reconstruct(store, shaped["result_delivery"]["result_id"], path)
            == h["stage_conditions"]["hidden_tomb_cessation"]
        )
