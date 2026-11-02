"""Three-valued stage applicability survives all published sixyao surfaces."""

import pytest

from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt

pytest_plugins = ["tests.test_agentic_nested_outputs"]


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
    from tests.test_result_delivery import reconstruct

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
