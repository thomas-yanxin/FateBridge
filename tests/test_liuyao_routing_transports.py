"""Route gates and their qualified, blocked and unknown states on three surfaces."""

import pytest

from tests.test_agentic_nested_outputs import business
from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt


@pytest.mark.parametrize(
    "day,base,changed,focus,kind,expected",
    [
        ("2002-05-27", "011110", "011101", 4, "visible", False),
        ("2006-09-28", "011110", "011101", 4, "visible", True),
        ("2002-05-21", "000101", "000001", 1, "hidden", None),
    ],
)
def test_route_qualification_survives_public_transports(
    day, base, changed, focus, kind, expected, rest, tmp_path, capsys
):
    payload = dict(
        date=day,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=base,
        changed_code=changed,
        focus_line=focus,
        focus_kind=kind,
    )
    field = "liuyao_evidence.conditional_analysis.routing_conditions"
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        detail = output["liuyao_evidence"]["conditional_analysis"]["routing_conditions"]
        assert detail["focus"].get("condition_match") is expected
        assert detail["focus"]["status"]
        assert (
            detail["adjudication"]
            == "successive_generation_conditions_not_final_relief"
        )


def test_false_route_leaf_has_no_sibling_requirement(rest, tmp_path, capsys):
    field = (
        "liuyao_evidence.conditional_analysis.routing_conditions.focus.condition_match"
    )
    payload = dict(
        date="2002-05-27",
        time="12:00:00",
        gua_code="011110",
        changed_code="011101",
        focus_line=4,
    )
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        assert output["liuyao_evidence"]["conditional_analysis"][
            "routing_conditions"
        ] == {"focus": {"condition_match": False}}


def test_same_run_rootless_route_snapshot_retains_direct_control(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "routing-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2002-05-27",
        time="12:00:00",
        gua_code="011110",
        changed_code="011101",
        focus_line=4,
    )
    restored = []
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"]
        raw = next(
            c for c in detail["role_effects"]["chains"] if c["positions"] == [6, 5, 4]
        )
        assert (
            raw["status"] == "successive_generation_candidate"
            and raw["route_condition_match"] is False
        )
        edge = next(
            e
            for e in detail["interaction_edges"]
            if e["source_kind"] == "base"
            and (e["source_position"], e["target_position"]) == (6, 4)
        )
        assert (
            edge["relation"] == "克爻" and edge["qualified_routing_condition"] is False
        )
        assert "用神月破日克无独立根，不能据路径认定已受生" in original["snapshot_text"]
        assert detail["routing_conditions"]["scope"] in original["snapshot_text"]
        path = "liuyao_evidence.conditional_analysis.routing_conditions"
        assert (
            reconstruct(store, shaped["result_delivery"]["result_id"], path)
            == detail["routing_conditions"]
        )
        restored.append(business(original))
    assert restored[0] == restored[1] == restored[2]
